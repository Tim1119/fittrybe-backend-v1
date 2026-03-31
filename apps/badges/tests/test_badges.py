"""
TDD tests for badge CRUD + assignment endpoints.

GET/POST    /api/v1/badges/
GET         /api/v1/badges/<id>/
POST        /api/v1/badges/clients/<client_id>/assign/
GET         /api/v1/badges/clients/<client_id>/
GET         /api/v1/badges/assignments/
"""

from unittest.mock import patch

import pytest

from apps.accounts.tests.factories import ClientFactory, TrainerFactory
from apps.badges.models import Badge, BadgeAssignment
from apps.badges.tests.factories import BadgeAssignmentFactory, BadgeFactory
from apps.clients.tests.factories import ClientMembershipTrainerFactory
from apps.profiles.tests.factories import ClientProfileFactory, TrainerProfileFactory

LIST_URL = "/api/v1/badges/"
ASSIGNMENTS_URL = "/api/v1/badges/assignments/"


def detail_url(pk):
    return f"/api/v1/badges/{pk}/"


def assign_url(client_id):
    return f"/api/v1/badges/clients/{client_id}/assign/"


def client_badges_url(client_id):
    return f"/api/v1/badges/clients/{client_id}/"


# ──────────────────────────────────────────────────────────────────────────────
# System badge seeding
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSystemBadgeSeeding:

    def test_all_13_system_badges_seeded(self):
        assert Badge.objects.filter(is_system=True).count() == 13

    def test_milestone_badges_have_thresholds(self):
        milestones = Badge.objects.filter(badge_type="milestone", is_system=True)
        assert milestones.count() == 5
        thresholds = set(milestones.values_list("milestone_threshold", flat=True))
        assert thresholds == {1, 5, 10, 25, 50}

    def test_manual_badges_have_no_threshold(self):
        manual = Badge.objects.filter(badge_type="manual", is_system=True)
        assert manual.count() == 5
        assert all(b.milestone_threshold is None for b in manual)

    def test_weekly_top_badges_seeded(self):
        wt = Badge.objects.filter(badge_type="weekly_top", is_system=True)
        assert wt.count() == 3


# ──────────────────────────────────────────────────────────────────────────────
# Badge list / detail (public)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBadgeListView:

    def test_get_all_badges_public(self, api_client):
        resp = api_client.get(LIST_URL)
        assert resp.status_code == 200
        # At least the 13 seeded system badges
        assert resp.data["meta"]["pagination"]["total_count"] >= 13

    def test_filter_by_badge_type(self, api_client):
        resp = api_client.get(LIST_URL, {"badge_type": "milestone"})
        assert resp.status_code == 200
        for badge in resp.data["data"]:
            assert badge["badge_type"] == "milestone"

    def test_get_badge_detail_public(self, api_client):
        badge = Badge.objects.filter(is_system=True).first()
        resp = api_client.get(detail_url(badge.id))
        assert resp.status_code == 200
        assert resp.data["data"]["name"] == badge.name


@pytest.mark.django_db
class TestBadgeCreateView:

    def test_trainer_creates_custom_badge(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)

        resp = api_client.post(
            LIST_URL,
            {
                "name": "Power House",
                "badge_type": "manual",
                "description": "Beast mode.",
            },
            format="json",
        )

        assert resp.status_code == 201
        assert resp.data["data"]["is_system"] is False

    def test_is_system_always_forced_false(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)

        resp = api_client.post(
            LIST_URL,
            {
                "name": "Sneaky System Badge",
                "badge_type": "manual",
                "is_system": True,
            },
            format="json",
        )

        assert resp.status_code == 201
        assert resp.data["data"]["is_system"] is False

    def test_milestone_threshold_requires_milestone_type(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        api_client.force_authenticate(user=trainer)

        resp = api_client.post(
            LIST_URL,
            {
                "name": "Bad Badge",
                "badge_type": "manual",
                "milestone_threshold": 5,
            },
            format="json",
        )

        assert resp.status_code == 400

    def test_client_cannot_create_badge(self, api_client):
        client_user = ClientFactory()
        ClientProfileFactory(user=client_user)
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(
            LIST_URL,
            {"name": "Sneaky Badge", "badge_type": "manual"},
            format="json",
        )

        assert resp.status_code == 403


# ──────────────────────────────────────────────────────────────────────────────
# Badge assignment
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBadgeAssignView:

    def test_trainer_assigns_badge_to_own_client(self, api_client):
        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        client_profile = ClientProfileFactory()
        ClientMembershipTrainerFactory(trainer=trainer_profile, client=client_profile)
        badge = BadgeFactory()

        api_client.force_authenticate(user=trainer)
        with (
            patch("apps.badges.views.post_badge_to_chatroom") as mock_chat,
            patch("apps.badges.views.send_push_notification") as mock_push,
        ):
            resp = api_client.post(
                assign_url(client_profile.id),
                {
                    "badge_id": badge.id,
                    "note": "Great work!",
                    "post_to_chatroom": True,
                },
                format="json",
            )

        assert resp.status_code == 201
        assert BadgeAssignment.objects.filter(
            client=client_profile, badge=badge
        ).exists()
        mock_chat.delay.assert_called_once()
        mock_push.delay.assert_called_once()

    def test_client_not_in_community_returns_403(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        client_profile = ClientProfileFactory()
        badge = BadgeFactory()

        api_client.force_authenticate(user=trainer)
        resp = api_client.post(
            assign_url(client_profile.id),
            {"badge_id": badge.id},
            format="json",
        )

        assert resp.status_code == 403

    def test_badge_not_found_returns_404(self, api_client):
        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        client_profile = ClientProfileFactory()
        ClientMembershipTrainerFactory(trainer=trainer_profile, client=client_profile)

        api_client.force_authenticate(user=trainer)
        resp = api_client.post(
            assign_url(client_profile.id),
            {"badge_id": 999999},
            format="json",
        )

        assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# Client badge list
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestClientBadgeListView:

    def test_client_views_own_badges(self, api_client):
        client_user = ClientFactory()
        client_profile = ClientProfileFactory(user=client_user)
        BadgeAssignmentFactory(client=client_profile)
        BadgeAssignmentFactory(client=client_profile)

        api_client.force_authenticate(user=client_user)
        resp = api_client.get(client_badges_url(client_profile.id))

        assert resp.status_code == 200
        assert resp.data["meta"]["pagination"]["total_count"] == 2

    def test_trainer_views_own_clients_badges(self, api_client):
        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        client_profile = ClientProfileFactory()
        ClientMembershipTrainerFactory(trainer=trainer_profile, client=client_profile)
        BadgeAssignmentFactory(client=client_profile, trainer=trainer_profile)

        api_client.force_authenticate(user=trainer)
        resp = api_client.get(client_badges_url(client_profile.id))

        assert resp.status_code == 200
        assert resp.data["meta"]["pagination"]["total_count"] == 1

    def test_trainer_cannot_view_another_trainers_client_badges(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        # Client belongs to a different trainer
        client_profile = ClientProfileFactory()
        other_trainer = TrainerProfileFactory()
        ClientMembershipTrainerFactory(trainer=other_trainer, client=client_profile)

        api_client.force_authenticate(user=trainer)
        resp = api_client.get(client_badges_url(client_profile.id))

        assert resp.status_code == 403


# ──────────────────────────────────────────────────────────────────────────────
# Assignment list
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBadgeAssignmentListView:

    def test_trainer_sees_own_assignments(self, api_client):
        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        BadgeAssignmentFactory(trainer=trainer_profile)
        BadgeAssignmentFactory(trainer=trainer_profile)
        # Another trainer's assignment
        BadgeAssignmentFactory()

        api_client.force_authenticate(user=trainer)
        resp = api_client.get(ASSIGNMENTS_URL)

        assert resp.status_code == 200
        assert resp.data["meta"]["pagination"]["total_count"] == 2


# ──────────────────────────────────────────────────────────────────────────────
# post_badge_to_chatroom task
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPostBadgeToChatroom:

    def test_posts_announcement_to_trainer_chatroom(self):
        from apps.badges.tasks import post_badge_to_chatroom
        from apps.badges.tests.factories import BadgeAssignmentFactory
        from apps.chat.models import Chatroom, Message

        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        chatroom = Chatroom.objects.create(trainer=trainer_profile, name="Test Room")
        client_profile = ClientProfileFactory()
        assignment = BadgeAssignmentFactory(
            trainer=trainer_profile,
            client=client_profile,
            assigned_by=trainer,
        )

        post_badge_to_chatroom(str(assignment.id))

        msg = Message.objects.filter(chatroom=chatroom).first()
        assert msg is not None
        assert msg.message_type == "announcement"
        assert assignment.badge.name in msg.content
