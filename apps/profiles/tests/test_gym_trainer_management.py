"""
TDD tests: gym trainer management endpoints.

Endpoints:
  POST   /api/v1/profiles/gym/trainers/       — add trainer (gym admin, max 3)
  GET    /api/v1/profiles/gym/trainers/       — list gym's trainers
  GET    /api/v1/profiles/gym/trainers/{pk}/  — get a single trainer
  DELETE /api/v1/profiles/gym/trainers/{pk}/  — hard-delete trainer user account

Rules under test:
  - Max 3 active trainers per gym; soft/hard-deleted ones do NOT count.
  - DELETE performs a hard delete of the trainer's User account, cascading
    TrainerProfile and GymTrainer; ClientMembership.trainer is SET_NULL.
"""

from unittest.mock import patch

import pytest
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.accounts.models import User
from apps.accounts.tests.factories import GymFactory, TrainerFactory
from apps.clients.tests.factories import ClientMembershipTrainerFactory
from apps.profiles.models import GymTrainer, TrainerProfile
from apps.profiles.tests.factories import GymProfileFactory, GymTrainerFactory
from apps.profiles.tokens import gym_trainer_invite_token

LIST_CREATE_URL = "/api/v1/profiles/gym/trainers/"
ACCEPT_URL = "/api/v1/profiles/gym/trainers/accept/"


def detail_url(pk):
    return f"/api/v1/profiles/gym/trainers/{pk}/"


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def gym_user():
    return GymFactory()


@pytest.fixture
def gym_profile(gym_user):
    return GymProfileFactory(user=gym_user)


def _make_gym_trainer(gym_profile):
    """Create a gym trainer belonging to the given gym."""
    return GymTrainerFactory(gym=gym_profile)


# ── POST: max 3 trainers ───────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGymTrainerMaxLimit:
    """POST must enforce a maximum of 3 active trainers per gym."""

    def test_can_add_first_trainer(self, api_client, gym_user, gym_profile):
        api_client.force_authenticate(user=gym_user)

        with patch("apps.profiles.views.send_gym_trainer_invite_email"):
            resp = api_client.post(
                LIST_CREATE_URL,
                {"email": "first@test.com", "full_name": "First Trainer"},
                format="json",
            )

        assert resp.status_code == 201

    def test_third_trainer_allowed(self, api_client, gym_user, gym_profile):
        _make_gym_trainer(gym_profile)
        _make_gym_trainer(gym_profile)
        api_client.force_authenticate(user=gym_user)

        with patch("apps.profiles.views.send_gym_trainer_invite_email"):
            resp = api_client.post(
                LIST_CREATE_URL,
                {"email": "third@test.com", "full_name": "Third Trainer"},
                format="json",
            )

        assert resp.status_code == 201

    def test_fourth_trainer_blocked(self, api_client, gym_user, gym_profile):
        _make_gym_trainer(gym_profile)
        _make_gym_trainer(gym_profile)
        _make_gym_trainer(gym_profile)
        api_client.force_authenticate(user=gym_user)

        resp = api_client.post(
            LIST_CREATE_URL,
            {"email": "fourth@test.com", "full_name": "Fourth"},
            format="json",
        )

        assert resp.status_code == 400
        assert resp.data["code"] == "VALIDATION_ERROR"

    def test_deleted_trainer_does_not_count_toward_limit(
        self, api_client, gym_user, gym_profile
    ):
        """Hard-deleting a trainer reduces the active count, unblocking a new invite."""
        _make_gym_trainer(gym_profile)
        _make_gym_trainer(gym_profile)
        to_remove = _make_gym_trainer(gym_profile)
        to_remove.trainer.user.hard_delete()  # cascades GymTrainer out of DB
        api_client.force_authenticate(user=gym_user)

        with patch("apps.profiles.views.send_gym_trainer_invite_email"):
            resp = api_client.post(
                LIST_CREATE_URL,
                {"email": "replacement@test.com", "full_name": "Replacement"},
                format="json",
            )

        assert resp.status_code == 201


# ── DELETE: hard delete ────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGymTrainerHardDelete:
    """DELETE must hard-delete the trainer's User and cascade related records."""

    def test_delete_returns_200(self, api_client, gym_user, gym_profile):
        gym_trainer = _make_gym_trainer(gym_profile)
        api_client.force_authenticate(user=gym_user)

        resp = api_client.delete(detail_url(gym_trainer.pk))

        assert resp.status_code == 200

    def test_delete_removes_user_from_db(self, api_client, gym_user, gym_profile):
        gym_trainer = _make_gym_trainer(gym_profile)
        trainer_user_pk = gym_trainer.trainer.user.pk
        api_client.force_authenticate(user=gym_user)

        api_client.delete(detail_url(gym_trainer.pk))

        assert not User.objects.filter(pk=trainer_user_pk).exists()

    def test_delete_removes_trainer_profile(self, api_client, gym_user, gym_profile):
        gym_trainer = _make_gym_trainer(gym_profile)
        trainer_profile_pk = gym_trainer.trainer.pk
        api_client.force_authenticate(user=gym_user)

        api_client.delete(detail_url(gym_trainer.pk))

        assert not TrainerProfile.all_objects.filter(pk=trainer_profile_pk).exists()

    def test_delete_removes_gym_trainer_record(self, api_client, gym_user, gym_profile):
        gym_trainer = _make_gym_trainer(gym_profile)
        gym_trainer_pk = gym_trainer.pk
        api_client.force_authenticate(user=gym_user)

        api_client.delete(detail_url(gym_trainer_pk))

        assert not GymTrainer.all_objects.filter(pk=gym_trainer_pk).exists()

    def test_delete_sets_client_membership_trainer_to_null(
        self, api_client, gym_user, gym_profile
    ):
        gym_trainer = _make_gym_trainer(gym_profile)
        membership = ClientMembershipTrainerFactory(trainer=gym_trainer.trainer)
        api_client.force_authenticate(user=gym_user)

        api_client.delete(detail_url(gym_trainer.pk))

        membership.refresh_from_db()
        assert membership.trainer_id is None

    def test_delete_trainer_from_other_gym_returns_404(
        self, api_client, gym_user, gym_profile
    ):
        other_gym_trainer = GymTrainerFactory()  # belongs to a different gym
        api_client.force_authenticate(user=gym_user)

        resp = api_client.delete(detail_url(other_gym_trainer.pk))

        assert resp.status_code == 404

    def test_after_delete_can_add_trainer_again(
        self, api_client, gym_user, gym_profile
    ):
        """Deleting from a full gym (3) frees a slot for a new trainer."""
        _make_gym_trainer(gym_profile)
        _make_gym_trainer(gym_profile)
        to_remove = _make_gym_trainer(gym_profile)
        api_client.force_authenticate(user=gym_user)

        api_client.delete(detail_url(to_remove.pk))

        with patch("apps.profiles.views.send_gym_trainer_invite_email"):
            resp = api_client.post(
                LIST_CREATE_URL,
                {"email": "newafter@test.com", "full_name": "New After Delete"},
                format="json",
            )

        assert resp.status_code == 201


# ── Permissions ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGymTrainerPermissions:
    def test_trainer_cannot_post(self, api_client):
        trainer_user = TrainerFactory()
        api_client.force_authenticate(user=trainer_user)

        resp = api_client.post(
            LIST_CREATE_URL,
            {"email": "x@x.com", "full_name": "X"},
            format="json",
        )

        assert resp.status_code == 403

    def test_trainer_cannot_delete(self, api_client):
        trainer_user = TrainerFactory()
        gym_trainer = GymTrainerFactory()
        api_client.force_authenticate(user=trainer_user)

        resp = api_client.delete(detail_url(gym_trainer.pk))

        assert resp.status_code == 403


# ── GET: read endpoints ────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGymTrainerRead:
    def test_list_returns_gym_trainers(self, api_client, gym_user, gym_profile):
        _make_gym_trainer(gym_profile)
        _make_gym_trainer(gym_profile)
        api_client.force_authenticate(user=gym_user)

        resp = api_client.get(LIST_CREATE_URL)

        assert resp.status_code == 200
        assert len(resp.data["data"]) == 2

    def test_list_excludes_other_gym_trainers(self, api_client, gym_user, gym_profile):
        _make_gym_trainer(gym_profile)
        GymTrainerFactory()  # different gym
        api_client.force_authenticate(user=gym_user)

        resp = api_client.get(LIST_CREATE_URL)

        assert resp.status_code == 200
        assert len(resp.data["data"]) == 1

    def test_get_detail_returns_200(self, api_client, gym_user, gym_profile):
        gym_trainer = _make_gym_trainer(gym_profile)
        api_client.force_authenticate(user=gym_user)

        resp = api_client.get(detail_url(gym_trainer.pk))

        assert resp.status_code == 200

    def test_get_detail_other_gym_returns_404(self, api_client, gym_user, gym_profile):
        other_gym_trainer = GymTrainerFactory()
        api_client.force_authenticate(user=gym_user)

        resp = api_client.get(detail_url(other_gym_trainer.pk))

        assert resp.status_code == 404


# ── Accept invite tests ────────────────────────────────────────────────────────


def _make_inactive_trainer_user():
    """Create a trainer User whose account is inactive (as-created by gym invite)."""
    user = TrainerFactory()
    user.is_active = False
    user.set_unusable_password()
    user.save(update_fields=["is_active", "password"])
    return user


def _valid_uid_token(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = gym_trainer_invite_token.make_token(user)
    return uid, token


@pytest.mark.django_db
class TestGymTrainerAcceptInvite:
    def test_valid_accept_returns_200(self, api_client):
        user = _make_inactive_trainer_user()
        uid, token = _valid_uid_token(user)

        resp = api_client.post(
            ACCEPT_URL,
            {
                "uid": uid,
                "token": token,
                "password": "Str0ng!Pass#99",
                "confirm_password": "Str0ng!Pass#99",
            },
            format="json",
        )

        assert resp.status_code == 200

    def test_user_is_active_after_accept(self, api_client):
        user = _make_inactive_trainer_user()
        uid, token = _valid_uid_token(user)

        api_client.post(
            ACCEPT_URL,
            {
                "uid": uid,
                "token": token,
                "password": "Str0ng!Pass#99",
                "confirm_password": "Str0ng!Pass#99",
            },
            format="json",
        )

        user.refresh_from_db()
        assert user.is_active is True

    def test_password_is_set_after_accept(self, api_client):
        user = _make_inactive_trainer_user()
        uid, token = _valid_uid_token(user)

        api_client.post(
            ACCEPT_URL,
            {
                "uid": uid,
                "token": token,
                "password": "Str0ng!Pass#99",
                "confirm_password": "Str0ng!Pass#99",
            },
            format="json",
        )

        user.refresh_from_db()
        assert user.has_usable_password()
        assert user.check_password("Str0ng!Pass#99")

    def test_trainer_can_login_after_accept(self, api_client):
        user = _make_inactive_trainer_user()
        uid, token = _valid_uid_token(user)
        api_client.post(
            ACCEPT_URL,
            {
                "uid": uid,
                "token": token,
                "password": "Str0ng!Pass#99",
                "confirm_password": "Str0ng!Pass#99",
            },
            format="json",
        )

        resp = api_client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "Str0ng!Pass#99"},
            format="json",
        )

        assert resp.status_code == 200

    def test_passwords_mismatch_returns_400(self, api_client):
        user = _make_inactive_trainer_user()
        uid, token = _valid_uid_token(user)

        resp = api_client.post(
            ACCEPT_URL,
            {
                "uid": uid,
                "token": token,
                "password": "Str0ng!Pass#99",
                "confirm_password": "Different#99",
            },
            format="json",
        )

        assert resp.status_code == 400
        assert resp.data["code"] == "VALIDATION_ERROR"

    def test_weak_password_returns_400(self, api_client):
        user = _make_inactive_trainer_user()
        uid, token = _valid_uid_token(user)

        resp = api_client.post(
            ACCEPT_URL,
            {
                "uid": uid,
                "token": token,
                "password": "password",
                "confirm_password": "password",
            },
            format="json",
        )

        assert resp.status_code == 400
        assert resp.data["code"] == "VALIDATION_ERROR"

    def test_invalid_uid_returns_400(self, api_client):
        user = _make_inactive_trainer_user()
        _, token = _valid_uid_token(user)

        resp = api_client.post(
            ACCEPT_URL,
            {
                "uid": "notvalidbase64!!!!",
                "token": token,
                "password": "Str0ng!Pass#99",
                "confirm_password": "Str0ng!Pass#99",
            },
            format="json",
        )

        assert resp.status_code == 400
        assert resp.data["code"] == "VALIDATION_ERROR"

    def test_invalid_token_returns_400(self, api_client):
        user = _make_inactive_trainer_user()
        uid, _ = _valid_uid_token(user)

        resp = api_client.post(
            ACCEPT_URL,
            {
                "uid": uid,
                "token": "totally-wrong-token",
                "password": "Str0ng!Pass#99",
                "confirm_password": "Str0ng!Pass#99",
            },
            format="json",
        )

        assert resp.status_code == 400
        assert resp.data["code"] == "VALIDATION_ERROR"

    def test_tampered_token_returns_400(self, api_client):
        user = _make_inactive_trainer_user()
        uid, token = _valid_uid_token(user)
        tampered = token[:-4] + "XXXX"

        resp = api_client.post(
            ACCEPT_URL,
            {
                "uid": uid,
                "token": tampered,
                "password": "Str0ng!Pass#99",
                "confirm_password": "Str0ng!Pass#99",
            },
            format="json",
        )

        assert resp.status_code == 400
        assert resp.data["code"] == "VALIDATION_ERROR"

    def test_already_active_user_returns_400(self, api_client):
        user = TrainerFactory()  # active by default
        uid, token = _valid_uid_token(user)

        resp = api_client.post(
            ACCEPT_URL,
            {
                "uid": uid,
                "token": token,
                "password": "Str0ng!Pass#99",
                "confirm_password": "Str0ng!Pass#99",
            },
            format="json",
        )

        assert resp.status_code == 400
        assert resp.data["code"] == "VALIDATION_ERROR"

    def test_missing_uid_returns_400(self, api_client):
        user = _make_inactive_trainer_user()
        _, token = _valid_uid_token(user)

        resp = api_client.post(
            ACCEPT_URL,
            {
                "token": token,
                "password": "Str0ng!Pass#99",
                "confirm_password": "Str0ng!Pass#99",
            },
            format="json",
        )

        assert resp.status_code == 400
        assert resp.data["code"] == "VALIDATION_ERROR"

    def test_missing_token_returns_400(self, api_client):
        user = _make_inactive_trainer_user()
        uid, _ = _valid_uid_token(user)

        resp = api_client.post(
            ACCEPT_URL,
            {
                "uid": uid,
                "password": "Str0ng!Pass#99",
                "confirm_password": "Str0ng!Pass#99",
            },
            format="json",
        )

        assert resp.status_code == 400
        assert resp.data["code"] == "VALIDATION_ERROR"
