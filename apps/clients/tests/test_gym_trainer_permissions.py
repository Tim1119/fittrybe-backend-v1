"""
TDD tests: gym trainer permission restrictions on write endpoints.

Gym trainers (trainer_type='gym_trainer') must be blocked from:
  - POST /clients/invite/
  - DELETE /clients/invite/{token}/
  - PUT /clients/{id}/
  - DELETE /clients/{id}/
  - POST /clients/{id}/reminder/

Gym trainers are still allowed to:
  - GET /clients/
  - GET /clients/{id}/
  - GET /clients/invite/

Independent trainers must not be affected.
"""

import pytest

from apps.accounts.tests.factories import GymFactory, TrainerFactory
from apps.clients.tests.factories import (
    ClientMembershipTrainerFactory,
    InviteLinkGymFactory,
)
from apps.profiles.tests.factories import GymProfileFactory, TrainerProfileFactory

INVITE_LIST_URL = "/api/v1/clients/invite/"
LIST_URL = "/api/v1/clients/"


def invite_deactivate_url(token):
    return f"/api/v1/clients/invite/{token}/"


def detail_url(pk):
    return f"/api/v1/clients/{pk}/"


def reminder_url(pk):
    return f"/api/v1/clients/{pk}/reminder/"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def gym_user():
    return GymFactory()


@pytest.fixture
def gym_profile(gym_user):
    return GymProfileFactory(user=gym_user)


@pytest.fixture
def gym_trainer_user():
    return TrainerFactory()


@pytest.fixture
def gym_trainer_profile(gym_trainer_user, gym_profile):
    return TrainerProfileFactory(
        user=gym_trainer_user,
        trainer_type="gym_trainer",
        gym=gym_profile,
    )


@pytest.fixture
def gym_trainer_membership(gym_trainer_profile):
    """A client membership linked to the gym trainer's own trainer profile."""
    return ClientMembershipTrainerFactory(trainer=gym_trainer_profile)


@pytest.fixture
def gym_invite(gym_profile):
    return InviteLinkGymFactory(gym=gym_profile)


@pytest.fixture
def indie_trainer_user():
    return TrainerFactory()


@pytest.fixture
def indie_trainer_profile(indie_trainer_user):
    return TrainerProfileFactory(user=indie_trainer_user, trainer_type="independent")


@pytest.fixture
def indie_membership(indie_trainer_profile):
    return ClientMembershipTrainerFactory(trainer=indie_trainer_profile)


# ── BLOCKED: gym trainer write endpoints ──────────────────────────────────────


@pytest.mark.django_db
class TestGymTrainerBlockedWriteEndpoints:
    """All write operations must return 403 for gym trainers."""

    def test_gym_trainer_cannot_post_invite(
        self, api_client, gym_trainer_user, gym_trainer_profile
    ):
        api_client.force_authenticate(user=gym_trainer_user)

        resp = api_client.post(INVITE_LIST_URL, {}, format="json")

        assert resp.status_code == 403
        assert resp.data["code"] == "PERMISSION_DENIED"

    def test_gym_trainer_cannot_delete_invite(
        self, api_client, gym_trainer_user, gym_trainer_profile, gym_invite
    ):
        api_client.force_authenticate(user=gym_trainer_user)

        resp = api_client.delete(invite_deactivate_url(gym_invite.token))

        assert resp.status_code == 403
        assert resp.data["code"] == "PERMISSION_DENIED"

    def test_gym_trainer_cannot_put_membership(
        self, api_client, gym_trainer_user, gym_trainer_profile, gym_trainer_membership
    ):
        api_client.force_authenticate(user=gym_trainer_user)

        resp = api_client.put(
            detail_url(gym_trainer_membership.pk),
            {"status": "lapsed"},
            format="json",
        )

        assert resp.status_code == 403
        assert resp.data["code"] == "PERMISSION_DENIED"

    def test_gym_trainer_cannot_delete_membership(
        self, api_client, gym_trainer_user, gym_trainer_profile, gym_trainer_membership
    ):
        api_client.force_authenticate(user=gym_trainer_user)

        resp = api_client.delete(detail_url(gym_trainer_membership.pk))

        assert resp.status_code == 403
        assert resp.data["code"] == "PERMISSION_DENIED"

    def test_gym_trainer_cannot_post_reminder(
        self, api_client, gym_trainer_user, gym_trainer_profile, gym_trainer_membership
    ):
        api_client.force_authenticate(user=gym_trainer_user)

        resp = api_client.post(reminder_url(gym_trainer_membership.pk))

        assert resp.status_code == 403
        assert resp.data["code"] == "PERMISSION_DENIED"

    def test_gym_trainer_error_message_mentions_gym_admin(
        self, api_client, gym_trainer_user, gym_trainer_profile
    ):
        """Error message should guide the user toward the gym admin."""
        api_client.force_authenticate(user=gym_trainer_user)

        resp = api_client.post(INVITE_LIST_URL, {}, format="json")

        assert "gym admin" in resp.data["message"].lower()


# ── ALLOWED: gym trainer read endpoints ───────────────────────────────────────


@pytest.mark.django_db
class TestGymTrainerAllowedReadEndpoints:
    """Read-only access must remain open for gym trainers."""

    def test_gym_trainer_can_list_clients(
        self, api_client, gym_trainer_user, gym_trainer_profile
    ):
        api_client.force_authenticate(user=gym_trainer_user)

        resp = api_client.get(LIST_URL)

        assert resp.status_code == 200

    def test_gym_trainer_can_get_client_detail(
        self, api_client, gym_trainer_user, gym_trainer_profile, gym_trainer_membership
    ):
        api_client.force_authenticate(user=gym_trainer_user)

        resp = api_client.get(detail_url(gym_trainer_membership.pk))

        assert resp.status_code == 200

    def test_gym_trainer_can_list_invites(
        self, api_client, gym_trainer_user, gym_trainer_profile
    ):
        api_client.force_authenticate(user=gym_trainer_user)

        resp = api_client.get(INVITE_LIST_URL)

        assert resp.status_code == 200


# ── CONTRAST: independent trainer is NOT blocked ──────────────────────────────


@pytest.mark.django_db
class TestIndependentTrainerNotBlocked:
    """Independent trainers must be completely unaffected by the gym block."""

    def test_independent_trainer_can_post_invite(
        self, api_client, indie_trainer_user, indie_trainer_profile
    ):
        api_client.force_authenticate(user=indie_trainer_user)

        resp = api_client.post(INVITE_LIST_URL, {}, format="json")

        assert resp.status_code == 201

    def test_independent_trainer_can_put_membership(
        self, api_client, indie_trainer_user, indie_trainer_profile, indie_membership
    ):
        api_client.force_authenticate(user=indie_trainer_user)

        resp = api_client.put(
            detail_url(indie_membership.pk),
            {"status": "lapsed"},
            format="json",
        )

        assert resp.status_code == 200

    def test_independent_trainer_can_delete_membership(
        self, api_client, indie_trainer_user, indie_trainer_profile, indie_membership
    ):
        api_client.force_authenticate(user=indie_trainer_user)

        resp = api_client.delete(detail_url(indie_membership.pk))

        assert resp.status_code == 204
