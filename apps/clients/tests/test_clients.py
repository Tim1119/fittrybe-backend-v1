"""
TDD tests for client management endpoints.

GET         /api/v1/clients/             — list managed clients
GET/PUT/DEL /api/v1/clients/<pk>/        — client detail
POST        /api/v1/clients/<pk>/reminder/ — send payment reminder
"""

from unittest.mock import patch

import pytest

from apps.accounts.tests.factories import ClientFactory, GymFactory, TrainerFactory
from apps.clients.models import ClientMembership
from apps.clients.tests.factories import (
    ClientMembershipGymFactory,
    ClientMembershipTrainerFactory,
)
from apps.profiles.tests.factories import GymProfileFactory, TrainerProfileFactory

LIST_URL = "/api/v1/clients/"


def detail_url(pk):
    return f"/api/v1/clients/{pk}/"


def reminder_url(pk):
    return f"/api/v1/clients/{pk}/reminder/"


@pytest.mark.django_db
class TestClientListView:

    def test_trainer_can_list_own_clients(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        ClientMembershipTrainerFactory(trainer=profile)
        ClientMembershipTrainerFactory(trainer=profile)
        api_client.force_authenticate(user=trainer)

        resp = api_client.get(LIST_URL)

        assert resp.status_code == 200
        assert resp.data["meta"]["pagination"]["total_count"] == 2

    def test_trainer_only_sees_own_clients(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        ClientMembershipTrainerFactory(trainer=profile)

        # Other trainer's client
        ClientMembershipTrainerFactory()

        api_client.force_authenticate(user=trainer)
        resp = api_client.get(LIST_URL)

        assert resp.status_code == 200
        assert resp.data["meta"]["pagination"]["total_count"] == 1

    def test_gym_lists_direct_clients(self, api_client):
        gym = GymFactory()
        gym_profile = GymProfileFactory(user=gym)
        ClientMembershipGymFactory(gym=gym_profile)
        ClientMembershipGymFactory(gym=gym_profile)
        api_client.force_authenticate(user=gym)

        resp = api_client.get(LIST_URL)

        assert resp.status_code == 200
        assert resp.data["meta"]["pagination"]["total_count"] == 2

    def test_gym_lists_trainer_clients_belonging_to_gym(self, api_client):
        gym = GymFactory()
        gym_profile = GymProfileFactory(user=gym)

        # A trainer who belongs to this gym
        trainer_profile = TrainerProfileFactory(gym=gym_profile)
        ClientMembershipTrainerFactory(trainer=trainer_profile)

        api_client.force_authenticate(user=gym)
        resp = api_client.get(LIST_URL)

        assert resp.status_code == 200
        assert resp.data["meta"]["pagination"]["total_count"] == 1

    def test_list_filter_by_status(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        ClientMembershipTrainerFactory(
            trainer=profile, status=ClientMembership.Status.ACTIVE
        )
        ClientMembershipTrainerFactory(
            trainer=profile, status=ClientMembership.Status.LAPSED
        )
        api_client.force_authenticate(user=trainer)

        resp = api_client.get(LIST_URL + "?status=active")

        assert resp.status_code == 200
        assert resp.data["meta"]["pagination"]["total_count"] == 1

    def test_client_role_cannot_list_clients(self, api_client):
        client = ClientFactory()
        api_client.force_authenticate(user=client)

        resp = api_client.get(LIST_URL)

        assert resp.status_code == 403


@pytest.mark.django_db
class TestClientDetailView:

    def test_trainer_can_view_own_client(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        membership = ClientMembershipTrainerFactory(trainer=profile)
        api_client.force_authenticate(user=trainer)

        resp = api_client.get(detail_url(membership.pk))

        assert resp.status_code == 200
        assert resp.data["data"]["id"] == membership.pk

    def test_trainer_cannot_view_another_trainers_client(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        other_membership = ClientMembershipTrainerFactory()
        api_client.force_authenticate(user=trainer)

        resp = api_client.get(detail_url(other_membership.pk))

        assert resp.status_code == 403

    def test_trainer_can_update_membership_status(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        membership = ClientMembershipTrainerFactory(
            trainer=profile, status=ClientMembership.Status.PENDING
        )
        api_client.force_authenticate(user=trainer)

        resp = api_client.put(
            detail_url(membership.pk),
            {"status": "active"},
            format="json",
        )

        assert resp.status_code == 200
        membership.refresh_from_db()
        assert membership.status == ClientMembership.Status.ACTIVE

    def test_trainer_can_update_payment_notes(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        membership = ClientMembershipTrainerFactory(trainer=profile)
        api_client.force_authenticate(user=trainer)

        resp = api_client.put(
            detail_url(membership.pk),
            {"payment_notes": "Paid via transfer"},
            format="json",
        )

        assert resp.status_code == 200
        membership.refresh_from_db()
        assert membership.payment_notes == "Paid via transfer"

    def test_trainer_can_soft_delete_membership(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        membership = ClientMembershipTrainerFactory(trainer=profile)
        api_client.force_authenticate(user=trainer)

        resp = api_client.delete(detail_url(membership.pk))

        assert resp.status_code == 204
        membership.refresh_from_db()
        assert membership.deleted_at is not None

    def test_soft_deleted_membership_excluded_from_list(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        membership = ClientMembershipTrainerFactory(trainer=profile)
        api_client.force_authenticate(user=trainer)

        api_client.delete(detail_url(membership.pk))
        resp = api_client.get(LIST_URL)

        assert resp.data["meta"]["pagination"]["total_count"] == 0


@pytest.mark.django_db
class TestClientReminderView:

    def test_reminder_updates_last_reminder_at(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        membership = ClientMembershipTrainerFactory(trainer=profile)
        assert membership.last_reminder_at is None
        api_client.force_authenticate(user=trainer)

        with patch("apps.clients.views.send_client_reminder_email"):
            resp = api_client.post(reminder_url(membership.pk))

        assert resp.status_code == 200
        membership.refresh_from_db()
        assert membership.last_reminder_at is not None

    def test_reminder_calls_email_function(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        membership = ClientMembershipTrainerFactory(trainer=profile)
        api_client.force_authenticate(user=trainer)

        with patch("apps.clients.views.send_client_reminder_email") as mock_email:
            api_client.post(reminder_url(membership.pk))

        mock_email.assert_called_once()

    def test_trainer_cannot_remind_another_trainers_client(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        other_membership = ClientMembershipTrainerFactory()
        api_client.force_authenticate(user=trainer)

        resp = api_client.post(reminder_url(other_membership.pk))

        assert resp.status_code == 403
