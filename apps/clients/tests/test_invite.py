"""
TDD tests for invite-link endpoints.

POST   /api/v1/clients/invite/                   — create invite
GET    /api/v1/clients/invite/                   — list invites
DELETE /api/v1/clients/invite/<token>/           — deactivate
GET    /api/v1/clients/invite/<token>/preview/   — public preview
POST   /api/v1/clients/invite/<token>/accept/    — client joins
"""

import pytest
from django.utils import timezone

from apps.accounts.tests.factories import ClientFactory, GymFactory, TrainerFactory
from apps.clients.models import ClientMembership
from apps.clients.tests.factories import InviteLinkGymFactory, InviteLinkTrainerFactory
from apps.profiles.tests.factories import (
    ClientProfileFactory,
    GymProfileFactory,
    TrainerProfileFactory,
)

CREATE_URL = "/api/v1/clients/invite/"
LIST_URL = "/api/v1/clients/invite/"


def deactivate_url(token):
    return f"/api/v1/clients/invite/{token}/"


def preview_url(token):
    return f"/api/v1/clients/invite/{token}/preview/"


def accept_url(token):
    return f"/api/v1/clients/invite/{token}/accept/"


@pytest.mark.django_db
class TestInviteCreate:

    def test_trainer_generates_invite_returns_web_url_and_deep_link(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)

        resp = api_client.post(CREATE_URL, {}, format="json")

        assert resp.status_code == 201
        data = resp.data["data"]
        assert "web_url" in data
        assert "deep_link" in data
        assert data["owner_type"] == "trainer"

    def test_gym_generates_invite_returns_web_url_and_deep_link(self, api_client):
        gym = GymFactory()
        GymProfileFactory(user=gym)
        api_client.force_authenticate(user=gym)

        resp = api_client.post(CREATE_URL, {}, format="json")

        assert resp.status_code == 201
        data = resp.data["data"]
        assert "web_url" in data
        assert "deep_link" in data
        assert data["owner_type"] == "gym"

    def test_client_cannot_generate_invite(self, api_client):
        client = ClientFactory()
        api_client.force_authenticate(user=client)

        resp = api_client.post(CREATE_URL, {}, format="json")

        assert resp.status_code == 403

    def test_invite_created_with_expires_at_and_max_uses(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)
        future = (timezone.now() + timezone.timedelta(days=7)).isoformat()

        resp = api_client.post(
            CREATE_URL,
            {"expires_at": future, "max_uses": 5},
            format="json",
        )

        assert resp.status_code == 201
        data = resp.data["data"]
        assert data["max_uses"] == 5
        assert data["expires_at"] is not None

    def test_trainer_can_list_own_invites(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        InviteLinkTrainerFactory(trainer=profile)
        InviteLinkTrainerFactory(trainer=profile)
        api_client.force_authenticate(user=trainer)

        resp = api_client.get(LIST_URL)

        assert resp.status_code == 200
        assert len(resp.data["data"]) == 2

    def test_trainer_only_sees_own_invites(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        InviteLinkTrainerFactory(trainer=profile)

        # Another trainer's invite
        InviteLinkTrainerFactory()

        api_client.force_authenticate(user=trainer)
        resp = api_client.get(LIST_URL)

        assert resp.status_code == 200
        assert len(resp.data["data"]) == 1


@pytest.mark.django_db
class TestInviteDeactivate:

    def test_trainer_can_deactivate_own_invite(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        invite = InviteLinkTrainerFactory(trainer=profile)
        api_client.force_authenticate(user=trainer)

        resp = api_client.delete(deactivate_url(invite.token))

        assert resp.status_code == 200
        invite.refresh_from_db()
        assert invite.is_active is False

    def test_trainer_cannot_deactivate_another_trainers_invite(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        other_invite = InviteLinkTrainerFactory()
        api_client.force_authenticate(user=trainer)

        resp = api_client.delete(deactivate_url(other_invite.token))

        assert resp.status_code == 403

    def test_deactivate_unknown_token_returns_404(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)

        resp = api_client.delete(deactivate_url("nonexistenttoken123"))

        assert resp.status_code == 404


@pytest.mark.django_db
class TestInvitePreview:

    def test_preview_returns_trainer_info_for_valid_token(self, api_client):
        invite = InviteLinkTrainerFactory()

        resp = api_client.get(preview_url(invite.token))

        assert resp.status_code == 200
        data = resp.data["data"]
        assert data["type"] == "trainer"
        assert data["name"] == invite.trainer.full_name
        assert "is_valid" in data
        assert data["is_valid"] is True

    def test_preview_returns_gym_info_for_valid_gym_invite(self, api_client):
        invite = InviteLinkGymFactory()

        resp = api_client.get(preview_url(invite.token))

        assert resp.status_code == 200
        data = resp.data["data"]
        assert data["type"] == "gym"
        assert data["name"] == invite.gym.gym_name

    def test_preview_returns_404_for_unknown_token(self, api_client):
        resp = api_client.get(preview_url("unknowntoken999"))

        assert resp.status_code == 404

    def test_preview_is_public_no_auth_needed(self, api_client):
        invite = InviteLinkTrainerFactory()

        resp = api_client.get(preview_url(invite.token))

        assert resp.status_code == 200

    def test_preview_shows_invalid_for_deactivated_invite(self, api_client):
        invite = InviteLinkTrainerFactory(is_active=False)

        resp = api_client.get(preview_url(invite.token))

        assert resp.status_code == 200
        assert resp.data["data"]["is_valid"] is False


@pytest.mark.django_db
class TestInviteAccept:

    def test_client_accepts_trainer_invite_creates_membership(self, api_client):
        client_user = ClientFactory()
        client_profile = ClientProfileFactory(user=client_user)
        invite = InviteLinkTrainerFactory()
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(accept_url(invite.token))

        assert resp.status_code == 201
        assert ClientMembership.objects.filter(
            client=client_profile,
            trainer=invite.trainer,
        ).exists()

    def test_client_accepts_gym_invite_creates_membership(self, api_client):
        client_user = ClientFactory()
        client_profile = ClientProfileFactory(user=client_user)
        invite = InviteLinkGymFactory()
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(accept_url(invite.token))

        assert resp.status_code == 201
        assert ClientMembership.objects.filter(
            client=client_profile,
            gym=invite.gym,
        ).exists()

    def test_accepting_invite_increments_uses_count(self, api_client):
        client_user = ClientFactory()
        ClientProfileFactory(user=client_user)
        invite = InviteLinkTrainerFactory()
        api_client.force_authenticate(user=client_user)

        api_client.post(accept_url(invite.token))

        invite.refresh_from_db()
        assert invite.uses_count == 1

    def test_trainer_cannot_accept_invite(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        invite = InviteLinkTrainerFactory()
        api_client.force_authenticate(user=trainer)

        resp = api_client.post(accept_url(invite.token))

        assert resp.status_code == 403

    def test_accept_deactivated_invite_returns_400(self, api_client):
        client_user = ClientFactory()
        ClientProfileFactory(user=client_user)
        invite = InviteLinkTrainerFactory(is_active=False)
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(accept_url(invite.token))

        assert resp.status_code == 400

    def test_accept_unknown_token_returns_404(self, api_client):
        client_user = ClientFactory()
        ClientProfileFactory(user=client_user)
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(accept_url("unknowntoken999"))

        assert resp.status_code == 404

    def test_duplicate_membership_returns_400(self, api_client):
        client_user = ClientFactory()
        client_profile = ClientProfileFactory(user=client_user)
        invite = InviteLinkTrainerFactory()
        # Pre-existing membership for same trainer
        ClientMembership.objects.create(
            client=client_profile,
            trainer=invite.trainer,
            status=ClientMembership.Status.ACTIVE,
        )
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(accept_url(invite.token))

        assert resp.status_code == 400
