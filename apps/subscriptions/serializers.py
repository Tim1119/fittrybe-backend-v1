"""
Subscription serializers.
"""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.subscriptions.models import PaymentRecord, PlanConfig, Subscription


class PlanConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanConfig
        fields = (
            "id",
            "plan",
            "display_name",
            "description",
            "price_ngn",
            "price_usd",
            "trial_days",
            "grace_period_days",
            "features",
        )


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.display_name", read_only=True)
    plan_slug = serializers.CharField(source="plan.plan", read_only=True)
    is_trial = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    is_access_allowed = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = (
            "id",
            "status",
            "plan_name",
            "plan_slug",
            "is_trial",
            "days_remaining",
            "is_access_allowed",
            "trial_end",
            "current_period_start",
            "current_period_end",
            "grace_period_end",
            "provider",
            "cancelled_at",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_is_trial(self, obj):
        return obj.is_trial_active()

    @extend_schema_field(serializers.IntegerField())
    def get_days_remaining(self, obj):
        return obj.days_remaining_in_trial()

    @extend_schema_field(serializers.BooleanField())
    def get_is_access_allowed(self, obj):
        return obj.is_access_allowed()


class PaymentRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentRecord
        fields = (
            "id",
            "amount",
            "currency",
            "status",
            "provider",
            "provider_reference",
            "paid_at",
            "created_at",
        )
        read_only_fields = fields
