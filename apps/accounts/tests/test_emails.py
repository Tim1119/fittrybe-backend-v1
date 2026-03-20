"""
Tests for accounts email utilities.
The pytest-django `mailoutbox` fixture automatically switches to the
locmem backend, so no @override_settings is needed.
"""

import pytest

from apps.accounts.emails import (
    send_account_locked_email,
    send_password_changed_email,
    send_password_reset_email,
    send_verification_email,
    send_welcome_email,
)
from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestSendVerificationEmail:
    def test_sends_one_email(self, mailoutbox):
        user = UserFactory()
        send_verification_email(user)
        assert len(mailoutbox) == 1

    def test_subject_is_correct(self, mailoutbox):
        user = UserFactory()
        send_verification_email(user)
        assert mailoutbox[0].subject == "Verify your Fit Trybe account"

    def test_verification_url_in_body(self, mailoutbox):
        user = UserFactory()
        send_verification_email(user)
        assert "verify-email" in mailoutbox[0].body

    def test_web_url_in_body(self, mailoutbox):
        user = UserFactory()
        send_verification_email(user)
        assert "/verify-email/" in mailoutbox[0].body

    def test_mobile_deep_link_in_body(self, mailoutbox):
        user = UserFactory()
        send_verification_email(user)
        assert "fittrybe://" in mailoutbox[0].body

    def test_html_contains_web_url(self, mailoutbox):
        user = UserFactory()
        send_verification_email(user)
        html = mailoutbox[0].alternatives[0][0]
        assert "/verify-email/" in html

    def test_html_contains_mobile_url(self, mailoutbox):
        user = UserFactory()
        send_verification_email(user)
        html = mailoutbox[0].alternatives[0][0]
        assert "fittrybe://" in html

    def test_html_alternative_attached(self, mailoutbox):
        user = UserFactory()
        send_verification_email(user)
        alternatives = mailoutbox[0].alternatives
        assert len(alternatives) == 1
        assert alternatives[0][1] == "text/html"

    def test_sent_to_user_email(self, mailoutbox):
        user = UserFactory(email="verify@test.com")
        send_verification_email(user)
        assert mailoutbox[0].to == ["verify@test.com"]


@pytest.mark.django_db
class TestSendPasswordResetEmail:
    def test_sends_one_email(self, mailoutbox):
        user = UserFactory()
        send_password_reset_email(user)
        assert len(mailoutbox) == 1

    def test_reset_url_in_body(self, mailoutbox):
        user = UserFactory()
        send_password_reset_email(user)
        assert "reset-password" in mailoutbox[0].body

    def test_web_url_in_body(self, mailoutbox):
        user = UserFactory()
        send_password_reset_email(user)
        assert "/reset-password/" in mailoutbox[0].body

    def test_mobile_deep_link_in_body(self, mailoutbox):
        user = UserFactory()
        send_password_reset_email(user)
        assert "fittrybe://" in mailoutbox[0].body

    def test_html_contains_web_url(self, mailoutbox):
        user = UserFactory()
        send_password_reset_email(user)
        html = mailoutbox[0].alternatives[0][0]
        assert "/reset-password/" in html

    def test_html_contains_mobile_url(self, mailoutbox):
        user = UserFactory()
        send_password_reset_email(user)
        html = mailoutbox[0].alternatives[0][0]
        assert "fittrybe://" in html

    def test_subject_is_correct(self, mailoutbox):
        user = UserFactory()
        send_password_reset_email(user)
        assert mailoutbox[0].subject == "Reset your Fit Trybe password"


@pytest.mark.django_db
class TestSendWelcomeEmail:
    def test_sends_one_email(self, mailoutbox):
        user = UserFactory()
        send_welcome_email(user)
        assert len(mailoutbox) == 1

    def test_subject_contains_welcome(self, mailoutbox):
        user = UserFactory()
        send_welcome_email(user)
        assert "Welcome" in mailoutbox[0].subject

    def test_html_contains_mobile_url(self, mailoutbox):
        user = UserFactory()
        send_welcome_email(user)
        html = mailoutbox[0].alternatives[0][0]
        assert "fittrybe://" in html

    def test_html_contains_web_url(self, mailoutbox):
        user = UserFactory()
        send_welcome_email(user)
        html = mailoutbox[0].alternatives[0][0]
        assert "http://localhost:3000" in html


@pytest.mark.django_db
class TestSendAccountLockedEmail:
    def test_sends_one_email(self, mailoutbox):
        user = UserFactory()
        send_account_locked_email(user)
        assert len(mailoutbox) == 1

    def test_subject_mentions_locked(self, mailoutbox):
        user = UserFactory()
        send_account_locked_email(user)
        assert "Locked" in mailoutbox[0].subject

    def test_web_reset_url_in_body(self, mailoutbox):
        user = UserFactory()
        send_account_locked_email(user)
        assert "/reset-password/" in mailoutbox[0].body

    def test_mobile_deep_link_in_body(self, mailoutbox):
        user = UserFactory()
        send_account_locked_email(user)
        assert "fittrybe://" in mailoutbox[0].body

    def test_html_contains_mobile_url(self, mailoutbox):
        user = UserFactory()
        send_account_locked_email(user)
        html = mailoutbox[0].alternatives[0][0]
        assert "fittrybe://" in html


@pytest.mark.django_db
class TestSendPasswordChangedEmail:
    def test_sends_one_email(self, mailoutbox):
        user = UserFactory()
        send_password_changed_email(user)
        assert len(mailoutbox) == 1

    def test_subject_mentions_password_changed(self, mailoutbox):
        user = UserFactory()
        send_password_changed_email(user)
        assert "Password Changed" in mailoutbox[0].subject

    def test_web_reset_url_in_body(self, mailoutbox):
        user = UserFactory()
        send_password_changed_email(user)
        assert "/reset-password/" in mailoutbox[0].body

    def test_mobile_deep_link_in_body(self, mailoutbox):
        user = UserFactory()
        send_password_changed_email(user)
        assert "fittrybe://" in mailoutbox[0].body

    def test_html_contains_mobile_url(self, mailoutbox):
        user = UserFactory()
        send_password_changed_email(user)
        html = mailoutbox[0].alternatives[0][0]
        assert "fittrybe://" in html
