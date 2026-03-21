"""
Subscription models — Fit Trybe billing system.
"""

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class PlanConfig(BaseModel):
    class Plan(models.TextChoices):
        BASIC = "basic", "Basic"
        PRO = "pro", "Pro"

    plan = models.CharField(
        max_length=10, choices=Plan.choices, unique=True, db_index=True
    )
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price_ngn = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Price in Nigerian Naira"
    )
    price_usd = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Price in US Dollars"
    )
    trial_days = models.PositiveIntegerField(default=14)
    grace_period_days = models.PositiveIntegerField(default=7)
    is_active = models.BooleanField(default=True)
    features = models.JSONField(default=list)
    paystack_plan_code = models.CharField(
        max_length=100,
        blank=True,
        help_text=(
            "Create a plan in Paystack Dashboard → Products → Plans. "
            "Monthly amount should match price_ngn. "
            "Copy the plan code (PLN_xxxxxxxx) here."
        ),
    )
    stripe_price_id = models.CharField(
        max_length=100,
        blank=True,
        help_text=(
            "Create a price in Stripe Dashboard → Products → Prices. "
            "Copy the price ID (price_xxxxxxxx) here."
        ),
    )

    class Meta:
        ordering = ["plan"]

    def __str__(self):
        return f"{self.display_name} - NGN {self.price_ngn}"

    @classmethod
    def get_for_role(cls, role):
        plan = "pro" if role == "gym" else "basic"
        return cls.objects.get(plan=plan, is_active=True)


class Subscription(BaseModel):
    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        GRACE = "grace", "Grace Period"
        LOCKED = "locked", "Locked"
        CANCELLED = "cancelled", "Cancelled"

    class Provider(models.TextChoices):
        PAYSTACK = "paystack", "Paystack"
        STRIPE = "stripe", "Stripe"
        NONE = "none", "None"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(
        PlanConfig, on_delete=models.PROTECT, related_name="subscriptions"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TRIAL,
        db_index=True,
    )
    trial_start = models.DateTimeField(auto_now_add=True)
    trial_end = models.DateTimeField()
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    grace_period_end = models.DateTimeField(null=True, blank=True)
    provider = models.CharField(
        max_length=20, choices=Provider.choices, default=Provider.NONE
    )
    provider_customer_id = models.CharField(max_length=200, blank=True)
    provider_subscription_id = models.CharField(max_length=200, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    payment_retry_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of payment failures received from Paystack/Stripe webhooks.",
    )
    last_payment_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the last payment failure notification.",
    )
    paystack_subscription_code = models.CharField(
        max_length=200,
        blank=True,
        help_text="Paystack subscription code, e.g. SUB_xxx",
    )
    paystack_email_token = models.CharField(
        max_length=200,
        blank=True,
        help_text="Used to manage subscription on Paystack",
    )
    paystack_customer_code = models.CharField(
        max_length=200,
        blank=True,
        help_text="Paystack customer code, e.g. CUS_xxx",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.plan.plan} ({self.status})"

    def is_trial_active(self):
        from django.utils import timezone

        return self.status == self.Status.TRIAL and timezone.now() < self.trial_end

    def is_access_allowed(self):
        return self.status in [
            self.Status.TRIAL,
            self.Status.ACTIVE,
            self.Status.GRACE,
        ]

    def days_remaining_in_trial(self):
        from django.utils import timezone

        if self.status != self.Status.TRIAL:
            return 0
        delta = self.trial_end - timezone.now()
        return max(0, delta.days)

    def activate(self, period_start, period_end, provider, provider_subscription_id):
        self.status = self.Status.ACTIVE
        self.current_period_start = period_start
        self.current_period_end = period_end
        self.provider = provider
        self.provider_subscription_id = provider_subscription_id
        self.grace_period_end = None
        self.save()

    def enter_grace_period(self):
        from datetime import timedelta

        from django.utils import timezone

        self.status = self.Status.GRACE
        self.grace_period_end = timezone.now() + timedelta(
            days=self.plan.grace_period_days
        )
        self.save()

    def lock(self):
        self.status = self.Status.LOCKED
        self.save()

    def cancel(self):
        from django.utils import timezone

        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.save()

    def record_payment_failure(self):
        """Increment failure count; enter grace period after 3 failures."""
        from django.utils import timezone

        self.payment_retry_count += 1
        self.last_payment_retry_at = timezone.now()
        self.save(update_fields=["payment_retry_count", "last_payment_retry_at"])
        if self.payment_retry_count >= 3:
            self.enter_grace_period()

    def reset_payment_retries(self):
        self.payment_retry_count = 0
        self.last_payment_retry_at = None
        self.save(update_fields=["payment_retry_count", "last_payment_retry_at"])


class PaymentRecord(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        PENDING = "pending", "Pending"
        REFUNDED = "refunded", "Refunded"

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="payment_records"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    provider = models.CharField(max_length=20)
    provider_reference = models.CharField(max_length=200, unique=True)
    provider_response = models.JSONField(default=dict)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.subscription.user.email} - "
            f"{self.amount} {self.currency} ({self.status})"
        )
