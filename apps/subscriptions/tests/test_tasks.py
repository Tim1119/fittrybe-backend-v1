"""Tests for subscription Celery tasks."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.subscriptions.models import Subscription
from apps.subscriptions.tasks import (
    check_active_subscription_expirations,
    check_grace_period_expirations,
    check_trial_expirations,
    process_payment_retries,
)
from apps.subscriptions.tests.factories import (
    ActiveSubscriptionFactory,
    SubscriptionFactory,
)


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

    def test_sends_grace_warning_email_directly(self):
        self._expired_trial()
        with patch("apps.subscriptions.tasks._send_grace_warning_email") as mock_send:
            check_trial_expirations()
        mock_send.assert_called_once()

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

    def test_sends_locked_email_directly_after_locking(self):
        self._expired_grace()
        with patch("apps.accounts.emails.send_subscription_locked_email") as mock_send:
            check_grace_period_expirations()
        mock_send.assert_called_once()

    def test_returns_count_of_locked_subscriptions(self):
        self._expired_grace()
        self._expired_grace()
        result = check_grace_period_expirations()
        assert result == 2


@pytest.mark.django_db
class TestCheckActiveSubscriptionExpirations:
    def _expired_active(self):
        sub = ActiveSubscriptionFactory()
        sub.current_period_end = timezone.now() - timedelta(hours=1)
        sub.save(update_fields=["current_period_end"])
        return sub

    def test_moves_expired_active_sub_to_grace(self):
        sub = self._expired_active()
        check_active_subscription_expirations()
        sub.refresh_from_db()
        assert sub.status == Subscription.Status.GRACE
        assert sub.grace_period_end is not None

    def test_ignores_active_subs_not_yet_expired(self):
        sub = ActiveSubscriptionFactory()
        check_active_subscription_expirations()
        sub.refresh_from_db()
        assert sub.status == Subscription.Status.ACTIVE

    def test_sends_grace_warning_email(self):
        self._expired_active()
        with patch("apps.subscriptions.tasks._send_grace_warning_email") as mock_send:
            check_active_subscription_expirations()
        mock_send.assert_called_once()

    def test_returns_count_of_moved_subscriptions(self):
        self._expired_active()
        self._expired_active()
        result = check_active_subscription_expirations()
        assert result == 2


@pytest.mark.django_db
class TestProcessPaymentRetries:
    def _due_retry_sub(self, retry_count=1):
        sub = ActiveSubscriptionFactory(
            payment_retry_count=retry_count,
            next_payment_retry_at=timezone.now() - timedelta(hours=1),
        )
        return sub

    def test_schedules_next_retry_for_due_subscription(self):
        sub = self._due_retry_sub(retry_count=1)
        process_payment_retries()
        sub.refresh_from_db()
        assert sub.payment_retry_count == 2

    def test_enters_grace_when_max_retries_exceeded(self):
        sub = self._due_retry_sub(retry_count=3)
        process_payment_retries()
        sub.refresh_from_db()
        assert sub.status == Subscription.Status.GRACE

    def test_ignores_subscriptions_not_yet_due(self):
        sub = ActiveSubscriptionFactory(
            payment_retry_count=1,
            next_payment_retry_at=timezone.now() + timedelta(days=2),
        )
        process_payment_retries()
        sub.refresh_from_db()
        assert sub.payment_retry_count == 1
