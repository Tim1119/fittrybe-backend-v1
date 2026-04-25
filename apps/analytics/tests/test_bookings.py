"""Tests for GET /api/v1/analytics/bookings/."""

from datetime import date

import pytest

BOOKINGS_URL = "/api/v1/analytics/bookings/"


@pytest.mark.django_db
class TestBookingsPermissions:
    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.get(BOOKINGS_URL)
        assert resp.status_code == 401

    def test_client_returns_403(self, client_setup):
        _, _, api = client_setup
        resp = api.get(BOOKINGS_URL)
        assert resp.status_code == 403

    def test_trainer_can_access(self, trainer_setup):
        _, _, api = trainer_setup
        resp = api.get(BOOKINGS_URL)
        assert resp.status_code == 200

    def test_gym_can_access(self, gym_setup):
        _, _, api = gym_setup
        resp = api.get(BOOKINGS_URL)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestBookingsShape:
    def test_response_has_all_required_keys(self, trainer_setup):
        _, _, api = trainer_setup
        resp = api.get(BOOKINGS_URL)
        data = resp.data["data"]
        expected = {
            "total",
            "completed",
            "cancelled",
            "no_show",
            "physical",
            "virtual",
            "completion_rate",
            "by_period",
            "period",
        }
        assert expected.issubset(data.keys())

    def test_by_period_is_list(self, trainer_setup):
        _, _, api = trainer_setup
        resp = api.get(BOOKINGS_URL)
        assert isinstance(resp.data["data"]["by_period"], list)


@pytest.mark.django_db
class TestBookingsData:
    def test_counts_are_correct(self, trainer_setup):
        from apps.sessions.tests.factories import (
            CancelledSessionFactory,
            NoShowSessionFactory,
            SessionFactory,
        )

        _, trainer_profile, api = trainer_setup
        today = date.today()
        SessionFactory(trainer=trainer_profile, session_date=today)
        SessionFactory(trainer=trainer_profile, session_date=today)
        CancelledSessionFactory(trainer=trainer_profile, session_date=today)
        NoShowSessionFactory(trainer=trainer_profile, session_date=today)

        resp = api.get(BOOKINGS_URL, {"period": "all"})
        d = resp.data["data"]
        assert d["total"] == 4
        assert d["completed"] == 2
        assert d["cancelled"] == 1
        assert d["no_show"] == 1

    def test_completion_rate_calculated_correctly(self, trainer_setup):
        from apps.sessions.tests.factories import (
            CancelledSessionFactory,
            SessionFactory,
        )

        _, trainer_profile, api = trainer_setup
        today = date.today()
        # 4 completed, 1 cancelled → rate = 4/5 * 100 = 80.0
        for _ in range(4):
            SessionFactory(trainer=trainer_profile, session_date=today)
        CancelledSessionFactory(trainer=trainer_profile, session_date=today)

        resp = api.get(BOOKINGS_URL, {"period": "all"})
        assert resp.data["data"]["completion_rate"] == 80.0

    def test_completion_rate_zero_when_no_sessions(self, trainer_setup):
        _, _, api = trainer_setup
        resp = api.get(BOOKINGS_URL, {"period": "all"})
        assert resp.data["data"]["completion_rate"] == 0.0

    def test_session_types_counted(self, trainer_setup):
        from apps.sessions.models import Session
        from apps.sessions.tests.factories import SessionFactory

        _, trainer_profile, api = trainer_setup
        today = date.today()
        SessionFactory(
            trainer=trainer_profile,
            session_date=today,
            session_type=Session.SessionType.PHYSICAL,
        )
        SessionFactory(
            trainer=trainer_profile,
            session_date=today,
            session_type=Session.SessionType.VIRTUAL,
        )

        resp = api.get(BOOKINGS_URL, {"period": "all"})
        d = resp.data["data"]
        assert d["physical"] == 1
        assert d["virtual"] == 1

    def test_by_period_groups_by_week_for_month(self, trainer_setup):
        from apps.sessions.tests.factories import SessionFactory

        _, trainer_profile, api = trainer_setup
        # Sessions on specific dates in Jan 2025 (two different weeks)
        SessionFactory(trainer=trainer_profile, session_date=date(2025, 1, 6))
        SessionFactory(trainer=trainer_profile, session_date=date(2025, 1, 13))

        resp = api.get(
            BOOKINGS_URL,
            {"date_from": "2025-01-01", "date_to": "2025-01-31"},
        )
        by_period = resp.data["data"]["by_period"]
        assert isinstance(by_period, list)
        assert len(by_period) >= 1
        # Each item has label and count
        for item in by_period:
            assert "label" in item
            assert "count" in item

    def test_by_period_groups_by_month_for_year(self, trainer_setup):
        from apps.sessions.tests.factories import SessionFactory

        _, trainer_profile, api = trainer_setup
        SessionFactory(trainer=trainer_profile, session_date=date(2025, 1, 15))
        SessionFactory(trainer=trainer_profile, session_date=date(2025, 3, 15))

        resp = api.get(
            BOOKINGS_URL,
            {"date_from": "2025-01-01", "date_to": "2025-12-31"},
        )
        by_period = resp.data["data"]["by_period"]
        assert len(by_period) >= 2

    def test_gym_bookings_scoped_to_gym_trainers(self, gym_setup):
        from apps.profiles.tests.factories import TrainerProfileFactory
        from apps.sessions.tests.factories import SessionFactory

        _, gym_profile, api = gym_setup
        gym_trainer = TrainerProfileFactory(gym=gym_profile)
        SessionFactory(trainer=gym_trainer, session_date=date.today())

        resp = api.get(BOOKINGS_URL, {"period": "all"})
        assert resp.data["data"]["total"] == 1

    def test_trainer_only_sees_own_bookings(self, trainer_setup, trainer2_setup):
        from apps.sessions.tests.factories import SessionFactory

        _, trainer_profile, api = trainer_setup
        _, other_profile, _ = trainer2_setup
        SessionFactory(trainer=other_profile, session_date=date.today())

        resp = api.get(BOOKINGS_URL, {"period": "all"})
        assert resp.data["data"]["total"] == 0
