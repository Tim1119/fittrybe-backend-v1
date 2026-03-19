import uuid

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.models import User


@pytest.mark.django_db
class TestUserModel:
    def test_create_user_with_email_password_role(self):
        user = User.objects.create_user(
            email="trainer@example.com",
            password="securepass123",
            role=User.Role.TRAINER,
        )
        assert user.email == "trainer@example.com"
        assert user.check_password("securepass123")
        assert user.role == User.Role.TRAINER

    def test_email_is_username_field(self):
        assert User.USERNAME_FIELD == "email"

    def test_create_superuser(self):
        superuser = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpass123",
            role=User.Role.TRAINER,
        )
        assert superuser.is_staff is True
        assert superuser.is_superuser is True

    def test_role_choices_are_exactly_trainer_gym_client(self):
        expected = {"trainer", "gym", "client"}
        actual = {choice[0] for choice in User.Role.choices}
        assert actual == expected

    def test_is_email_verified_defaults_to_false(self):
        user = User.objects.create_user(
            email="user@example.com",
            password="pass123",
            role=User.Role.CLIENT,
        )
        assert user.is_email_verified is False

    def test_uuid_is_primary_key(self):
        user = User.objects.create_user(
            email="uuid@example.com",
            password="pass123",
            role=User.Role.GYM,
        )
        assert isinstance(user.pk, uuid.UUID)

    def test_str_returns_email(self):
        user = User.objects.create_user(
            email="str@example.com",
            password="pass123",
            role=User.Role.CLIENT,
        )
        assert str(user) == "str@example.com"

    def test_duplicate_email_raises_integrity_error(self):
        User.objects.create_user(
            email="dup@example.com",
            password="pass123",
            role=User.Role.CLIENT,
        )
        with pytest.raises(IntegrityError):
            User.objects.create_user(
                email="dup@example.com",
                password="pass456",
                role=User.Role.CLIENT,
            )

    def test_missing_email_raises_value_error(self):
        with pytest.raises(ValueError, match="Email is required"):
            User.objects.create_user(
                email="", password="pass123", role=User.Role.CLIENT
            )

    def test_created_at_and_updated_at_are_auto_set(self):
        before = timezone.now()
        user = User.objects.create_user(
            email="timestamps@example.com",
            password="pass123",
            role=User.Role.CLIENT,
        )
        after = timezone.now()
        assert before <= user.created_at <= after
        assert before <= user.updated_at <= after


@pytest.mark.django_db
class TestUserSoftDelete:
    def _make_user(self, email="softdelete@example.com"):
        return User.objects.create_user(
            email=email, password="pass123", role=User.Role.TRAINER
        )

    def test_delete_sets_deleted_at_and_deactivates(self):
        user = self._make_user()
        user.delete()
        user.refresh_from_db()
        assert user.deleted_at is not None
        assert user.is_active is False

    def test_restore_clears_deleted_at_and_activates(self):
        user = self._make_user("restore@example.com")
        user.delete()
        user.restore()
        user.refresh_from_db()
        assert user.deleted_at is None
        assert user.is_active is True

    def test_is_deleted_returns_true_after_delete(self):
        user = self._make_user("isdeleted@example.com")
        user.delete()
        user.refresh_from_db()
        assert user.is_deleted is True

    def test_is_deleted_returns_false_before_delete(self):
        user = self._make_user("notdeleted@example.com")
        assert user.is_deleted is False

    def test_hard_delete_removes_from_database(self):
        user = self._make_user("harddelete@example.com")
        pk = user.pk
        user.hard_delete()
        assert not User.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestUserOnboarding:
    def _make_user(self, email="onboard@example.com"):
        return User.objects.create_user(
            email=email, password="pass123", role=User.Role.TRAINER
        )

    def test_onboarding_status_defaults_to_not_started(self):
        user = self._make_user()
        assert user.onboarding_status == User.OnboardingStatus.NOT_STARTED

    def test_is_first_login_defaults_to_true(self):
        user = self._make_user("firstlogin@example.com")
        assert user.is_first_login is True

    def test_complete_onboarding_sets_status_and_timestamp(self):
        user = self._make_user("complete@example.com")
        before = timezone.now()
        user.complete_onboarding()
        after = timezone.now()
        user.refresh_from_db()
        assert user.onboarding_status == User.OnboardingStatus.COMPLETED
        assert before <= user.onboarding_completed_at <= after

    def test_onboarding_completed_at_is_null_by_default(self):
        user = self._make_user("nullonboard@example.com")
        assert user.onboarding_completed_at is None
