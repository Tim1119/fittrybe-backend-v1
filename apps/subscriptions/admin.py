"""
Subscription admin configuration.
"""

from django.contrib import admin

from apps.subscriptions.models import PaymentRecord, PlanConfig, Subscription


@admin.register(PlanConfig)
class PlanConfigAdmin(admin.ModelAdmin):
    list_display = (
        "plan",
        "display_name",
        "price_ngn",
        "price_usd",
        "trial_days",
        "is_active",
        "paystack_plan_code",
        "stripe_price_id",
    )
    list_editable = ("price_ngn", "price_usd", "is_active")
    ordering = ("plan",)
    fieldsets = (
        (
            "Plan Details",
            {
                "fields": (
                    "plan",
                    "display_name",
                    "description",
                    "price_ngn",
                    "price_usd",
                    "trial_days",
                    "grace_period_days",
                    "is_active",
                    "features",
                )
            },
        ),
        (
            "Payment Gateway Codes",
            {
                "fields": ("paystack_plan_code", "stripe_price_id"),
                "description": (
                    "Paystack: create a plan in Paystack Dashboard → Products → Plans. "
                    "Stripe: create a price in Stripe Dashboard → Products → Prices."
                ),
            },
        ),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("get_user_email", "plan", "status", "trial_end", "created_at")
    list_filter = ("status", "plan")
    search_fields = ("user__email",)
    readonly_fields = ("trial_start", "created_at", "updated_at")

    @admin.display(description="User Email")
    def get_user_email(self, obj):
        return obj.user.email


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display = (
        "get_user_email",
        "amount",
        "currency",
        "status",
        "provider",
        "paid_at",
    )
    list_filter = ("status", "provider")
    readonly_fields = (
        "subscription",
        "amount",
        "currency",
        "status",
        "provider",
        "provider_reference",
        "provider_response",
        "paid_at",
        "created_at",
    )

    @admin.display(description="User Email")
    def get_user_email(self, obj):
        return obj.subscription.user.email
