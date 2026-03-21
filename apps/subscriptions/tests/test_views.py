"""
Tests for subscription views.
"""

import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.tests.factories import ClientFactory, TrainerFactory
from apps.subscriptions.models import Subscription
from apps.subscriptions.tests.factories import (
    ActiveSubscriptionFactory,
    BasicPlanFactory,
    PaymentRecordFactory,
    ProPlanFactory,
    SubscriptionFactory,
)

PLANS_URL = "/api/v1/subscriptions/plans/"
STATUS_URL = "/api/v1/subscriptions/status/"
PAYSTACK_CHECKOUT_URL = "/api/v1/subscriptions/checkout/paystack/"
STRIPE_CHECKOUT_URL = "/api/v1/subscriptions/checkout/stripe/"
PAYSTACK_WEBHOOK_URL = "/api/v1/subscriptions/webhook/paystack/"
STRIPE_WEBHOOK_URL = "/api/v1/subscriptions/webhook/stripe/"
CANCEL_URL = "/api/v1/subscriptions/cancel/"
BILLING_URL = "/api/v1/subscriptions/billing/"


def _auth_client(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


def _paystack_signature(payload_bytes, secret="test-secret"):
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha512).hexdigest()


# ---------------------------------------------------------------------------
# PlansView
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestPlansView:
    def test_returns_all_active_plans(self):
        BasicPlanFactory()
        ProPlanFactory()
        client = APIClient()
        resp = client.get(PLANS_URL)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["data"]) == 2

    def test_returns_prices_in_ngn_and_usd(self):
        BasicPlanFactory()
        client = APIClient()
        resp = client.get(PLANS_URL)
        plan = resp.data["data"][0]
        assert "price_ngn" in plan
        assert "price_usd" in plan

    def test_returns_features_list(self):
        BasicPlanFactory()
        client = APIClient()
        resp = client.get(PLANS_URL)
        assert "features" in resp.data["data"][0]

    def test_unauthenticated_allowed(self):
        client = APIClient()
        resp = client.get(PLANS_URL)
        assert resp.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# SubscriptionStatusView
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestSubscriptionStatusView:
    def test_returns_trial_status_with_days_remaining(self):
        user = TrainerFactory()
        BasicPlanFactory()
        SubscriptionFactory(
            user=user, trial_end=timezone.now() + timedelta(days=10, hours=1)
        )
        resp = _auth_client(user).get(STATUS_URL)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.data["data"]
        assert data["status"] == "trial"
        assert data["days_remaining"] == 10

    def test_returns_active_status_after_activation(self):
        user = TrainerFactory()
        BasicPlanFactory()
        ActiveSubscriptionFactory(user=user)
        resp = _auth_client(user).get(STATUS_URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"]["status"] == "active"

    def test_client_returns_403(self):
        user = ClientFactory()
        resp = _auth_client(user).get(STATUS_URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_returns_401(self):
        resp = APIClient().get(STATUS_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# PaystackCheckoutView
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestPaystackCheckoutView:
    def test_initializes_transaction(self):
        user = TrainerFactory()
        BasicPlanFactory()
        SubscriptionFactory(user=user)

        mock_response = {
            "status": True,
            "data": {
                "authorization_url": "https://checkout.paystack.com/abc",
                "reference": "ref_abc123",
            },
        }
        with patch(
            "apps.subscriptions.views.PaystackGateway.initialize_transaction",
            return_value=mock_response,
        ):
            resp = _auth_client(user).post(PAYSTACK_CHECKOUT_URL, format="json")

        assert resp.status_code == status.HTTP_200_OK
        assert "authorization_url" in resp.data["data"]

    def test_client_returns_403(self):
        user = ClientFactory()
        resp = _auth_client(user).post(PAYSTACK_CHECKOUT_URL, format="json")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_returns_401(self):
        resp = APIClient().post(PAYSTACK_CHECKOUT_URL, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# StripeCheckoutView
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestStripeCheckoutView:
    def test_creates_checkout_session(self):
        user = TrainerFactory()
        BasicPlanFactory()
        SubscriptionFactory(user=user)

        mock_customer = MagicMock()
        mock_customer.id = "cus_test_123"
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/session"

        with (
            patch(
                "apps.subscriptions.views.StripeGateway.create_customer",
                return_value=mock_customer,
            ),
            patch(
                "apps.subscriptions.views.StripeGateway.create_checkout_session",
                return_value=mock_session,
            ),
        ):
            resp = _auth_client(user).post(
                STRIPE_CHECKOUT_URL,
                data={"price_id": "price_test_123"},
                format="json",
            )

        assert resp.status_code == status.HTTP_200_OK
        assert "checkout_url" in resp.data["data"]

    def test_client_returns_403(self):
        user = ClientFactory()
        resp = _auth_client(user).post(STRIPE_CHECKOUT_URL, format="json")
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# PaystackWebhookView
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestPaystackWebhookView:
    def _post_webhook(self, event_type, data, secret="test-secret"):
        payload = json.dumps({"event": event_type, "data": data}).encode()
        sig = _paystack_signature(payload, secret)
        client = APIClient()
        return client.post(
            PAYSTACK_WEBHOOK_URL,
            data=payload,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=sig,
        )

    def test_charge_success_activates_subscription(self):
        user = TrainerFactory()
        BasicPlanFactory()
        sub = SubscriptionFactory(user=user)

        event_data = {
            "reference": "ref_webhook_001",
            "amount": 1500000,
            "currency": "NGN",
            "customer": {"email": user.email},
            "paid_at": "2024-01-01T00:00:00.000Z",
            "metadata": {"user_id": str(user.id)},
        }
        with patch(
            "apps.subscriptions.views.PaystackGateway.verify_webhook",
            return_value=True,
        ):
            resp = self._post_webhook("charge.success", event_data)

        assert resp.status_code == status.HTTP_200_OK
        sub.refresh_from_db()
        assert sub.status == Subscription.Status.ACTIVE

    def test_charge_success_resets_payment_retries(self):
        user = TrainerFactory()
        BasicPlanFactory()
        sub = SubscriptionFactory(user=user)
        sub.payment_retry_count = 2
        sub.next_payment_retry_at = timezone.now() + timedelta(days=7)
        sub.save(update_fields=["payment_retry_count", "next_payment_retry_at"])

        event_data = {
            "reference": "ref_reset_001",
            "amount": 1500000,
            "currency": "NGN",
            "customer": {"email": user.email},
            "paid_at": "2024-01-01T00:00:00.000Z",
            "metadata": {"user_id": str(user.id)},
        }
        with (
            patch(
                "apps.subscriptions.views.PaystackGateway.verify_webhook",
                return_value=True,
            ),
            patch("apps.accounts.emails.send_subscription_activated_email"),
        ):
            self._post_webhook("charge.success", event_data)

        sub.refresh_from_db()
        assert sub.payment_retry_count == 0
        assert sub.next_payment_retry_at is None

    def test_payment_failed_schedules_retry(self):
        user = TrainerFactory()
        BasicPlanFactory()
        sub = ActiveSubscriptionFactory(user=user)

        event_data = {
            "customer": {"email": user.email},
            "metadata": {"user_id": str(user.id)},
        }
        with (
            patch(
                "apps.subscriptions.views.PaystackGateway.verify_webhook",
                return_value=True,
            ),
            patch("apps.accounts.emails.send_payment_retry_email"),
        ):
            resp = self._post_webhook("invoice.payment_failed", event_data)

        assert resp.status_code == status.HTTP_200_OK
        sub.refresh_from_db()
        assert sub.payment_retry_count == 1
        assert sub.next_payment_retry_at is not None

    def test_invalid_signature_returns_400(self):
        payload = json.dumps({"event": "charge.success", "data": {}}).encode()
        client = APIClient()
        resp = client.post(
            PAYSTACK_WEBHOOK_URL,
            data=payload,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE="bad_sig",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_subscription_disable_enters_grace(self):
        user = TrainerFactory()
        BasicPlanFactory()
        sub = ActiveSubscriptionFactory(user=user)

        event_data = {
            "customer": {"email": user.email},
            "metadata": {"user_id": str(user.id)},
        }
        with patch(
            "apps.subscriptions.views.PaystackGateway.verify_webhook",
            return_value=True,
        ):
            resp = self._post_webhook("subscription.disable", event_data)

        assert resp.status_code == status.HTTP_200_OK
        sub.refresh_from_db()
        assert sub.status == Subscription.Status.GRACE


# ---------------------------------------------------------------------------
# StripeWebhookView
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestStripeWebhookView:
    def test_checkout_session_completed_activates_subscription(self):
        user = TrainerFactory()
        BasicPlanFactory()
        sub = SubscriptionFactory(user=user)

        mock_event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_test_456",
                    "subscription": "sub_test_456",
                    "metadata": {"user_id": str(user.id)},
                }
            },
        }
        with patch(
            "apps.subscriptions.views.StripeGateway.verify_webhook",
            return_value=mock_event,
        ):
            payload = json.dumps(mock_event).encode()
            resp = APIClient().post(
                STRIPE_WEBHOOK_URL,
                data=payload,
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="sig_test",
            )

        assert resp.status_code == status.HTTP_200_OK
        sub.refresh_from_db()
        assert sub.status == Subscription.Status.ACTIVE

    def test_invoice_payment_succeeded_resets_retries(self):
        user = TrainerFactory()
        BasicPlanFactory()
        sub = ActiveSubscriptionFactory(
            user=user,
            payment_retry_count=1,
            next_payment_retry_at=timezone.now() + timedelta(days=3),
        )

        mock_event = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": "in_test_success",
                    "amount_paid": 1500000,
                    "currency": "usd",
                    "customer": "cus_test_789",
                    "subscription": sub.provider_subscription_id,
                    "metadata": {"user_id": str(user.id)},
                }
            },
        }
        with (
            patch(
                "apps.subscriptions.views.StripeGateway.verify_webhook",
                return_value=mock_event,
            ),
            patch("apps.accounts.emails.send_subscription_activated_email"),
        ):
            payload = json.dumps(mock_event).encode()
            APIClient().post(
                STRIPE_WEBHOOK_URL,
                data=payload,
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="sig_test",
            )

        sub.refresh_from_db()
        assert sub.payment_retry_count == 0
        assert sub.next_payment_retry_at is None

    def test_invoice_payment_failed_schedules_retry(self):
        user = TrainerFactory()
        BasicPlanFactory()
        sub = ActiveSubscriptionFactory(user=user)

        mock_event = {
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "customer": "cus_test_789",
                    "subscription": sub.provider_subscription_id,
                    "metadata": {"user_id": str(user.id)},
                }
            },
        }
        with (
            patch(
                "apps.subscriptions.views.StripeGateway.verify_webhook",
                return_value=mock_event,
            ),
            patch("apps.accounts.emails.send_payment_retry_email"),
        ):
            payload = json.dumps(mock_event).encode()
            resp = APIClient().post(
                STRIPE_WEBHOOK_URL,
                data=payload,
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="sig_test",
            )

        assert resp.status_code == status.HTTP_200_OK
        sub.refresh_from_db()
        assert sub.payment_retry_count == 1
        assert sub.next_payment_retry_at is not None

    def test_invalid_stripe_signature_returns_400(self):
        with patch(
            "apps.subscriptions.views.StripeGateway.verify_webhook",
            side_effect=Exception("Invalid signature"),
        ):
            resp = APIClient().post(
                STRIPE_WEBHOOK_URL,
                data=b"{}",
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="bad_sig",
            )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# CancelSubscriptionView
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestCancelSubscriptionView:
    def test_cancel_returns_200(self):
        user = TrainerFactory()
        BasicPlanFactory()
        ActiveSubscriptionFactory(user=user)
        resp = _auth_client(user).post(CANCEL_URL, format="json")
        assert resp.status_code == status.HTTP_200_OK

    def test_cancel_sets_status_to_cancelled(self):
        user = TrainerFactory()
        BasicPlanFactory()
        sub = ActiveSubscriptionFactory(user=user)
        _auth_client(user).post(CANCEL_URL, format="json")
        sub.refresh_from_db()
        assert sub.status == Subscription.Status.CANCELLED

    def test_client_returns_403(self):
        user = ClientFactory()
        resp = _auth_client(user).post(CANCEL_URL, format="json")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_no_subscription_returns_404(self):
        user = TrainerFactory()
        resp = _auth_client(user).post(CANCEL_URL, format="json")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# BillingHistoryView
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestBillingHistoryView:
    def test_returns_paginated_payment_records(self):
        user = TrainerFactory()
        BasicPlanFactory()
        sub = SubscriptionFactory(user=user)
        PaymentRecordFactory.create_batch(3, subscription=sub)
        resp = _auth_client(user).get(BILLING_URL)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["data"]) == 3

    def test_client_returns_403(self):
        user = ClientFactory()
        resp = _auth_client(user).get(BILLING_URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_empty_history_returns_empty_list(self):
        user = TrainerFactory()
        BasicPlanFactory()
        SubscriptionFactory(user=user)
        resp = _auth_client(user).get(BILLING_URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"] == []
