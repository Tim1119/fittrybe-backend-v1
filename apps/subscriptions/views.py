"""
Subscription views — billing, checkout, webhooks.
"""

import json
import logging
from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.core.error_codes import ErrorCode
from apps.core.pagination import StandardPagination
from apps.core.permissions import IsTrainerOrGym
from apps.core.responses import APIResponse
from apps.subscriptions.gateways.paystack import PaystackGateway
from apps.subscriptions.gateways.stripe_gateway import StripeGateway
from apps.subscriptions.models import PaymentRecord, PlanConfig, Subscription
from apps.subscriptions.serializers import (
    PaymentRecordSerializer,
    PlanConfigSerializer,
    SubscriptionSerializer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------
@extend_schema(
    summary="List subscription plans",
    description=(
        "Returns all active subscription plans with pricing in NGN and USD, "
        "trial duration, grace period, and feature lists. "
        "Public endpoint — no authentication required."
    ),
    responses={
        200: OpenApiResponse(
            description="List of active plans with pricing and feature details"
        ),
    },
    tags=["Subscriptions"],
    auth=[],
)
class PlansView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        plans = PlanConfig.objects.filter(is_active=True)
        serializer = PlanConfigSerializer(plans, many=True)
        return APIResponse.success(
            data=serializer.data,
            message="Plans retrieved successfully.",
        )


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
@extend_schema(
    summary="Get subscription status",
    description=(
        "Returns the current subscription record for the authenticated trainer or gym, "
        "including status (trial, active, grace, locked, cancelled), "
        "trial end date, current period dates, and provider details. "
        "Only accessible to trainer and gym roles."
    ),
    responses={
        200: OpenApiResponse(
            description="Subscription record with status and period details"
        ),
        401: OpenApiResponse(description="Not authenticated"),
        403: OpenApiResponse(description="Client accounts do not have subscriptions"),
        404: OpenApiResponse(description="No subscription found for this user"),
    },
    tags=["Subscriptions"],
)
class SubscriptionStatusView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    def get(self, request):
        try:
            sub = request.user.subscription
        except Subscription.DoesNotExist:
            return APIResponse.error(
                message="No subscription found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        serializer = SubscriptionSerializer(sub)
        return APIResponse.success(
            data=serializer.data,
            message="Subscription status retrieved.",
        )


# ---------------------------------------------------------------------------
# Paystack checkout
# ---------------------------------------------------------------------------
@extend_schema(
    summary="Initialize Paystack checkout",
    description=(
        "Initializes a Paystack transaction for the authenticated trainer or gym. "
        "Plan and amount are determined from the user's role. "
        "Returns an authorization URL to redirect to Paystack's payment page."
    ),
    request=inline_serializer(name="PaystackCheckoutRequest", fields={}),
    responses={
        200: OpenApiResponse(
            description="Transaction initialized — authorization_url and reference"
        ),
        401: OpenApiResponse(description="Not authenticated"),
        403: OpenApiResponse(description="Only trainer and gym accounts can subscribe"),
        404: OpenApiResponse(description="No active plan configured for this role"),
        502: OpenApiResponse(description="Paystack API error"),
    },
    tags=["Subscriptions"],
)
class PaystackCheckoutView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    def post(self, request):
        try:
            plan = PlanConfig.get_for_role(request.user.role)
        except PlanConfig.DoesNotExist:
            return APIResponse.error(
                message="No active plan found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        amount_kobo = int(plan.price_ngn * 100)
        gateway = PaystackGateway()
        result = gateway.initialize_transaction(
            email=request.user.email,
            amount_kobo=amount_kobo,
            metadata={
                "user_id": str(request.user.id),
                "plan": plan.plan,
            },
        )
        if result.get("status"):
            return APIResponse.success(
                data={
                    "authorization_url": result["data"]["authorization_url"],
                    "reference": result["data"]["reference"],
                },
                message="Payment initialized successfully.",
            )
        return APIResponse.error(
            message="Failed to initialize payment. Please try again.",
            status_code=502,
        )


# ---------------------------------------------------------------------------
# Stripe checkout
# ---------------------------------------------------------------------------
@extend_schema(
    summary="Initialize Stripe checkout",
    description=(
        "Creates a Stripe checkout session for the authenticated trainer or gym. "
        "Requires a Stripe price_id for the chosen plan. "
        "Returns a checkout_url to redirect the user to Stripe's hosted payment page."
    ),
    request=inline_serializer(
        name="StripeCheckoutRequest",
        fields={
            "price_id": drf_serializers.CharField(
                help_text="Stripe price ID, e.g. price_1ABC..."
            )
        },
    ),
    responses={
        200: OpenApiResponse(
            description="Checkout session created — returns checkout_url"
        ),
        400: OpenApiResponse(description="price_id is required"),
        401: OpenApiResponse(description="Not authenticated"),
        403: OpenApiResponse(description="Only trainer and gym accounts can subscribe"),
        502: OpenApiResponse(description="Stripe API error"),
    },
    tags=["Subscriptions"],
)
class StripeCheckoutView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    def post(self, request):
        price_id = request.data.get("price_id", "")
        if not price_id:
            return APIResponse.error(
                message="price_id is required.",
                code=ErrorCode.VALIDATION_ERROR,
            )

        gateway = StripeGateway()
        try:
            customer = gateway.create_customer(
                email=request.user.email,
                metadata={"user_id": str(request.user.id)},
            )
            session = gateway.create_checkout_session(
                customer_id=customer.id,
                price_id=price_id,
                success_url=f"{request.build_absolute_uri('/')}subscription/success",
                cancel_url=f"{request.build_absolute_uri('/')}subscription/cancel",
            )
        except Exception as exc:
            logger.exception("Stripe checkout error: %s", exc)
            return APIResponse.error(
                message="Failed to create checkout session.",
                status_code=502,
            )

        return APIResponse.success(
            data={"checkout_url": session.url},
            message="Stripe checkout session created.",
        )


# ---------------------------------------------------------------------------
# Paystack webhook
# ---------------------------------------------------------------------------
@extend_schema(
    summary="Paystack webhook receiver",
    description=(
        "Receives and processes Paystack webhook events. "
        "Verifies the HMAC-SHA512 signature before handling. "
        "Handles: charge.success, subscription.disable, invoice.payment_failed. "
        "This endpoint is called by Paystack servers — do not call it directly."
    ),
    responses={
        200: OpenApiResponse(description="Webhook received and queued for processing"),
        400: OpenApiResponse(description="Invalid signature or malformed payload"),
    },
    tags=["Subscriptions"],
    auth=[],
    exclude=True,
)
class PaystackWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        signature = request.headers.get("X-Paystack-Signature", "")
        payload = request.body

        gateway = PaystackGateway()
        if not gateway.verify_webhook(payload, signature):
            return APIResponse.error(
                message="Invalid webhook signature.",
                status_code=400,
            )

        try:
            event = json.loads(payload)
        except Exception:
            return APIResponse.error(message="Invalid payload.", status_code=400)

        event_type = event.get("event")
        data = event.get("data", {})

        try:
            self._handle_event(event_type, data)
        except Exception:
            logger.exception("Error handling Paystack event %s", event_type)

        return APIResponse.success(message="Webhook received.")

    def _handle_event(self, event_type, data):
        user_id = data.get("metadata", {}).get("user_id")

        if event_type == "charge.success":
            self._handle_charge_success(data, user_id)
        elif event_type == "subscription.disable":
            self._handle_subscription_disable(data, user_id)
        elif event_type == "invoice.payment_failed":
            self._handle_payment_failed(data, user_id)

    def _handle_charge_success(self, data, user_id):
        if not user_id:
            return
        try:
            sub = Subscription.objects.select_related("plan").get(user_id=user_id)
        except Subscription.DoesNotExist:
            return

        now = timezone.now()
        sub.activate(
            period_start=now,
            period_end=now + timedelta(days=30),
            provider=Subscription.Provider.PAYSTACK,
            provider_subscription_id=data.get("reference", ""),
        )
        PaymentRecord.objects.get_or_create(
            provider_reference=data.get("reference", ""),
            defaults={
                "subscription": sub,
                "amount": data.get("amount", 0) / 100,
                "currency": data.get("currency", "NGN"),
                "status": PaymentRecord.Status.SUCCESS,
                "provider": "paystack",
                "provider_response": data,
                "paid_at": now,
            },
        )

    def _handle_subscription_disable(self, data, user_id):
        if not user_id:
            return
        try:
            sub = Subscription.objects.select_related("plan").get(user_id=user_id)
            sub.enter_grace_period()
        except Subscription.DoesNotExist:
            pass

    def _handle_payment_failed(self, data, user_id):
        if not user_id:
            return
        try:
            sub = Subscription.objects.select_related("plan").get(user_id=user_id)
            if sub.status == Subscription.Status.ACTIVE:
                sub.enter_grace_period()
        except Subscription.DoesNotExist:
            pass


# ---------------------------------------------------------------------------
# Stripe webhook
# ---------------------------------------------------------------------------
@extend_schema(
    summary="Stripe webhook receiver",
    description=(
        "Receives and processes Stripe webhook events. "
        "Verifies the Stripe-Signature header before handling. "
        "Handles: checkout.session.completed, invoice.payment_succeeded, "
        "invoice.payment_failed, customer.subscription.deleted. "
        "This endpoint is called by Stripe servers — do not call it directly."
    ),
    responses={
        200: OpenApiResponse(description="Webhook received and queued for processing"),
        400: OpenApiResponse(description="Invalid signature or malformed payload"),
    },
    tags=["Subscriptions"],
    auth=[],
    exclude=True,
)
class StripeWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        payload = request.body
        sig_header = request.headers.get("Stripe-Signature", "")

        gateway = StripeGateway()
        try:
            event = gateway.verify_webhook(payload, sig_header)
        except Exception:
            return APIResponse.error(
                message="Invalid webhook signature.",
                status_code=400,
            )

        try:
            self._handle_event(event)
        except Exception:
            logger.exception("Error handling Stripe event %s", event.get("type"))

        return APIResponse.success(message="Webhook received.")

    def _handle_event(self, event):
        event_type = event.get("type")
        obj = event.get("data", {}).get("object", {})
        user_id = obj.get("metadata", {}).get("user_id")

        if event_type == "checkout.session.completed":
            self._handle_checkout_completed(obj, user_id)
        elif event_type == "invoice.payment_succeeded":
            self._handle_payment_succeeded(obj, user_id)
        elif event_type == "invoice.payment_failed":
            self._handle_payment_failed(obj, user_id)
        elif event_type == "customer.subscription.deleted":
            self._handle_subscription_deleted(obj, user_id)

    def _handle_checkout_completed(self, obj, user_id):
        if not user_id:
            return
        try:
            sub = Subscription.objects.select_related("plan").get(user_id=user_id)
        except Subscription.DoesNotExist:
            return

        now = timezone.now()
        sub.activate(
            period_start=now,
            period_end=now + timedelta(days=30),
            provider=Subscription.Provider.STRIPE,
            provider_subscription_id=obj.get("subscription", ""),
        )
        if obj.get("customer"):
            sub.provider_customer_id = obj["customer"]
            sub.save(update_fields=["provider_customer_id"])

    def _handle_payment_succeeded(self, obj, user_id):
        if not user_id:
            return
        try:
            sub = Subscription.objects.get(user_id=user_id)
            PaymentRecord.objects.get_or_create(
                provider_reference=obj.get("id", ""),
                defaults={
                    "subscription": sub,
                    "amount": obj.get("amount_paid", 0) / 100,
                    "currency": obj.get("currency", "USD").upper(),
                    "status": PaymentRecord.Status.SUCCESS,
                    "provider": "stripe",
                    "provider_response": obj,
                    "paid_at": timezone.now(),
                },
            )
        except Subscription.DoesNotExist:
            pass

    def _handle_payment_failed(self, obj, user_id):
        if not user_id:
            return
        try:
            sub = Subscription.objects.select_related("plan").get(user_id=user_id)
            if sub.status == Subscription.Status.ACTIVE:
                sub.enter_grace_period()
        except Subscription.DoesNotExist:
            pass

    def _handle_subscription_deleted(self, obj, user_id):
        if not user_id:
            return
        try:
            sub = Subscription.objects.get(user_id=user_id)
            sub.lock()
        except Subscription.DoesNotExist:
            pass


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------
@extend_schema(
    summary="Cancel subscription",
    description=(
        "Cancel the current subscription for the authenticated trainer or gym. "
        "Sets status to 'cancelled' and records the cancellation timestamp. "
        "Access is retained until the end of the current billing period."
    ),
    request=inline_serializer(name="CancelSubscriptionRequest", fields={}),
    responses={
        200: OpenApiResponse(
            description="Subscription cancelled — returns cancelled_at timestamp"
        ),
        401: OpenApiResponse(description="Not authenticated"),
        403: OpenApiResponse(description="Only trainer and gym accounts can cancel"),
        404: OpenApiResponse(description="No active subscription found"),
    },
    tags=["Subscriptions"],
)
class CancelSubscriptionView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    def post(self, request):
        try:
            sub = request.user.subscription
        except Subscription.DoesNotExist:
            return APIResponse.error(
                message="No active subscription found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        sub.cancel()
        return APIResponse.success(
            data={"cancelled_at": sub.cancelled_at},
            message="Subscription cancelled successfully.",
        )


# ---------------------------------------------------------------------------
# Billing history
# ---------------------------------------------------------------------------
@extend_schema(
    summary="Billing history",
    description=(
        "Returns a paginated list of payment records for the authenticated trainer "
        "or gym. Each record includes amount, currency, provider, status, paid_at. "
        "Returns an empty list if no subscription or payments exist."
    ),
    responses={
        200: OpenApiResponse(
            description="Paginated payment record list (empty list if no history)"
        ),
        401: OpenApiResponse(description="Not authenticated"),
        403: OpenApiResponse(
            description="Only trainer and gym accounts have billing history"
        ),
    },
    tags=["Subscriptions"],
)
class BillingHistoryView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    def get(self, request):
        try:
            sub = request.user.subscription
        except Subscription.DoesNotExist:
            return APIResponse.success(data=[], message="No billing history.")

        records = PaymentRecord.objects.filter(subscription=sub)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(records, request)
        serializer = PaymentRecordSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
