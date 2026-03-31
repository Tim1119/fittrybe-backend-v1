"""
TDD tests for session logging endpoints.

GET/POST /api/v1/sessions/
GET/PUT/DELETE /api/v1/sessions/<id>/
GET /api/v1/sessions/upcoming/
GET /api/v1/sessions/stats/
"""

import datetime
from unittest.mock import patch

import pytest

from apps.accounts.tests.factories import ClientFactory, GymFactory, TrainerFactory
from apps.clients.tests.factories import ClientMembershipTrainerFactory
from apps.profiles.tests.factories import (
    ClientProfileFactory,
    GymProfileFactory,
    TrainerProfileFactory,
)
from apps.sessions.models import Session
from apps.sessions.tests.factories import (
    CancelledSessionFactory,
    NoShowSessionFactory,
    SessionFactory,
)

LIST_URL = "/api/v1/sessions/"
UPCOMING_URL = "/api/v1/sessions/upcoming/"
STATS_URL = "/api/v1/sessions/stats/"


def detail_url(pk):
    return f"/api/v1/sessions/{pk}/"


# ──────────────────────────────────────────────────────────────────────────────
# List / filter
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSessionListView:

    def test_trainer_sees_only_own_sessions(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        client_profile = ClientProfileFactory()
        SessionFactory(trainer=profile, client=client_profile)

        # Another trainer's session
        SessionFactory()

        api_client.force_authenticate(user=trainer)
        resp = api_client.get(LIST_URL)

        assert resp.status_code == 200
        assert resp.data["meta"]["pagination"]["total_count"] == 1

    def test_client_sees_only_own_sessions(self, api_client):
        client_user = ClientFactory()
        client_profile = ClientProfileFactory(user=client_user)
        SessionFactory(client=client_profile)

        # Another client's session
        SessionFactory()

        api_client.force_authenticate(user=client_user)
        resp = api_client.get(LIST_URL)

        assert resp.status_code == 200
        assert resp.data["meta"]["pagination"]["total_count"] == 1

    def test_gym_sees_sessions_from_all_gym_trainers(self, api_client):
        gym_user = GymFactory()
        gym_profile = GymProfileFactory(user=gym_user)

        trainer_profile_1 = TrainerProfileFactory(gym=gym_profile)
        trainer_profile_2 = TrainerProfileFactory(gym=gym_profile)
        SessionFactory(trainer=trainer_profile_1)
        SessionFactory(trainer=trainer_profile_2)

        # Another gym's session
        SessionFactory()

        api_client.force_authenticate(user=gym_user)
        resp = api_client.get(LIST_URL)

        assert resp.status_code == 200
        assert resp.data["meta"]["pagination"]["total_count"] == 2

    def test_filter_by_status(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        SessionFactory(trainer=profile, status=Session.Status.COMPLETED)
        CancelledSessionFactory(trainer=profile)

        api_client.force_authenticate(user=trainer)
        resp = api_client.get(LIST_URL, {"status": "cancelled"})

        assert resp.status_code == 200
        assert resp.data["meta"]["pagination"]["total_count"] == 1
        assert resp.data["data"][0]["status"] == "cancelled"

    def test_filter_by_client_id(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        client_a = ClientProfileFactory()
        client_b = ClientProfileFactory()
        SessionFactory(trainer=profile, client=client_a)
        SessionFactory(trainer=profile, client=client_b)

        api_client.force_authenticate(user=trainer)
        resp = api_client.get(LIST_URL, {"client_id": str(client_a.id)})

        assert resp.status_code == 200
        assert resp.data["meta"]["pagination"]["total_count"] == 1

    def test_filter_by_date_range(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        today = datetime.date.today()
        SessionFactory(trainer=profile, session_date=today)
        SessionFactory(
            trainer=profile,
            session_date=today - datetime.timedelta(days=30),
        )

        api_client.force_authenticate(user=trainer)
        resp = api_client.get(
            LIST_URL,
            {
                "date_from": str(today - datetime.timedelta(days=7)),
                "date_to": str(today),
            },
        )

        assert resp.status_code == 200
        assert resp.data["meta"]["pagination"]["total_count"] == 1

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(LIST_URL)
        assert resp.status_code == 401


# ──────────────────────────────────────────────────────────────────────────────
# Create
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSessionCreateView:

    def test_trainer_logs_session_for_own_client(self, api_client):
        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        client_profile = ClientProfileFactory()
        ClientMembershipTrainerFactory(trainer=trainer_profile, client=client_profile)

        api_client.force_authenticate(user=trainer)
        with patch("apps.sessions.views.check_session_badges") as mock_task:
            resp = api_client.post(
                LIST_URL,
                {
                    "client_id": str(client_profile.id),
                    "session_date": str(datetime.date.today()),
                    "status": "completed",
                },
                format="json",
            )

        assert resp.status_code == 201
        assert resp.data["data"]["status"] == "completed"
        mock_task.delay.assert_called_once()

    def test_session_defaults_to_status_completed(self, api_client):
        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        client_profile = ClientProfileFactory()
        ClientMembershipTrainerFactory(trainer=trainer_profile, client=client_profile)

        api_client.force_authenticate(user=trainer)
        with patch("apps.sessions.views.check_session_badges"):
            resp = api_client.post(
                LIST_URL,
                {
                    "client_id": str(client_profile.id),
                    "session_date": str(datetime.date.today()),
                },
                format="json",
            )

        assert resp.status_code == 201
        assert resp.data["data"]["status"] == "completed"

    def test_client_not_in_community_returns_400(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        client_profile = ClientProfileFactory()

        api_client.force_authenticate(user=trainer)
        resp = api_client.post(
            LIST_URL,
            {
                "client_id": str(client_profile.id),
                "session_date": str(datetime.date.today()),
            },
            format="json",
        )

        assert resp.status_code == 400

    def test_client_role_cannot_create_session(self, api_client):
        client_user = ClientFactory()
        ClientProfileFactory(user=client_user)

        api_client.force_authenticate(user=client_user)
        resp = api_client.post(
            LIST_URL,
            {
                "client_id": str(client_user.id),
                "session_date": str(datetime.date.today()),
            },
            format="json",
        )

        assert resp.status_code == 403

    def test_check_session_badges_not_called_for_cancelled(self, api_client):
        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        client_profile = ClientProfileFactory()
        ClientMembershipTrainerFactory(trainer=trainer_profile, client=client_profile)

        api_client.force_authenticate(user=trainer)
        with patch("apps.sessions.views.check_session_badges") as mock_task:
            resp = api_client.post(
                LIST_URL,
                {
                    "client_id": str(client_profile.id),
                    "session_date": str(datetime.date.today()),
                    "status": "cancelled",
                },
                format="json",
            )

        assert resp.status_code == 201
        mock_task.delay.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# Detail — get / update / delete
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSessionDetailView:

    def test_trainer_updates_own_session(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        session = SessionFactory(trainer=profile, status=Session.Status.COMPLETED)

        api_client.force_authenticate(user=trainer)
        resp = api_client.put(
            detail_url(session.id),
            {"status": "cancelled"},
            format="json",
        )

        assert resp.status_code == 200
        assert resp.data["data"]["status"] == "cancelled"

    def test_trainer_cannot_update_another_trainers_session(self, api_client):
        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer)
        session = SessionFactory()

        api_client.force_authenticate(user=trainer)
        resp = api_client.put(
            detail_url(session.id),
            {"status": "cancelled"},
            format="json",
        )

        assert resp.status_code == 403

    def test_soft_delete_removes_from_list(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        session = SessionFactory(trainer=profile)

        api_client.force_authenticate(user=trainer)
        resp = api_client.delete(detail_url(session.id))

        assert resp.status_code == 200
        session.refresh_from_db()
        assert session.deleted_at is not None

        list_resp = api_client.get(LIST_URL)
        assert list_resp.data["meta"]["pagination"]["total_count"] == 0


# ──────────────────────────────────────────────────────────────────────────────
# Upcoming
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUpcomingSessionsView:

    def test_upcoming_returns_future_sessions_only(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        today = datetime.date.today()

        # Future
        SessionFactory(trainer=profile, session_date=today + datetime.timedelta(days=1))
        SessionFactory(trainer=profile, session_date=today + datetime.timedelta(days=2))

        # Past
        SessionFactory(trainer=profile, session_date=today - datetime.timedelta(days=1))

        api_client.force_authenticate(user=trainer)
        resp = api_client.get(UPCOMING_URL)

        assert resp.status_code == 200
        assert len(resp.data["data"]) == 2

    def test_upcoming_returns_max_5(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        today = datetime.date.today()

        for i in range(1, 8):
            SessionFactory(
                trainer=profile,
                session_date=today + datetime.timedelta(days=i),
            )

        api_client.force_authenticate(user=trainer)
        resp = api_client.get(UPCOMING_URL)

        assert resp.status_code == 200
        assert len(resp.data["data"]) == 5

    def test_upcoming_ordered_ascending(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        today = datetime.date.today()

        SessionFactory(trainer=profile, session_date=today + datetime.timedelta(days=3))
        SessionFactory(trainer=profile, session_date=today + datetime.timedelta(days=1))

        api_client.force_authenticate(user=trainer)
        resp = api_client.get(UPCOMING_URL)

        dates = [s["session_date"] for s in resp.data["data"]]
        assert dates == sorted(dates)


# ──────────────────────────────────────────────────────────────────────────────
# Stats
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSessionStatsView:

    def test_stats_returns_correct_counts(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        SessionFactory(trainer=profile, status=Session.Status.COMPLETED)
        SessionFactory(trainer=profile, status=Session.Status.COMPLETED)
        CancelledSessionFactory(trainer=profile)
        NoShowSessionFactory(trainer=profile)

        api_client.force_authenticate(user=trainer)
        resp = api_client.get(STATS_URL)

        assert resp.status_code == 200
        data = resp.data["data"]
        assert data["total"] == 2
        assert data["completed"] == 2
        assert data["cancelled"] == 1
        assert data["no_show"] == 1

    def test_stats_growth_percent_zero_when_last_month_zero(self, api_client):
        trainer = TrainerFactory()
        profile = TrainerProfileFactory(user=trainer)
        today = datetime.date.today()
        SessionFactory(
            trainer=profile,
            status=Session.Status.COMPLETED,
            session_date=today,
        )

        api_client.force_authenticate(user=trainer)
        resp = api_client.get(STATS_URL)

        assert resp.status_code == 200
        assert resp.data["data"]["growth_percent"] == 0

    def test_stats_client_forbidden(self, api_client):
        client_user = ClientFactory()
        ClientProfileFactory(user=client_user)
        api_client.force_authenticate(user=client_user)
        resp = api_client.get(STATS_URL)
        assert resp.status_code == 403
