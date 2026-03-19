"""
Factories for subscription tests.
"""

from datetime import timedelta

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import GymFactory, TrainerFactory
from apps.subscriptions.models import PaymentRecord, PlanConfig, Subscription


class BasicPlanFactory(DjangoModelFactory):
    class Meta:
        model = PlanConfig
        django_get_or_create = ("plan",)

    plan = PlanConfig.Plan.BASIC
    display_name = "Basic"
    description = "For individual fitness trainers"
    price_ngn = "5000.00"
    price_usd = "5.00"
    trial_days = 14
    grace_period_days = 7
    is_active = True
    features = ["1 trainer profile", "marketplace", "basic analytics"]


class ProPlanFactory(DjangoModelFactory):
    class Meta:
        model = PlanConfig
        django_get_or_create = ("plan",)

    plan = PlanConfig.Plan.PRO
    display_name = "Pro"
    description = "For gyms and fitness centres"
    price_ngn = "12000.00"
    price_usd = "12.00"
    trial_days = 14
    grace_period_days = 7
    is_active = True
    features = ["gym profile", "up to 3 admin logins", "multi-trainer analytics"]


class SubscriptionFactory(DjangoModelFactory):
    class Meta:
        model = Subscription

    user = factory.SubFactory(TrainerFactory)
    plan = factory.SubFactory(BasicPlanFactory)
    status = Subscription.Status.TRIAL
    trial_end = factory.LazyFunction(lambda: timezone.now() + timedelta(days=14))


class ActiveSubscriptionFactory(SubscriptionFactory):
    status = Subscription.Status.ACTIVE
    current_period_start = factory.LazyFunction(timezone.now)
    current_period_end = factory.LazyFunction(
        lambda: timezone.now() + timedelta(days=30)
    )
    provider = Subscription.Provider.PAYSTACK
    provider_subscription_id = "sub_test_123"


class GymSubscriptionFactory(SubscriptionFactory):
    user = factory.SubFactory(GymFactory)
    plan = factory.SubFactory(ProPlanFactory)


class PaymentRecordFactory(DjangoModelFactory):
    class Meta:
        model = PaymentRecord

    subscription = factory.SubFactory(SubscriptionFactory)
    amount = "15000.00"
    currency = "NGN"
    status = PaymentRecord.Status.SUCCESS
    provider = "paystack"
    provider_reference = factory.Sequence(lambda n: f"ref_{n:08d}")
    provider_response = {}
    paid_at = factory.LazyFunction(timezone.now)
