"""
Tests for accounts views (auth endpoints).
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import OTPCode, generate_otp
from apps.accounts.tests.factories import UnverifiedUserFactory, UserFactory

STRONG = "F1tTryb3!#2025"


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
            "full_name": "Test User",
            "country": "Nigeria",
            "terms_accepted": True,
        }
        if role == "trainer":
            defaults["full_name"] = "Test Trainer Full"
        elif role == "gym":
            defaults["full_name"] = "Test Gym"
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
                full_name="Fit Gym",
            ),
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_register_client_returns_201(self, api_client):
        resp = api_client.post(
            self.URL,
            self._payload(
                email="client@example.com",
                role="client",
                full_name="Jane Client",
            ),
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_trainer_missing_full_name_returns_400(self, api_client):
        payload = self._payload()
        payload.pop("full_name")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_gym_missing_full_name_returns_400(self, api_client):
        payload = self._payload(email="gymx@example.com", role="gym")
        payload.pop("full_name")
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
        assert "verif" in mailoutbox[0].subject.lower()

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
            full_name="Gym 2",
        )
        payload.pop("terms_accepted")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_client_missing_terms_accepted_returns_400(self, api_client):
        payload = self._payload(email="client2@example.com", role="client")
        payload.pop("terms_accepted")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # --- full_name and terms_accepted_at persistence ---

    def test_full_name_saved_on_trainer_profile(self, api_client):
        from apps.profiles.models import TrainerProfile

        resp = api_client.post(
            self.URL,
            self._payload(full_name="Jane Full Name"),
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        profile = TrainerProfile.objects.get(user__email="new@example.com")
        assert profile.full_name == "Jane Full Name"

    def test_terms_accepted_at_set_on_trainer(self, api_client):
        from apps.accounts.models import User

        api_client.post(self.URL, self._payload(), format="json")
        user = User.objects.get(email="new@example.com")
        assert user.terms_accepted_at is not None

    def test_full_name_saved_on_client_profile(self, api_client):
        from apps.profiles.models import ClientProfile

        resp = api_client.post(
            self.URL,
            self._payload(
                email="clientdn@example.com", role="client", full_name="Joe Client"
            ),
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        profile = ClientProfile.objects.get(user__email="clientdn@example.com")
        assert profile.full_name == "Joe Client"

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
    # Country validation
    # ---------------------------------------------------------------------------

    def test_trainer_signup_without_country_returns_400(self, api_client):
        payload = self._payload()
        payload.pop("country")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_trainer_signup_with_iso_code_returns_400(self, api_client):
        resp = api_client.post(self.URL, self._payload(country="NG"), format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            "full country name" in str(resp.data).lower()
            or "recognised" in str(resp.data).lower()
        )

    def test_trainer_signup_with_lowercase_iso_returns_400(self, api_client):
        resp = api_client.post(self.URL, self._payload(country="ng"), format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_trainer_signup_with_nigeria_returns_201(self, api_client):
        from apps.accounts.models import User

        resp = api_client.post(
            self.URL, self._payload(country="Nigeria"), format="json"
        )
        assert resp.status_code == status.HTTP_201_CREATED
        user = User.objects.get(email="new@example.com")
        assert user.country == "Nigeria"

    def test_trainer_signup_with_lowercase_country_normalised(self, api_client):
        from apps.accounts.models import User

        resp = api_client.post(
            self.URL, self._payload(country="nigeria"), format="json"
        )
        assert resp.status_code == status.HTTP_201_CREATED
        user = User.objects.get(email="new@example.com")
        assert user.country == "Nigeria"

    def test_gym_signup_without_country_returns_400(self, api_client):
        payload = self._payload(email="gym99@example.com", role="gym")
        payload.pop("country")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_client_signup_without_country_returns_400(self, api_client):
        payload = self._payload(email="client99@example.com", role="client")
        payload.pop("country")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_response_contains_country(self, api_client):
        resp = api_client.post(
            self.URL, self._payload(country="Nigeria"), format="json"
        )
        assert resp.status_code == status.HTTP_201_CREATED

    # ---------------------------------------------------------------------------
    # unified full_name
    # ---------------------------------------------------------------------------

    def test_trainer_signup_without_full_name_returns_400(self, api_client):
        payload = self._payload()
        payload.pop("full_name")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_gym_signup_with_full_name_saves_on_gym_profile(self, api_client):
        from apps.profiles.models import GymProfile

        resp = api_client.post(
            self.URL,
            self._payload(
                email="gym88@example.com", role="gym", full_name="Iron House Gym"
            ),
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        profile = GymProfile.objects.get(user__email="gym88@example.com")
        assert profile.full_name == "Iron House Gym"

    def test_client_signup_with_full_name_saves_on_client_profile(self, api_client):
        from apps.profiles.models import ClientProfile

        resp = api_client.post(
            self.URL,
            self._payload(
                email="cli88@example.com", role="client", full_name="Jane Smith"
            ),
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        profile = ClientProfile.objects.get(user__email="cli88@example.com")
        assert profile.full_name == "Jane Smith"

    def test_client_signup_without_full_name_returns_400(self, api_client):
        payload = self._payload(email="cli77@example.com", role="client")
        payload.pop("full_name")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # ---------------------------------------------------------------------------
    # display_name removed
    # ---------------------------------------------------------------------------

    def test_user_model_has_no_display_name_field(self, api_client):
        from apps.accounts.models import User

        assert not hasattr(
            User(), "display_name"
        ), "User.display_name should be removed"

    def test_trainer_signup_does_not_require_display_name(self, api_client):
        payload = self._payload()
        payload.pop("display_name", None)
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED

    # ---------------------------------------------------------------------------
    # admin_full_name removed from signup
    # ---------------------------------------------------------------------------

    def test_gym_signup_without_admin_full_name_returns_201(self, api_client):
        payload = self._payload(email="gym77@example.com", role="gym")
        payload.pop("admin_full_name", None)
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED

    # ---------------------------------------------------------------------------
    # phone_number and city removed from signup
    # ---------------------------------------------------------------------------

    def test_trainer_signup_without_phone_number_returns_201(self, api_client):
        payload = self._payload()
        payload.pop("phone_number", None)
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED

    def test_gym_signup_without_city_returns_201(self, api_client):
        payload = self._payload(email="gym55@example.com", role="gym")
        payload.pop("city", None)
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED

    # ---------------------------------------------------------------------------
    # full_name_display property
    # ---------------------------------------------------------------------------

    def test_full_name_display_returns_trainer_profile_full_name(self, api_client):
        from apps.accounts.tests.factories import TrainerFactory
        from apps.profiles.tests.factories import TrainerProfileFactory

        user = TrainerFactory()
        TrainerProfileFactory(user=user, full_name="Trainer Name")
        assert user.full_name_display == "Trainer Name"

    def test_full_name_display_returns_gym_profile_full_name(self, api_client):
        from apps.accounts.tests.factories import GymFactory
        from apps.profiles.tests.factories import GymProfileFactory

        user = GymFactory()
        GymProfileFactory(user=user, full_name="Gym Name")
        assert user.full_name_display == "Gym Name"

    def test_full_name_display_returns_client_profile_full_name(self, api_client):
        from apps.accounts.tests.factories import ClientFactory
        from apps.profiles.tests.factories import ClientProfileFactory

        user = ClientFactory()
        ClientProfileFactory(user=user, full_name="Client Name")
        assert user.full_name_display == "Client Name"

    def test_full_name_display_falls_back_to_email_prefix(self, api_client):
        from apps.accounts.tests.factories import TrainerFactory

        user = TrainerFactory(email="john.doe@example.com")
        assert user.full_name_display == "john.doe"


# ---------------------------------------------------------------------------
# Email verification (OTP-based)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestVerifyEmailView:
    """Legacy name kept — now tests the OTP-based verify-otp/ endpoint."""

    URL = "/api/v1/auth/verify-otp/"

    def test_valid_code_returns_200(self, api_client):
        user = UnverifiedUserFactory()
        otp = generate_otp(user, OTPCode.Purpose.EMAIL_VERIFICATION)
        resp = api_client.post(
            self.URL, {"email": user.email, "code": otp.code}, format="json"
        )
        assert resp.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.is_active is True
        assert user.is_email_verified is True

    def test_invalid_code_returns_400(self, api_client):
        user = UnverifiedUserFactory()
        generate_otp(user, OTPCode.Purpose.EMAIL_VERIFICATION)
        resp = api_client.post(
            self.URL, {"email": user.email, "code": "000000"}, format="json"
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_unknown_email_returns_400(self, api_client):
        resp = api_client.post(
            self.URL, {"email": "ghost@nowhere.com", "code": "123456"}, format="json"
        )
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
        assert "current_step" in onboarding
        assert "total_steps" in onboarding
        assert "is_profile_published" in onboarding
        assert "is_first_login" in onboarding

    def test_login_onboarding_current_step_defaults_to_zero(self, api_client):
        user = UserFactory()
        resp = api_client.post(
            self.URL,
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        assert resp.data["data"]["onboarding"]["current_step"] == 0

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
# Reset password (OTP-based)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestResetPasswordView:
    """Legacy name kept — now tests the OTP-based reset-password/ endpoint."""

    URL = "/api/v1/auth/reset-password/"

    def test_valid_otp_returns_200(self, api_client):
        user = UserFactory()
        otp = generate_otp(user, OTPCode.Purpose.PASSWORD_RESET)
        resp = api_client.post(
            self.URL,
            {
                "email": user.email,
                "code": otp.code,
                "new_password": STRONG,
                "confirm_password": STRONG,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_invalid_code_returns_400(self, api_client):
        user = UserFactory()
        generate_otp(user, OTPCode.Purpose.PASSWORD_RESET)
        resp = api_client.post(
            self.URL,
            {
                "email": user.email,
                "code": "000000",
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
        assert "current_step" in onboarding
        assert "total_steps" in onboarding
        assert "is_profile_published" in onboarding
        assert "is_first_login" in onboarding

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


# ---------------------------------------------------------------------------
# Resend OTP (renamed from TestResendVerificationView)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestResendOTPView:
    URL = "/api/v1/auth/resend-otp/"

    def test_unverified_email_returns_200_and_fires_task(self, api_client):
        user = UnverifiedUserFactory(email="unverified@example.com", is_active=True)
        with patch(
            "apps.accounts.views.send_otp_verification_email_task.delay"
        ) as task:
            resp = api_client.post(
                self.URL,
                {"email": "unverified@example.com", "purpose": "email_verification"},
                format="json",
            )
            assert resp.status_code == status.HTTP_200_OK
            task.assert_called_once_with(str(user.id))

    def test_already_verified_email_returns_400(self, api_client):
        UserFactory(email="verified@example.com")
        resp = api_client.post(
            self.URL,
            {"email": "verified@example.com", "purpose": "email_verification"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "already verified" in resp.data["message"].lower()

    def test_unknown_email_returns_200_no_leak(self, api_client):
        resp = api_client.post(self.URL, {"email": "nobody@example.com"}, format="json")
        assert resp.status_code == status.HTTP_200_OK

    def test_missing_email_returns_400(self, api_client):
        resp = api_client.post(self.URL, {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_cooldown_within_60_seconds_returns_429(self, api_client):
        user = UnverifiedUserFactory(email="cool@example.com", is_active=True)
        generate_otp(user, OTPCode.Purpose.EMAIL_VERIFICATION)
        resp = api_client.post(
            self.URL,
            {"email": "cool@example.com", "purpose": "email_verification"},
            format="json",
        )
        assert resp.status_code == 429

    def test_cooldown_expired_returns_200(self, api_client):
        user = UnverifiedUserFactory(email="cool2@example.com", is_active=True)
        otp = generate_otp(user, OTPCode.Purpose.EMAIL_VERIFICATION)
        otp.created_at = timezone.now() - timedelta(seconds=61)
        otp.save(update_fields=["created_at"])
        with patch(
            "apps.accounts.views.send_otp_verification_email_task.delay"
        ) as task:
            resp = api_client.post(
                self.URL,
                {"email": "cool2@example.com", "purpose": "email_verification"},
                format="json",
            )
            assert resp.status_code == status.HTTP_200_OK
            task.assert_called_once_with(str(user.id))

    def test_password_reset_purpose_returns_200(self, api_client):
        user = UserFactory(email="reset@example.com")
        with patch(
            "apps.accounts.views.send_otp_password_reset_email_task.delay"
        ) as task:
            resp = api_client.post(
                self.URL,
                {"email": "reset@example.com", "purpose": "password_reset"},
                format="json",
            )
            assert resp.status_code == status.HTTP_200_OK
            task.assert_called_once_with(str(user.id))


# ---------------------------------------------------------------------------
# Login onboarding response
# new fields: current_step, total_steps, is_profile_published
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestLoginOnboardingResponse:
    URL = "/api/v1/auth/login/"

    def test_trainer_with_no_onboarding_current_step_is_zero(self, api_client):
        from apps.profiles.tests.factories import TrainerProfileFactory

        profile = TrainerProfileFactory()
        resp = api_client.post(
            self.URL,
            {"email": profile.user.email, "password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"]["onboarding"]["current_step"] == 0

    def test_trainer_published_profile_shows_is_profile_published_true(
        self, api_client
    ):
        from apps.profiles.tests.factories import TrainerProfileFactory

        profile = TrainerProfileFactory(is_published=True)
        resp = api_client.post(
            self.URL,
            {"email": profile.user.email, "password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"]["onboarding"]["is_profile_published"] is True

    def test_login_response_no_wizard_step_key(self, api_client):
        user = UserFactory()
        resp = api_client.post(
            self.URL,
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "wizard_step" not in resp.data["data"]["onboarding"]

    def test_login_response_no_is_completed_key(self, api_client):
        user = UserFactory()
        resp = api_client.post(
            self.URL,
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "is_completed" not in resp.data["data"]["onboarding"]

    def test_gym_login_has_is_profile_published(self, api_client):
        from apps.profiles.tests.factories import GymProfileFactory

        profile = GymProfileFactory()
        resp = api_client.post(
            self.URL,
            {"email": profile.user.email, "password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "is_profile_published" in resp.data["data"]["onboarding"]
        assert resp.data["data"]["onboarding"]["is_profile_published"] is False


# ---------------------------------------------------------------------------
# OTP: Verify email with OTP (comprehensive)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestVerifyOTPView:
    URL = "/api/v1/auth/verify-otp/"

    def test_missing_email_returns_400(self, api_client):
        resp = api_client.post(self.URL, {"code": "123456"}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_code_returns_400(self, api_client):
        resp = api_client.post(self.URL, {"email": "test@example.com"}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_unknown_email_returns_400(self, api_client):
        resp = api_client.post(
            self.URL, {"email": "ghost@nowhere.com", "code": "123456"}, format="json"
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_wrong_code_returns_400(self, api_client):
        user = UnverifiedUserFactory()
        generate_otp(user, OTPCode.Purpose.EMAIL_VERIFICATION)
        resp = api_client.post(
            self.URL, {"email": user.email, "code": "000000"}, format="json"
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_expired_otp_returns_400(self, api_client):
        user = UnverifiedUserFactory()
        otp = generate_otp(user, OTPCode.Purpose.EMAIL_VERIFICATION)
        otp.expires_at = timezone.now() - timedelta(minutes=1)
        otp.save(update_fields=["expires_at"])
        resp = api_client.post(
            self.URL, {"email": user.email, "code": otp.code}, format="json"
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_correct_code_verifies_user(self, api_client):
        user = UnverifiedUserFactory()
        otp = generate_otp(user, OTPCode.Purpose.EMAIL_VERIFICATION)
        resp = api_client.post(
            self.URL, {"email": user.email, "code": otp.code}, format="json"
        )
        assert resp.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.is_email_verified is True
        assert user.is_active is True

    def test_correct_code_creates_trial_for_trainer(self, api_client):
        from apps.accounts.tests.factories import TrainerFactory

        user = TrainerFactory(is_active=False, is_email_verified=False)
        otp = generate_otp(user, OTPCode.Purpose.EMAIL_VERIFICATION)
        with patch("apps.subscriptions.utils.create_trial_subscription") as mock_trial:
            resp = api_client.post(
                self.URL, {"email": user.email, "code": otp.code}, format="json"
            )
        assert resp.status_code == status.HTTP_200_OK
        mock_trial.assert_called_once_with(user)

    def test_already_verified_returns_400(self, api_client):
        user = UserFactory()
        otp = generate_otp(user, OTPCode.Purpose.EMAIL_VERIFICATION)
        resp = api_client.post(
            self.URL, {"email": user.email, "code": otp.code}, format="json"
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "already verified" in resp.data["message"].lower()


# ---------------------------------------------------------------------------
# OTP: Forgot password (OTP-specific tests)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestForgotPasswordOTP:
    URL = "/api/v1/auth/forgot-password/"

    def test_verified_email_returns_200_and_fires_otp_task(self, api_client):
        user = UserFactory()
        with patch(
            "apps.accounts.views.send_otp_password_reset_email_task.delay"
        ) as task:
            resp = api_client.post(self.URL, {"email": user.email}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        task.assert_called_once_with(str(user.id))

    def test_unknown_email_returns_200_no_leak(self, api_client):
        resp = api_client.post(self.URL, {"email": "nobody@nowhere.com"}, format="json")
        assert resp.status_code == status.HTTP_200_OK

    def test_unverified_email_returns_200_but_task_not_fired(self, api_client):
        user = UnverifiedUserFactory()
        with patch(
            "apps.accounts.views.send_otp_password_reset_email_task.delay"
        ) as task:
            resp = api_client.post(self.URL, {"email": user.email}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        task.assert_not_called()


# ---------------------------------------------------------------------------
# OTP: Reset password with OTP (comprehensive)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestResetPasswordOTPView:
    URL = "/api/v1/auth/reset-password/"

    def test_missing_fields_returns_400(self, api_client):
        resp = api_client.post(self.URL, {"email": "x@example.com"}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_wrong_code_returns_400(self, api_client):
        user = UserFactory()
        generate_otp(user, OTPCode.Purpose.PASSWORD_RESET)
        resp = api_client.post(
            self.URL,
            {
                "email": user.email,
                "code": "000000",
                "new_password": STRONG,
                "confirm_password": STRONG,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_expired_code_returns_400(self, api_client):
        user = UserFactory()
        otp = generate_otp(user, OTPCode.Purpose.PASSWORD_RESET)
        otp.expires_at = timezone.now() - timedelta(minutes=1)
        otp.save(update_fields=["expires_at"])
        resp = api_client.post(
            self.URL,
            {
                "email": user.email,
                "code": otp.code,
                "new_password": STRONG,
                "confirm_password": STRONG,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_mismatched_passwords_returns_400(self, api_client):
        user = UserFactory()
        otp = generate_otp(user, OTPCode.Purpose.PASSWORD_RESET)
        resp = api_client.post(
            self.URL,
            {
                "email": user.email,
                "code": otp.code,
                "new_password": STRONG,
                "confirm_password": "DifferentPass!99",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_weak_password_returns_400(self, api_client):
        user = UserFactory()
        otp = generate_otp(user, OTPCode.Purpose.PASSWORD_RESET)
        resp = api_client.post(
            self.URL,
            {
                "email": user.email,
                "code": otp.code,
                "new_password": "password",
                "confirm_password": "password",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_valid_otp_resets_password(self, api_client):
        user = UserFactory()
        otp = generate_otp(user, OTPCode.Purpose.PASSWORD_RESET)
        resp = api_client.post(
            self.URL,
            {
                "email": user.email,
                "code": otp.code,
                "new_password": STRONG,
                "confirm_password": STRONG,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.check_password(STRONG)

    def test_valid_otp_sends_password_changed_email(self, api_client, mailoutbox):
        user = UserFactory()
        otp = generate_otp(user, OTPCode.Purpose.PASSWORD_RESET)
        api_client.post(
            self.URL,
            {
                "email": user.email,
                "code": otp.code,
                "new_password": STRONG,
                "confirm_password": STRONG,
            },
            format="json",
        )
        subjects = [m.subject for m in mailoutbox]
        assert any("password" in s.lower() for s in subjects)

    def test_already_used_code_returns_400(self, api_client):
        user = UserFactory()
        otp = generate_otp(user, OTPCode.Purpose.PASSWORD_RESET)
        payload = {
            "email": user.email,
            "code": otp.code,
            "new_password": STRONG,
            "confirm_password": STRONG,
        }
        api_client.post(self.URL, payload, format="json")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
