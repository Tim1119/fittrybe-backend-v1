"""
TDD tests for the badge leaderboard endpoint.

GET /api/v1/badges/leaderboard/
"""

import datetime

import pytest

from apps.accounts.tests.factories import GymFactory, TrainerFactory
from apps.profiles.tests.factories import (
    ClientProfileFactory,
    GymProfileFactory,
    TrainerProfileFactory,
)
from apps.sessions.tests.factories import SessionFactory

LEADERBOARD_URL = "/api/v1/badges/leaderboard/"


@pytest.mark.django_db
class TestBadgeLeaderboardView:

    def test_clients_ranked_by_sessions_last_7_days(self, api_client):
        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        today = datetime.date.today()

        client_a = ClientProfileFactory()
        client_b = ClientProfileFactory()

        # client_a: 3 sessions this week
        for i in range(3):
            SessionFactory(
                trainer=trainer_profile,
                client=client_a,
                status="completed",
                session_date=today - datetime.timedelta(days=i),
            )
        # client_b: 1 session this week
        SessionFactory(
            trainer=trainer_profile,
            client=client_b,
            status="completed",
            session_date=today,
        )

        api_client.force_authenticate(user=trainer)
        resp = api_client.get(LEADERBOARD_URL)

        assert resp.status_code == 200
        data = resp.data["data"]
        assert data[0]["sessions_this_week"] == 3
        assert data[1]["sessions_this_week"] == 1

    def test_leaderboard_max_10(self, api_client):
        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        today = datetime.date.today()

        for _ in range(15):
            client = ClientProfileFactory()
            SessionFactory(
                trainer=trainer_profile,
                client=client,
                status="completed",
                session_date=today,
            )

        api_client.force_authenticate(user=trainer)
        resp = api_client.get(LEADERBOARD_URL)

        assert resp.status_code == 200
        assert len(resp.data["data"]) == 10

    def test_only_completed_sessions_counted(self, api_client):
        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        today = datetime.date.today()
        client = ClientProfileFactory()

        SessionFactory(
            trainer=trainer_profile,
            client=client,
            status="completed",
            session_date=today,
        )
        SessionFactory(
            trainer=trainer_profile,
            client=client,
            status="cancelled",
            session_date=today,
        )

        api_client.force_authenticate(user=trainer)
        resp = api_client.get(LEADERBOARD_URL)

        assert resp.status_code == 200
        assert resp.data["data"][0]["sessions_this_week"] == 1

    def test_only_sessions_from_last_7_days_counted(self, api_client):
        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        today = datetime.date.today()
        client = ClientProfileFactory()

        # Old session — should not count
        SessionFactory(
            trainer=trainer_profile,
            client=client,
            status="completed",
            session_date=today - datetime.timedelta(days=10),
        )

        api_client.force_authenticate(user=trainer)
        resp = api_client.get(LEADERBOARD_URL)

        assert resp.status_code == 200
        assert len(resp.data["data"]) == 0

    def test_gym_leaderboard_spans_all_gym_trainers(self, api_client):
        gym_user = GymFactory()
        gym_profile = GymProfileFactory(user=gym_user)
        today = datetime.date.today()

        trainer_a = TrainerProfileFactory(gym=gym_profile)
        trainer_b = TrainerProfileFactory(gym=gym_profile)

        client_a = ClientProfileFactory()
        client_b = ClientProfileFactory()

        SessionFactory(
            trainer=trainer_a, client=client_a, status="completed", session_date=today
        )
        SessionFactory(
            trainer=trainer_b, client=client_b, status="completed", session_date=today
        )

        api_client.force_authenticate(user=gym_user)
        resp = api_client.get(LEADERBOARD_URL)

        assert resp.status_code == 200
        assert len(resp.data["data"]) == 2

    def test_client_cannot_access_leaderboard(self, api_client):
        from apps.accounts.tests.factories import ClientFactory
        from apps.profiles.tests.factories import ClientProfileFactory

        client_user = ClientFactory()
        ClientProfileFactory(user=client_user)
        api_client.force_authenticate(user=client_user)
        resp = api_client.get(LEADERBOARD_URL)
        assert resp.status_code == 403
