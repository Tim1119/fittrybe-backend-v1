"""Tests for GET /api/v1/analytics/overview/."""

from datetime import date

import pytest

OVERVIEW_URL = "/api/v1/analytics/overview/"


@pytest.mark.django_db
class TestOverviewPermissions:
    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.get(OVERVIEW_URL)
        assert resp.status_code == 401

    def test_client_returns_403(self, client_setup):
        _, _, api = client_setup
        resp = api.get(OVERVIEW_URL)
        assert resp.status_code == 403

    def test_trainer_can_access(self, trainer_setup):
        _, _, api = trainer_setup
        resp = api.get(OVERVIEW_URL)
        assert resp.status_code == 200
        assert resp.data["status"] == "success"

    def test_gym_can_access(self, gym_setup):
        _, _, api = gym_setup
        resp = api.get(OVERVIEW_URL)
        assert resp.status_code == 200
        assert resp.data["status"] == "success"


@pytest.mark.django_db
class TestOverviewShape:
    def test_response_has_all_required_keys(self, trainer_setup):
        _, _, api = trainer_setup
        resp = api.get(OVERVIEW_URL)
        data = resp.data["data"]
        expected_keys = {
            "total_active_clients",
            "total_sessions",
            "total_completed_sessions",
            "total_cancelled_sessions",
            "total_no_show_sessions",
            "new_clients_this_period",
            "marketplace_enquiries",
            "physical_sessions",
            "virtual_sessions",
            "period",
            "date_from",
            "date_to",
        }
        assert expected_keys.issubset(data.keys())

    def test_default_period_is_month(self, trainer_setup):
        _, _, api = trainer_setup
        resp = api.get(OVERVIEW_URL)
        assert resp.data["data"]["period"] == "month"


@pytest.mark.django_db
class TestOverviewTrainerData:
    def test_counts_active_clients_only(self, trainer_setup):
        from apps.clients.tests.factories import ClientMembershipTrainerFactory

        _, trainer_profile, api = trainer_setup
        ClientMembershipTrainerFactory(trainer=trainer_profile, status="active")
        ClientMembershipTrainerFactory(trainer=trainer_profile, status="active")
        ClientMembershipTrainerFactory(trainer=trainer_profile, status="lapsed")

        resp = api.get(OVERVIEW_URL, {"period": "all"})
        assert resp.data["data"]["total_active_clients"] == 2

    def test_counts_sessions_in_period(self, trainer_setup):
        from apps.sessions.tests.factories import SessionFactory

        _, trainer_profile, api = trainer_setup
        today = date.today()
        SessionFactory(trainer=trainer_profile, session_date=today)
        SessionFactory(trainer=trainer_profile, session_date=today)
        # session from far in the past — outside month
        SessionFactory(trainer=trainer_profile, session_date=date(2020, 1, 1))

        resp = api.get(OVERVIEW_URL, {"period": "month"})
        assert resp.data["data"]["total_sessions"] == 2

    def test_counts_session_statuses(self, trainer_setup):
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

        resp = api.get(OVERVIEW_URL, {"period": "all"})
        d = resp.data["data"]
        assert d["total_completed_sessions"] == 2
        assert d["total_cancelled_sessions"] == 1
        assert d["total_no_show_sessions"] == 1

    def test_counts_session_types(self, trainer_setup):
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

        resp = api.get(OVERVIEW_URL, {"period": "all"})
        d = resp.data["data"]
        assert d["physical_sessions"] == 1
        assert d["virtual_sessions"] == 1

    def test_new_clients_this_period_uses_created_at(self, trainer_setup):
        from apps.clients.tests.factories import ClientMembershipTrainerFactory

        _, trainer_profile, api = trainer_setup
        ClientMembershipTrainerFactory(trainer=trainer_profile)

        resp = api.get(OVERVIEW_URL, {"period": "month"})
        # Just created, so created_at is today → within month
        assert resp.data["data"]["new_clients_this_period"] == 1

    def test_marketplace_enquiries_counted(self, trainer_setup):
        from apps.marketplace.models import Product, ProductEnquiry
        from apps.profiles.tests.factories import ClientProfileFactory

        _, trainer_profile, api = trainer_setup
        product = Product.objects.create(
            trainer=trainer_profile,
            name="Test Product",
            description="desc",
            category=Product.Category.PROGRAM,
            price="5000.00",
            status=Product.Status.ACTIVE,
        )
        client_profile = ClientProfileFactory()
        ProductEnquiry.objects.create(
            product=product,
            client=client_profile,
            message="Interested",
        )

        resp = api.get(OVERVIEW_URL, {"period": "month"})
        assert resp.data["data"]["marketplace_enquiries"] == 1

    def test_trainer_only_sees_own_data(self, trainer_setup, trainer2_setup):
        from apps.clients.tests.factories import ClientMembershipTrainerFactory
        from apps.sessions.tests.factories import SessionFactory

        _, trainer_profile, api = trainer_setup
        _, other_profile, _ = trainer2_setup

        # Data belonging to other trainer
        SessionFactory(trainer=other_profile, session_date=date.today())
        ClientMembershipTrainerFactory(trainer=other_profile, status="active")

        resp = api.get(OVERVIEW_URL, {"period": "all"})
        d = resp.data["data"]
        assert d["total_sessions"] == 0
        assert d["total_active_clients"] == 0

    def test_custom_date_range_filter(self, trainer_setup):
        from apps.sessions.tests.factories import SessionFactory

        _, trainer_profile, api = trainer_setup
        SessionFactory(trainer=trainer_profile, session_date=date(2025, 1, 15))
        SessionFactory(trainer=trainer_profile, session_date=date(2025, 2, 15))
        SessionFactory(trainer=trainer_profile, session_date=date(2025, 3, 15))

        resp = api.get(
            OVERVIEW_URL,
            {"date_from": "2025-01-01", "date_to": "2025-02-28"},
        )
        assert resp.data["data"]["total_sessions"] == 2


@pytest.mark.django_db
class TestOverviewGymData:
    def test_gym_sessions_scoped_to_gym_trainers(self, gym_setup):
        from apps.profiles.tests.factories import TrainerProfileFactory
        from apps.sessions.tests.factories import SessionFactory

        _, gym_profile, api = gym_setup
        today = date.today()

        gym_trainer = TrainerProfileFactory(gym=gym_profile)
        SessionFactory(trainer=gym_trainer, session_date=today)

        resp = api.get(OVERVIEW_URL, {"period": "all"})
        assert resp.data["data"]["total_sessions"] == 1

    def test_gym_active_clients_scoped_to_gym(self, gym_setup):
        from apps.clients.tests.factories import ClientMembershipGymFactory

        _, gym_profile, api = gym_setup
        ClientMembershipGymFactory(gym=gym_profile, status="active")

        resp = api.get(OVERVIEW_URL, {"period": "all"})
        assert resp.data["data"]["total_active_clients"] == 1

    def test_gym_does_not_see_other_gym_data(self, gym_setup):
        from apps.clients.tests.factories import ClientMembershipGymFactory
        from apps.profiles.tests.factories import (
            GymProfileFactory,
            TrainerProfileFactory,
        )
        from apps.sessions.tests.factories import SessionFactory

        _, gym_profile, api = gym_setup
        other_gym = GymProfileFactory()
        other_trainer = TrainerProfileFactory(gym=other_gym)

        SessionFactory(trainer=other_trainer, session_date=date.today())
        ClientMembershipGymFactory(gym=other_gym, status="active")

        resp = api.get(OVERVIEW_URL, {"period": "all"})
        d = resp.data["data"]
        assert d["total_sessions"] == 0
        assert d["total_active_clients"] == 0
