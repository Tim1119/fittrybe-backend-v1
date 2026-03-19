"""
Tests for accounts Celery tasks.
"""

from unittest.mock import patch

import pytest
from celery.exceptions import MaxRetriesExceededError, Retry

from apps.accounts.tasks import (
    send_password_reset_email_task,
    send_verification_email_task,
)
from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestSendVerificationEmailTask:
    def test_sends_verification_email(self, mailoutbox):
        user = UserFactory()
        send_verification_email_task(str(user.id))
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == [user.email]

    def test_missing_user_does_not_raise(self):
        send_verification_email_task("00000000-0000-0000-0000-000000000000")

    def test_retries_on_email_failure(self):
        user = UserFactory()
        with patch(
            "apps.accounts.emails.send_verification_email",
            side_effect=Exception("SMTP error"),
        ):
            with pytest.raises((Retry, MaxRetriesExceededError)):
                send_verification_email_task.apply(
                    args=[str(user.id)], throw=True
                ).get()


@pytest.mark.django_db
class TestSendPasswordResetEmailTask:
    def test_sends_password_reset_email(self, mailoutbox):
        user = UserFactory()
        send_password_reset_email_task(str(user.id))
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == [user.email]

    def test_missing_user_does_not_raise(self):
        send_password_reset_email_task("00000000-0000-0000-0000-000000000000")

    def test_retries_on_email_failure(self):
        user = UserFactory()
        with patch(
            "apps.accounts.emails.send_password_reset_email",
            side_effect=Exception("SMTP error"),
        ):
            with pytest.raises((Retry, MaxRetriesExceededError)):
                send_password_reset_email_task.apply(
                    args=[str(user.id)], throw=True
                ).get()
