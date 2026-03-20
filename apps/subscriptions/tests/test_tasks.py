"""Tests for subscription Celery tasks."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.subscriptions.models import Subscription
from apps.subscriptions.tasks import (
    check_grace_period_expirations,
    check_trial_expirations,
)
from apps.subscriptions.tests.factories import SubscriptionFactory


@pytest.mark.django_db
class TestCheckTrialExpirations:
    def _expired_trial(self):
        return SubscriptionFactory(
            status=Subscription.Status.TRIAL,
            trial_end=timezone.now() - timedelta(hours=1),
        )

    def test_moves_expired_trial_to_grace(self):
        sub = self._expired_trial()
        check_trial_expirations()
        sub.refresh_from_db()
        assert sub.status == Subscription.Status.GRACE

    def test_ignores_active_trials(self):
        sub = SubscriptionFactory(
            status=Subscription.Status.TRIAL,
            trial_end=timezone.now() + timedelta(days=3),
        )
        check_trial_expirations()
        sub.refresh_from_db()
        assert sub.status == Subscription.Status.TRIAL

    def test_dispatches_grace_period_warning_email(self):
        self._expired_trial()
        with patch(
            "apps.subscriptions.tasks.send_grace_period_warning.delay"
        ) as mock_delay:
            check_trial_expirations()
        mock_delay.assert_called_once()

    def test_returns_count_of_moved_subscriptions(self):
        self._expired_trial()
        self._expired_trial()
        result = check_trial_expirations()
        assert result == 2


@pytest.mark.django_db
class TestCheckGracePeriodExpirations:
    def _expired_grace(self):
        sub = SubscriptionFactory(
            status=Subscription.Status.GRACE,
            trial_end=timezone.now() - timedelta(days=8),
        )
        sub.grace_period_end = timezone.now() - timedelta(hours=1)
        sub.save(update_fields=["grace_period_end"])
        return sub

    def test_locks_expired_grace_subscriptions(self):
        sub = self._expired_grace()
        check_grace_period_expirations()
        sub.refresh_from_db()
        assert sub.status == Subscription.Status.LOCKED

    def test_ignores_active_grace_subscriptions(self):
        sub = SubscriptionFactory(
            status=Subscription.Status.GRACE,
            trial_end=timezone.now() - timedelta(days=1),
        )
        sub.grace_period_end = timezone.now() + timedelta(days=3)
        sub.save(update_fields=["grace_period_end"])
        check_grace_period_expirations()
        sub.refresh_from_db()
        assert sub.status == Subscription.Status.GRACE

    def test_dispatches_locked_email_after_locking(self):
        self._expired_grace()
        with patch(
            "apps.subscriptions.tasks.send_subscription_locked_email.delay"
        ) as mock_delay:
            check_grace_period_expirations()
        mock_delay.assert_called_once()

    def test_returns_count_of_locked_subscriptions(self):
        self._expired_grace()
        self._expired_grace()
        result = check_grace_period_expirations()
        assert result == 2


@pytest.mark.django_db
class TestSendSubscriptionLockedEmail:
    def test_calls_send_account_locked_email(self):
        from apps.subscriptions.tasks import send_subscription_locked_email
        from apps.subscriptions.tests.factories import SubscriptionFactory

        sub = SubscriptionFactory(status=Subscription.Status.LOCKED)
        with patch("apps.accounts.emails.send_account_locked_email") as mock_email:
            send_subscription_locked_email(sub.id)
        mock_email.assert_called_once_with(sub.user)

    def test_handles_missing_subscription_gracefully(self):
        from apps.subscriptions.tasks import send_subscription_locked_email

        # Should not raise
        send_subscription_locked_email(99999)
