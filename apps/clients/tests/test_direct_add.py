"""
TDD tests: manual client add by username (TRN-07 Option 2).

  GET  /api/v1/clients/search/?username={q}  — search existing clients
  POST /api/v1/clients/add/                  — directly add client by username
"""

import pytest

from apps.accounts.tests.factories import ClientFactory, GymFactory, TrainerFactory
from apps.clients.models import ClientMembership
from apps.profiles.tests.factories import (
    ClientProfileFactory,
    GymProfileFactory,
    TrainerProfileFactory,
)

SEARCH_URL = "/api/v1/clients/search/"
ADD_URL = "/api/v1/clients/add/"


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def trainer_user():
    return TrainerFactory()


@pytest.fixture
def trainer_profile(trainer_user):
    return TrainerProfileFactory(user=trainer_user, trainer_type="independent")


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
def client_user():
    return ClientFactory()


@pytest.fixture
def client_profile(client_user):
    return ClientProfileFactory(user=client_user)


# ── Search tests ───────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestClientSearch:
    def test_trainer_can_search_by_username(
        self, api_client, trainer_user, trainer_profile, client_profile
    ):
        api_client.force_authenticate(user=trainer_user)

        resp = api_client.get(SEARCH_URL, {"username": client_profile.username})

        assert resp.status_code == 200
        assert len(resp.data["data"]) == 1
        assert resp.data["data"][0]["username"] == client_profile.username

    def test_search_no_match_returns_empty_with_message(
        self, api_client, trainer_user, trainer_profile
    ):
        api_client.force_authenticate(user=trainer_user)

        resp = api_client.get(SEARCH_URL, {"username": "zzznomatchzzz"})

        assert resp.status_code == 200
        assert resp.data["data"] == []
        assert "invite link" in resp.data["message"].lower()

    def test_missing_username_param_returns_400(
        self, api_client, trainer_user, trainer_profile
    ):
        api_client.force_authenticate(user=trainer_user)

        resp = api_client.get(SEARCH_URL)

        assert resp.status_code == 400
        assert resp.data["code"] == "VALIDATION_ERROR"

    def test_gym_trainer_cannot_search(
        self, api_client, gym_trainer_user, gym_trainer_profile
    ):
        api_client.force_authenticate(user=gym_trainer_user)

        resp = api_client.get(SEARCH_URL, {"username": "anyone"})

        assert resp.status_code == 403
        assert resp.data["code"] == "PERMISSION_DENIED"

    def test_client_role_cannot_search(self, api_client, client_user):
        api_client.force_authenticate(user=client_user)

        resp = api_client.get(SEARCH_URL, {"username": "anyone"})

        assert resp.status_code == 403


# ── Direct add tests ───────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestClientDirectAdd:
    def test_trainer_can_add_client(
        self, api_client, trainer_user, trainer_profile, client_profile
    ):
        api_client.force_authenticate(user=trainer_user)

        resp = api_client.post(ADD_URL, {"username": client_profile.username})

        assert resp.status_code == 201
        assert resp.data["message"] == "Client added to your community."

    def test_gym_can_add_client(
        self, api_client, gym_user, gym_profile, client_profile
    ):
        api_client.force_authenticate(user=gym_user)

        resp = api_client.post(ADD_URL, {"username": client_profile.username})

        assert resp.status_code == 201

    def test_membership_created_with_status_active(
        self, api_client, trainer_user, trainer_profile, client_profile
    ):
        api_client.force_authenticate(user=trainer_user)

        api_client.post(ADD_URL, {"username": client_profile.username})

        membership = ClientMembership.objects.get(
            client=client_profile, trainer=trainer_profile
        )
        assert membership.status == ClientMembership.Status.ACTIVE

    def test_unknown_username_returns_404(
        self, api_client, trainer_user, trainer_profile
    ):
        api_client.force_authenticate(user=trainer_user)

        resp = api_client.post(ADD_URL, {"username": "ghostuser99999"})

        assert resp.status_code == 404
        assert resp.data["code"] == "NOT_FOUND"

    def test_adding_non_client_account_returns_400(
        self, api_client, trainer_user, trainer_profile
    ):
        """A ClientProfile linked to a non-client user should be rejected."""
        non_client_user = TrainerFactory()
        bad_profile = ClientProfileFactory(user=non_client_user)
        api_client.force_authenticate(user=trainer_user)

        resp = api_client.post(ADD_URL, {"username": bad_profile.username})

        assert resp.status_code == 400
        assert resp.data["code"] == "VALIDATION_ERROR"

    def test_already_member_returns_400(
        self, api_client, trainer_user, trainer_profile, client_profile
    ):
        ClientMembership.objects.create(
            client=client_profile,
            trainer=trainer_profile,
            status=ClientMembership.Status.ACTIVE,
        )
        api_client.force_authenticate(user=trainer_user)

        resp = api_client.post(ADD_URL, {"username": client_profile.username})

        assert resp.status_code == 400
        assert resp.data["code"] == "ALREADY_EXISTS"

    def test_gym_trainer_cannot_add(
        self, api_client, gym_trainer_user, gym_trainer_profile, client_profile
    ):
        api_client.force_authenticate(user=gym_trainer_user)

        resp = api_client.post(ADD_URL, {"username": client_profile.username})

        assert resp.status_code == 403
        assert resp.data["code"] == "PERMISSION_DENIED"

    def test_client_role_cannot_add(self, api_client, client_user, client_profile):
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(ADD_URL, {"username": client_profile.username})

        assert resp.status_code == 403
