"""
Tests for accounts views (auth endpoints).
"""

import pytest
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.emails import account_token_generator
from apps.accounts.tests.factories import UnverifiedUserFactory, UserFactory

STRONG = "F1tTryb3!#2025"


def make_uid_token(user, generator=None):
    g = generator or account_token_generator
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = g.make_token(user)
    return uid, token


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client(api_client):
    user = UserFactory()
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    api_client._user = user
    return api_client


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestRegisterView:
    URL = "/api/v1/auth/register/"

    def _payload(self, **kw):
        role = kw.get("role", "trainer")
        defaults = {
            "email": "new@example.com",
            "password": STRONG,
            "confirm_password": STRONG,
            "role": role,
            "display_name": "Test User",
            "terms_accepted": True,
        }
        if role == "trainer":
            defaults["full_name"] = "Test Trainer Full"
        elif role == "gym":
            defaults["gym_name"] = "Test Gym"
            defaults["admin_full_name"] = "Admin User"
        defaults.update(kw)
        return defaults

    def test_register_trainer_returns_201(self, api_client):
        resp = api_client.post(self.URL, self._payload(), format="json")
        assert resp.status_code == status.HTTP_201_CREATED

    def test_register_gym_returns_201(self, api_client):
        resp = api_client.post(
            self.URL,
            self._payload(
                email="gym@example.com",
                role="gym",
                gym_name="Fit Gym",
                admin_full_name="Gym Admin",
            ),
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_register_client_returns_201(self, api_client):
        resp = api_client.post(
            self.URL,
            self._payload(email="client@example.com", role="client"),
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_trainer_missing_full_name_returns_400(self, api_client):
        payload = self._payload()
        payload.pop("full_name")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_gym_missing_gym_name_returns_400(self, api_client):
        payload = self._payload(email="gymx@example.com", role="gym")
        payload.pop("gym_name")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_duplicate_email_returns_400(self, api_client):
        UserFactory(email="dup@example.com")
        resp = api_client.post(
            self.URL, self._payload(email="dup@example.com"), format="json"
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_weak_password_returns_400(self, api_client):
        resp = api_client.post(
            self.URL,
            self._payload(password="aaaaaaaa", confirm_password="aaaaaaaa"),
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_sends_email(self, api_client, mailoutbox):
        api_client.post(self.URL, self._payload(), format="json")
        assert len(mailoutbox) == 1
        assert "Verify" in mailoutbox[0].subject

    # --- terms_accepted validation ---

    def test_missing_terms_accepted_returns_400(self, api_client):
        payload = self._payload()
        payload.pop("terms_accepted")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_terms_accepted_false_returns_400(self, api_client):
        resp = api_client.post(
            self.URL, self._payload(terms_accepted=False), format="json"
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_gym_missing_terms_accepted_returns_400(self, api_client):
        payload = self._payload(
            email="gym2@example.com",
            role="gym",
            gym_name="Gym 2",
            admin_full_name="Admin",
        )
        payload.pop("terms_accepted")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_client_missing_terms_accepted_returns_400(self, api_client):
        payload = self._payload(email="client2@example.com", role="client")
        payload.pop("terms_accepted")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # --- display_name and terms_accepted_at persistence ---

    def test_display_name_saved_on_trainer(self, api_client):
        from apps.accounts.models import User

        resp = api_client.post(
            self.URL,
            self._payload(display_name="Jane Trainer", full_name="Jane Full Name"),
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        user = User.objects.get(email="new@example.com")
        assert user.display_name == "Jane Trainer"

    def test_terms_accepted_at_set_on_trainer(self, api_client):
        from apps.accounts.models import User

        api_client.post(self.URL, self._payload(), format="json")
        user = User.objects.get(email="new@example.com")
        assert user.terms_accepted_at is not None

    def test_display_name_saved_on_client(self, api_client):
        from apps.accounts.models import User

        resp = api_client.post(
            self.URL,
            self._payload(
                email="clientdn@example.com", role="client", display_name="Joe Client"
            ),
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        user = User.objects.get(email="clientdn@example.com")
        assert user.display_name == "Joe Client"

    def test_terms_accepted_at_set_on_gym(self, api_client):
        from apps.accounts.models import User

        api_client.post(
            self.URL,
            self._payload(email="gym3@example.com", role="gym"),
            format="json",
        )
        user = User.objects.get(email="gym3@example.com")
        assert user.terms_accepted_at is not None


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestVerifyEmailView:
    URL = "/api/v1/auth/verify-email/"

    def test_valid_uid_and_token_returns_200(self, api_client):
        user = UnverifiedUserFactory()
        uid, token = make_uid_token(user)
        resp = api_client.get(self.URL, {"uid": uid, "token": token})
        assert resp.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.is_active is True
        assert user.is_email_verified is True

    def test_invalid_token_returns_400(self, api_client):
        user = UnverifiedUserFactory()
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        resp = api_client.get(self.URL, {"uid": uid, "token": "badtoken"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_uid_returns_400(self, api_client):
        resp = api_client.get(self.URL, {"uid": "notbase64!!", "token": "abc"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestLoginView:
    URL = "/api/v1/auth/login/"

    def test_unverified_user_returns_403(self, api_client):
        user = UnverifiedUserFactory()
        user.set_password("StrongPass123!")
        user.save()
        resp = api_client.post(
            self.URL,
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_valid_credentials_returns_200_with_tokens(self, api_client):
        user = UserFactory()
        resp = api_client.post(
            self.URL,
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.data["data"]
        assert "refresh" in resp.data["data"]
        assert resp.data["data"]["email"] == user.email

    def test_login_response_includes_onboarding_data(self, api_client):
        user = UserFactory()
        resp = api_client.post(
            self.URL,
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        onboarding = resp.data["data"]["onboarding"]
        assert "status" in onboarding
        assert "is_completed" in onboarding
        assert "is_first_login" in onboarding
        assert "wizard_step" in onboarding
        assert "profile_completion_percentage" in onboarding

    def test_login_onboarding_wizard_step_defaults_to_zero(self, api_client):
        user = UserFactory()
        resp = api_client.post(
            self.URL,
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        assert resp.data["data"]["onboarding"]["wizard_step"] == 0
        assert resp.data["data"]["onboarding"]["profile_completion_percentage"] == 0

    def test_is_first_login_set_to_false_after_first_login(self, api_client):
        user = UserFactory()
        assert user.is_first_login is True
        api_client.post(
            self.URL,
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        user.refresh_from_db()
        assert user.is_first_login is False

    def test_is_first_login_true_in_first_login_response(self, api_client):
        user = UserFactory()
        resp = api_client.post(
            self.URL,
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        assert resp.data["data"]["onboarding"]["is_first_login"] is True

    def test_wrong_password_returns_401(self, api_client):
        user = UserFactory()
        resp = api_client.post(
            self.URL,
            {"email": user.email, "password": "wrongpassword"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_locked_after_three_failed_attempts_returns_429(self, api_client):
        user = UserFactory()
        for _ in range(3):
            api_client.post(
                self.URL,
                {"email": user.email, "password": "WrongPassword!"},
                format="json",
            )
        resp = api_client.post(
            self.URL,
            {"email": user.email, "password": "WrongPassword!"},
            format="json",
        )
        assert resp.status_code == 429
        assert resp.data["code"] == "ACCOUNT_LOCKED"

    def test_login_succeeds_after_axes_reset(self, api_client):
        from axes.models import AccessAttempt

        user = UserFactory()
        for _ in range(3):
            api_client.post(
                self.URL,
                {"email": user.email, "password": "WrongPassword!"},
                format="json",
            )
        AccessAttempt.objects.all().delete()
        resp = api_client.post(
            self.URL,
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestLogoutView:
    URL = "/api/v1/auth/logout/"

    def test_valid_refresh_returns_200(self, auth_client):
        user = auth_client._user
        refresh = str(RefreshToken.for_user(user))
        resp = auth_client.post(self.URL, {"refresh": refresh}, format="json")
        assert resp.status_code == status.HTTP_200_OK

    def test_missing_refresh_returns_400(self, auth_client):
        resp = auth_client.post(self.URL, {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.post(self.URL, {"refresh": "sometoken"}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Forgot password
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestForgotPasswordView:
    URL = "/api/v1/auth/forgot-password/"

    def test_existing_email_returns_200(self, api_client):
        user = UserFactory()
        resp = api_client.post(self.URL, {"email": user.email}, format="json")
        assert resp.status_code == status.HTTP_200_OK

    def test_non_existing_email_returns_200(self, api_client):
        resp = api_client.post(self.URL, {"email": "ghost@nowhere.com"}, format="json")
        assert resp.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# Reset password
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestResetPasswordView:
    URL = "/api/v1/auth/reset-password/"

    def test_valid_token_returns_200(self, api_client):
        user = UserFactory()
        gen = PasswordResetTokenGenerator()
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = gen.make_token(user)
        resp = api_client.post(
            self.URL,
            {
                "uid": uid,
                "token": token,
                "new_password": STRONG,
                "confirm_password": STRONG,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_invalid_token_returns_400(self, api_client):
        user = UserFactory()
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        resp = api_client.post(
            self.URL,
            {
                "uid": uid,
                "token": "invalidtoken",
                "new_password": STRONG,
                "confirm_password": STRONG,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestChangePasswordView:
    URL = "/api/v1/auth/change-password/"

    def test_correct_old_password_returns_200(self, auth_client):
        resp = auth_client.post(
            self.URL,
            {
                "old_password": "StrongPass123!",
                "new_password": STRONG,
                "confirm_password": STRONG,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_wrong_old_password_returns_400(self, auth_client):
        resp = auth_client.post(
            self.URL,
            {
                "old_password": "WrongPassword!",
                "new_password": STRONG,
                "confirm_password": STRONG,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Me
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestMeView:
    URL = "/api/v1/auth/me/"

    def test_authenticated_returns_200_with_user_data(self, auth_client):
        resp = auth_client.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        assert "email" in resp.data["data"]
        assert "role" in resp.data["data"]

    def test_me_response_includes_onboarding_data(self, auth_client):
        resp = auth_client.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        onboarding = resp.data["data"]["onboarding"]
        assert "status" in onboarding
        assert "is_completed" in onboarding
        assert "is_first_login" in onboarding
        assert "wizard_step" in onboarding
        assert "profile_completion_percentage" in onboarding

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(self.URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestCompleteOnboardingView:
    URL = "/api/v1/auth/onboarding/complete/"

    def test_completes_onboarding(self, auth_client):
        resp = auth_client.post(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        auth_client._user.refresh_from_db()
        assert auth_client._user.onboarding_status == "completed"

    def test_returns_success_message(self, auth_client):
        resp = auth_client.post(self.URL)
        assert resp.data["message"] == "Onboarding completed."

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.post(self.URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_idempotent_if_already_completed(self, auth_client):
        auth_client.post(self.URL)
        resp = auth_client.post(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        auth_client._user.refresh_from_db()
        assert auth_client._user.onboarding_status == "completed"
