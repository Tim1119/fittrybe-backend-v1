"""
Tests for accounts serializers.
"""

import pytest

from apps.accounts.serializers import (
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserProfileSerializer,
)
from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestRegisterSerializer:
    STRONG_PASSWORD = "F1tTryb3!#2025"

    def _data(self, **kwargs):
        defaults = {
            "email": "trainer@example.com",
            "password": self.STRONG_PASSWORD,
            "confirm_password": self.STRONG_PASSWORD,
            "role": "trainer",
        }
        defaults.update(kwargs)
        return defaults

    def test_valid_trainer_data_passes(self):
        s = RegisterSerializer(data=self._data(role="trainer"))
        assert s.is_valid(), s.errors

    def test_valid_gym_data_passes(self):
        s = RegisterSerializer(data=self._data(email="gym@example.com", role="gym"))
        assert s.is_valid(), s.errors

    def test_valid_client_data_passes(self):
        s = RegisterSerializer(
            data=self._data(email="client@example.com", role="client")
        )
        assert s.is_valid(), s.errors

    def test_duplicate_email_returns_error(self):
        UserFactory(email="dup@example.com")
        s = RegisterSerializer(data=self._data(email="dup@example.com"))
        assert not s.is_valid()
        assert "email" in s.errors

    def test_password_mismatch_returns_error(self):
        s = RegisterSerializer(data=self._data(confirm_password="DifferentPass1!"))
        assert not s.is_valid()
        assert "non_field_errors" in s.errors or "confirm_password" in s.errors

    def test_password_too_short_returns_error(self):
        s = RegisterSerializer(
            data=self._data(password="Ab1!", confirm_password="Ab1!")
        )
        assert not s.is_valid()

    def test_common_password_fails(self):
        s = RegisterSerializer(
            data=self._data(password="password123", confirm_password="password123")
        )
        assert not s.is_valid()

    def test_weak_password_fails_zxcvbn(self):
        # Score < 2
        s = RegisterSerializer(
            data=self._data(password="aaaaaaaa", confirm_password="aaaaaaaa")
        )
        assert not s.is_valid()

    def test_strong_password_passes(self):
        s = RegisterSerializer(data=self._data())
        assert s.is_valid(), s.errors

    def test_invalid_role_returns_error(self):
        s = RegisterSerializer(data=self._data(role="superadmin"))
        assert not s.is_valid()
        assert "role" in s.errors

    def test_create_user_is_inactive_and_unverified(self):
        s = RegisterSerializer(data=self._data())
        assert s.is_valid(), s.errors
        user = s.save()
        assert user.is_active is False
        assert user.is_email_verified is False


@pytest.mark.django_db
class TestUserProfileSerializer:
    def test_returns_expected_fields(self):
        user = UserFactory()
        s = UserProfileSerializer(user)
        data = s.data
        assert set(data.keys()) == {
            "id",
            "email",
            "role",
            "is_email_verified",
            "created_at",
        }

    def test_id_is_string(self):
        user = UserFactory()
        s = UserProfileSerializer(user)
        assert isinstance(s.data["id"], str)

    def test_email_matches(self):
        user = UserFactory(email="test@fittrybe.com")
        s = UserProfileSerializer(user)
        assert s.data["email"] == "test@fittrybe.com"

    def test_role_matches(self):
        user = UserFactory(role="gym")
        s = UserProfileSerializer(user)
        assert s.data["role"] == "gym"

    def test_is_email_verified_matches(self):
        user = UserFactory(is_email_verified=True)
        s = UserProfileSerializer(user)
        assert s.data["is_email_verified"] is True


@pytest.mark.django_db
class TestForgotPasswordSerializer:
    def test_valid_email_passes(self):
        s = ForgotPasswordSerializer(data={"email": "user@example.com"})
        assert s.is_valid(), s.errors

    def test_invalid_email_fails(self):
        s = ForgotPasswordSerializer(data={"email": "not-an-email"})
        assert not s.is_valid()


class TestResetPasswordSerializer:
    STRONG = "F1tTryb3!#2025"

    def test_valid_data_passes(self):
        s = ResetPasswordSerializer(
            data={
                "uid": "abc",
                "token": "xyz",
                "new_password": self.STRONG,
                "confirm_password": self.STRONG,
            }
        )
        assert s.is_valid(), s.errors

    def test_password_mismatch_fails(self):
        s = ResetPasswordSerializer(
            data={
                "uid": "abc",
                "token": "xyz",
                "new_password": self.STRONG,
                "confirm_password": "DifferentPass1!",
            }
        )
        assert not s.is_valid()

    def test_weak_password_fails(self):
        s = ResetPasswordSerializer(
            data={
                "uid": "abc",
                "token": "xyz",
                "new_password": "aaaaaaaa",
                "confirm_password": "aaaaaaaa",
            }
        )
        assert not s.is_valid()


class TestChangePasswordSerializer:
    STRONG = "F1tTryb3!#2025"

    def test_valid_data_passes(self):
        s = ChangePasswordSerializer(
            data={
                "old_password": "OldPass1!",
                "new_password": self.STRONG,
                "confirm_password": self.STRONG,
            }
        )
        assert s.is_valid(), s.errors

    def test_password_mismatch_fails(self):
        s = ChangePasswordSerializer(
            data={
                "old_password": "OldPass1!",
                "new_password": self.STRONG,
                "confirm_password": "Different1!",
            }
        )
        assert not s.is_valid()

    def test_weak_new_password_fails(self):
        s = ChangePasswordSerializer(
            data={
                "old_password": "OldPass1!",
                "new_password": "aaaaaaaa",
                "confirm_password": "aaaaaaaa",
            }
        )
        assert not s.is_valid()
