"""
TDD tests for weekly recognition post endpoint.

POST /api/v1/badges/recognition-post/
"""

import pytest

from apps.accounts.tests.factories import ClientFactory, TrainerFactory
from apps.badges.models import BadgeAssignment
from apps.badges.tests.factories import BadgeFactory
from apps.chat.models import Chatroom, Message
from apps.clients.tests.factories import ClientMembershipTrainerFactory
from apps.profiles.tests.factories import ClientProfileFactory, TrainerProfileFactory

RECOGNITION_URL = "/api/v1/badges/recognition-post/"


def _make_slot(client_profile, badge):
    return {
        "client_id": str(client_profile.id),
        "badge_id": badge.id,
        "note": "Crushed it!",
    }


@pytest.mark.django_db
class TestWeeklyRecognitionPostView:

    def _setup_trainer_with_chatroom(self):
        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        chatroom = Chatroom.objects.create(trainer=trainer_profile, name="Community")
        return trainer, trainer_profile, chatroom

    def test_recognition_post_1_slot_returns_201(self, api_client):
        trainer, trainer_profile, chatroom = self._setup_trainer_with_chatroom()
        client_profile = ClientProfileFactory()
        ClientMembershipTrainerFactory(trainer=trainer_profile, client=client_profile)
        badge = BadgeFactory()

        api_client.force_authenticate(user=trainer)
        resp = api_client.post(
            RECOGNITION_URL,
            {"slots": [_make_slot(client_profile, badge)]},
            format="json",
        )

        assert resp.status_code == 201
        assert len(resp.data["data"]) == 1

    def test_recognition_post_3_slots_returns_201(self, api_client):
        trainer, trainer_profile, chatroom = self._setup_trainer_with_chatroom()
        clients = [ClientProfileFactory() for _ in range(3)]
        badges = [BadgeFactory() for _ in range(3)]
        for c in clients:
            ClientMembershipTrainerFactory(trainer=trainer_profile, client=c)

        slots = [_make_slot(clients[i], badges[i]) for i in range(3)]

        api_client.force_authenticate(user=trainer)
        resp = api_client.post(RECOGNITION_URL, {"slots": slots}, format="json")

        assert resp.status_code == 201
        assert len(resp.data["data"]) == 3

    def test_badge_assignments_created_for_each_slot(self, api_client):
        trainer, trainer_profile, chatroom = self._setup_trainer_with_chatroom()
        clients = [ClientProfileFactory() for _ in range(2)]
        badges = [BadgeFactory() for _ in range(2)]
        for c in clients:
            ClientMembershipTrainerFactory(trainer=trainer_profile, client=c)

        slots = [_make_slot(clients[i], badges[i]) for i in range(2)]
        api_client.force_authenticate(user=trainer)
        api_client.post(RECOGNITION_URL, {"slots": slots}, format="json")

        assert BadgeAssignment.objects.filter(trainer=trainer_profile).count() == 2

    def test_one_chatroom_message_created_not_3(self, api_client):
        trainer, trainer_profile, chatroom = self._setup_trainer_with_chatroom()
        clients = [ClientProfileFactory() for _ in range(3)]
        badges = [BadgeFactory() for _ in range(3)]
        for c in clients:
            ClientMembershipTrainerFactory(trainer=trainer_profile, client=c)

        slots = [_make_slot(clients[i], badges[i]) for i in range(3)]
        api_client.force_authenticate(user=trainer)
        api_client.post(RECOGNITION_URL, {"slots": slots}, format="json")

        assert Message.objects.filter(chatroom=chatroom).count() == 1

    def test_message_content_contains_all_clients(self, api_client):
        trainer, trainer_profile, chatroom = self._setup_trainer_with_chatroom()
        clients = [ClientProfileFactory() for _ in range(3)]
        badges = [BadgeFactory() for _ in range(3)]
        for c in clients:
            ClientMembershipTrainerFactory(trainer=trainer_profile, client=c)

        slots = [_make_slot(clients[i], badges[i]) for i in range(3)]
        api_client.force_authenticate(user=trainer)
        api_client.post(RECOGNITION_URL, {"slots": slots}, format="json")

        msg = Message.objects.filter(chatroom=chatroom).first()
        for c in clients:
            assert c.username in msg.content

    def test_message_type_is_announcement(self, api_client):
        trainer, trainer_profile, chatroom = self._setup_trainer_with_chatroom()
        client_profile = ClientProfileFactory()
        ClientMembershipTrainerFactory(trainer=trainer_profile, client=client_profile)
        badge = BadgeFactory()

        api_client.force_authenticate(user=trainer)
        api_client.post(
            RECOGNITION_URL,
            {"slots": [_make_slot(client_profile, badge)]},
            format="json",
        )

        msg = Message.objects.filter(chatroom=chatroom).first()
        assert msg.message_type == "announcement"

    def test_more_than_3_slots_returns_400(self, api_client):
        trainer, trainer_profile, _ = self._setup_trainer_with_chatroom()
        clients = [ClientProfileFactory() for _ in range(4)]
        badges = [BadgeFactory() for _ in range(4)]
        for c in clients:
            ClientMembershipTrainerFactory(trainer=trainer_profile, client=c)

        slots = [_make_slot(clients[i], badges[i]) for i in range(4)]
        api_client.force_authenticate(user=trainer)
        resp = api_client.post(RECOGNITION_URL, {"slots": slots}, format="json")

        assert resp.status_code == 400

    def test_zero_slots_returns_400(self, api_client):
        trainer, _, _ = self._setup_trainer_with_chatroom()
        api_client.force_authenticate(user=trainer)
        resp = api_client.post(RECOGNITION_URL, {"slots": []}, format="json")
        assert resp.status_code == 400

    def test_client_not_in_community_returns_400(self, api_client):
        trainer, trainer_profile, _ = self._setup_trainer_with_chatroom()
        client_profile = ClientProfileFactory()  # no membership
        badge = BadgeFactory()

        api_client.force_authenticate(user=trainer)
        resp = api_client.post(
            RECOGNITION_URL,
            {"slots": [_make_slot(client_profile, badge)]},
            format="json",
        )

        assert resp.status_code == 400

    def test_client_role_returns_403(self, api_client):
        client_user = ClientFactory()
        ClientProfileFactory(user=client_user)
        badge = BadgeFactory()
        other_client = ClientProfileFactory()

        api_client.force_authenticate(user=client_user)
        resp = api_client.post(
            RECOGNITION_URL,
            {"slots": [_make_slot(other_client, badge)]},
            format="json",
        )

        assert resp.status_code == 403
