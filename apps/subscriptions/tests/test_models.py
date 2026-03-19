"""
Tests for subscription models.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.subscriptions.models import PlanConfig, Subscription
from apps.subscriptions.tests.factories import (
    ActiveSubscriptionFactory,
    BasicPlanFactory,
    PaymentRecordFactory,
    ProPlanFactory,
    SubscriptionFactory,
)


@pytest.mark.django_db
class TestPlanConfig:
    def test_get_for_role_trainer_returns_basic(self):
        BasicPlanFactory()
        result = PlanConfig.get_for_role("trainer")
        assert result.plan == PlanConfig.Plan.BASIC

    def test_get_for_role_gym_returns_pro(self):
        ProPlanFactory()
        result = PlanConfig.get_for_role("gym")
        assert result.plan == PlanConfig.Plan.PRO

    def test_str_contains_name_and_price(self):
        plan = BasicPlanFactory()
        assert "Basic" in str(plan)
        assert "5000" in str(plan)


@pytest.mark.django_db
class TestSubscriptionModel:
    def test_is_trial_active_during_trial(self):
        sub = SubscriptionFactory(
            status=Subscription.Status.TRIAL,
            trial_end=timezone.now() + timedelta(days=7),
        )
        assert sub.is_trial_active() is True

    def test_is_trial_active_false_after_trial_ends(self):
        sub = SubscriptionFactory(
            status=Subscription.Status.TRIAL,
            trial_end=timezone.now() - timedelta(seconds=1),
        )
        assert sub.is_trial_active() is False

    def test_is_trial_active_false_when_status_not_trial(self):
        sub = ActiveSubscriptionFactory()
        assert sub.is_trial_active() is False

    def test_is_access_allowed_true_for_trial(self):
        sub = SubscriptionFactory(status=Subscription.Status.TRIAL)
        assert sub.is_access_allowed() is True

    def test_is_access_allowed_true_for_active(self):
        sub = ActiveSubscriptionFactory()
        assert sub.is_access_allowed() is True

    def test_is_access_allowed_true_for_grace(self):
        sub = SubscriptionFactory(
            status=Subscription.Status.GRACE,
            trial_end=timezone.now() - timedelta(days=1),
        )
        assert sub.is_access_allowed() is True

    def test_is_access_allowed_false_for_locked(self):
        sub = SubscriptionFactory(
            status=Subscription.Status.LOCKED,
            trial_end=timezone.now() - timedelta(days=1),
        )
        assert sub.is_access_allowed() is False

    def test_is_access_allowed_false_for_cancelled(self):
        sub = SubscriptionFactory(
            status=Subscription.Status.CANCELLED,
            trial_end=timezone.now() - timedelta(days=1),
        )
        assert sub.is_access_allowed() is False

    def test_days_remaining_in_trial_returns_correct_count(self):
        sub = SubscriptionFactory(
            status=Subscription.Status.TRIAL,
            trial_end=timezone.now() + timedelta(days=10, hours=1),
        )
        assert sub.days_remaining_in_trial() == 10

    def test_days_remaining_returns_zero_when_not_trial(self):
        sub = ActiveSubscriptionFactory()
        assert sub.days_remaining_in_trial() == 0

    def test_activate_updates_status_and_provider(self):
        sub = SubscriptionFactory()
        now = timezone.now()
        period_end = now + timedelta(days=30)
        sub.activate(now, period_end, Subscription.Provider.PAYSTACK, "sub_abc123")
        sub.refresh_from_db()
        assert sub.status == Subscription.Status.ACTIVE
        assert sub.provider == Subscription.Provider.PAYSTACK
        assert sub.provider_subscription_id == "sub_abc123"
        assert sub.grace_period_end is None

    def test_enter_grace_period_sets_grace_period_end(self):
        plan = BasicPlanFactory()
        sub = SubscriptionFactory(plan=plan)
        sub.enter_grace_period()
        sub.refresh_from_db()
        assert sub.status == Subscription.Status.GRACE
        assert sub.grace_period_end is not None
        expected_end = timezone.now() + timedelta(days=plan.grace_period_days)
        assert abs((sub.grace_period_end - expected_end).total_seconds()) < 5

    def test_lock_sets_status_to_locked(self):
        sub = SubscriptionFactory()
        sub.lock()
        sub.refresh_from_db()
        assert sub.status == Subscription.Status.LOCKED

    def test_cancel_sets_status_and_cancelled_at(self):
        sub = ActiveSubscriptionFactory()
        sub.cancel()
        sub.refresh_from_db()
        assert sub.status == Subscription.Status.CANCELLED
        assert sub.cancelled_at is not None

    def test_str_contains_email_and_status(self):
        sub = SubscriptionFactory()
        s = str(sub)
        assert sub.user.email in s
        assert "trial" in s


@pytest.mark.django_db
class TestPaymentRecord:
    def test_str_contains_email_and_amount(self):
        record = PaymentRecordFactory()
        s = str(record)
        assert record.subscription.user.email in s
        assert "NGN" in s
