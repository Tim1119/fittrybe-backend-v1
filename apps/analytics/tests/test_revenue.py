"""Tests for GET /api/v1/analytics/revenue/."""

import pytest

REVENUE_URL = "/api/v1/analytics/revenue/"


def _make_subscription(user):
    """Create a minimal Subscription for the given user."""
    from datetime import timedelta

    from django.utils import timezone as tz

    from apps.subscriptions.models import PlanConfig, Subscription

    plan, _ = PlanConfig.objects.get_or_create(
        plan="basic",
        defaults={
            "display_name": "Basic",
            "price_ngn": "5000.00",
            "price_usd": "10.00",
            "is_active": True,
        },
    )
    return Subscription.objects.create(
        user=user,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        trial_end=tz.now() + timedelta(days=14),
    )


def _make_payment(subscription, amount, currency="NGN", status="success", ref=None):
    import uuid

    from django.utils import timezone as tz

    from apps.subscriptions.models import PaymentRecord

    return PaymentRecord.objects.create(
        subscription=subscription,
        amount=amount,
        currency=currency,
        status=status,
        provider="paystack",
        provider_reference=ref or str(uuid.uuid4()),
        paid_at=tz.now(),
    )


@pytest.mark.django_db
class TestRevenuePermissions:
    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.get(REVENUE_URL)
        assert resp.status_code == 401

    def test_client_returns_403(self, client_setup):
        _, _, api = client_setup
        resp = api.get(REVENUE_URL)
        assert resp.status_code == 403

    def test_trainer_can_access(self, trainer_setup):
        _, _, api = trainer_setup
        resp = api.get(REVENUE_URL)
        assert resp.status_code == 200

    def test_gym_can_access(self, gym_setup):
        _, _, api = gym_setup
        resp = api.get(REVENUE_URL)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestRevenueShape:
    def test_response_has_all_required_keys(self, trainer_setup):
        _, _, api = trainer_setup
        resp = api.get(REVENUE_URL)
        data = resp.data["data"]
        expected = {
            "platform_revenue_ngn",
            "platform_revenue_usd",
            "marketplace_enquiry_count",
            "note",
            "period",
        }
        assert expected.issubset(data.keys())

    def test_note_is_present(self, trainer_setup):
        _, _, api = trainer_setup
        resp = api.get(REVENUE_URL)
        assert resp.data["data"]["note"] != ""


@pytest.mark.django_db
class TestRevenueData:
    def test_sums_ngn_successful_payments(self, trainer_setup):
        user, _, api = trainer_setup
        sub = _make_subscription(user)
        _make_payment(sub, "5000.00", currency="NGN", status="success")
        _make_payment(sub, "3000.00", currency="NGN", status="success")
        _make_payment(sub, "2000.00", currency="NGN", status="failed")  # excluded

        resp = api.get(REVENUE_URL, {"period": "month"})
        assert resp.data["data"]["platform_revenue_ngn"] == "8000.00"

    def test_sums_usd_successful_payments(self, trainer_setup):
        user, _, api = trainer_setup
        sub = _make_subscription(user)
        _make_payment(sub, "10.00", currency="USD", status="success")

        resp = api.get(REVENUE_URL, {"period": "month"})
        assert resp.data["data"]["platform_revenue_usd"] == "10.00"

    def test_zero_revenue_when_no_payments(self, trainer_setup):
        _, _, api = trainer_setup
        resp = api.get(REVENUE_URL, {"period": "all"})
        d = resp.data["data"]
        assert d["platform_revenue_ngn"] == "0.00"
        assert d["platform_revenue_usd"] == "0.00"

    def test_only_sees_own_payments(self, trainer_setup, trainer2_setup):
        user, _, api = trainer_setup
        user2, _, _ = trainer2_setup
        sub2 = _make_subscription(user2)
        _make_payment(sub2, "9999.00", currency="NGN", status="success")

        resp = api.get(REVENUE_URL, {"period": "all"})
        assert resp.data["data"]["platform_revenue_ngn"] == "0.00"

    def test_marketplace_enquiry_count(self, trainer_setup):
        from apps.marketplace.models import Product, ProductEnquiry
        from apps.profiles.tests.factories import ClientProfileFactory

        _, trainer_profile, api = trainer_setup
        product = Product.objects.create(
            trainer=trainer_profile,
            name="Product",
            description="desc",
            category=Product.Category.PROGRAM,
            price="1000.00",
            status=Product.Status.ACTIVE,
        )
        client_profile = ClientProfileFactory()
        ProductEnquiry.objects.create(
            product=product,
            client=client_profile,
            message="I want this",
        )

        resp = api.get(REVENUE_URL, {"period": "month"})
        assert resp.data["data"]["marketplace_enquiry_count"] == 1
