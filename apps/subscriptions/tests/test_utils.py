"""
Tests for subscription utility functions.
"""

import pytest

from apps.accounts.tests.factories import GymFactory, TrainerFactory
from apps.subscriptions.models import Subscription
from apps.subscriptions.tests.factories import BasicPlanFactory, ProPlanFactory
from apps.subscriptions.utils import create_trial_subscription


@pytest.mark.django_db
class TestCreateTrialSubscription:
    def test_creates_trial_for_trainer(self):
        user = TrainerFactory()
        BasicPlanFactory()
        sub = create_trial_subscription(user)
        assert sub.status == Subscription.Status.TRIAL
        assert sub.plan.plan == "basic"

    def test_creates_trial_for_gym(self):
        user = GymFactory()
        ProPlanFactory()
        sub = create_trial_subscription(user)
        assert sub.status == Subscription.Status.TRIAL
        assert sub.plan.plan == "pro"

    def test_idempotent_returns_existing_subscription(self):
        user = TrainerFactory()
        BasicPlanFactory()
        sub1 = create_trial_subscription(user)
        sub2 = create_trial_subscription(user)
        assert sub1.id == sub2.id

    def test_trial_end_set_from_plan_trial_days(self):
        from django.utils import timezone

        user = TrainerFactory()
        BasicPlanFactory()
        sub = create_trial_subscription(user)
        # trial_end should be ~14 days from now
        delta = sub.trial_end - timezone.now()
        assert 13 <= delta.days <= 14
