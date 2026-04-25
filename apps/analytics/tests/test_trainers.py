"""Tests for GET /api/v1/analytics/trainers/ (gym-only endpoint)."""

from datetime import date

import pytest

TRAINERS_URL = "/api/v1/analytics/trainers/"


@pytest.mark.django_db
class TestTrainersPermissions:
    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.get(TRAINERS_URL)
        assert resp.status_code == 401

    def test_client_returns_403(self, client_setup):
        _, _, api = client_setup
        resp = api.get(TRAINERS_URL)
        assert resp.status_code == 403

    def test_trainer_returns_403(self, trainer_setup):
        _, _, api = trainer_setup
        resp = api.get(TRAINERS_URL)
        assert resp.status_code == 403

    def test_gym_can_access(self, gym_setup):
        _, _, api = gym_setup
        resp = api.get(TRAINERS_URL)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestTrainersShape:
    def test_response_is_paginated(self, gym_setup):
        _, _, api = gym_setup
        resp = api.get(TRAINERS_URL)
        assert resp.data["status"] == "success"
        assert "data" in resp.data
        assert isinstance(resp.data["data"], list)
        assert "pagination" in resp.data["meta"]

    def test_each_item_has_required_keys(self, gym_setup):
        from apps.profiles.tests.factories import TrainerProfileFactory

        _, gym_profile, api = gym_setup
        TrainerProfileFactory(gym=gym_profile)

        resp = api.get(TRAINERS_URL, {"period": "all"})
        assert len(resp.data["data"]) == 1
        item = resp.data["data"][0]
        expected = {
            "trainer_id",
            "trainer_name",
            "active_clients",
            "total_sessions",
            "completed_sessions",
            "cancelled_sessions",
            "marketplace_products",
            "marketplace_enquiries",
        }
        assert expected.issubset(item.keys())


@pytest.mark.django_db
class TestTrainersData:
    def test_lists_only_gym_trainers(self, gym_setup, trainer_setup):
        from apps.profiles.tests.factories import TrainerProfileFactory

        _, gym_profile, api = gym_setup
        gym_trainer = TrainerProfileFactory(gym=gym_profile)

        resp = api.get(TRAINERS_URL, {"period": "all"})
        ids = [item["trainer_id"] for item in resp.data["data"]]
        assert gym_trainer.id in ids

    def test_independent_trainer_not_listed(self, gym_setup, trainer_setup):
        _, gym_profile, api = gym_setup
        _, other_profile, _ = trainer_setup  # independent trainer

        resp = api.get(TRAINERS_URL, {"period": "all"})
        ids = [item["trainer_id"] for item in resp.data["data"]]
        assert other_profile.id not in ids

    def test_trainer_stats_computed_correctly(self, gym_setup):
        from apps.clients.tests.factories import ClientMembershipTrainerFactory
        from apps.marketplace.models import Product, ProductEnquiry
        from apps.profiles.tests.factories import (
            ClientProfileFactory,
            TrainerProfileFactory,
        )
        from apps.sessions.tests.factories import (
            CancelledSessionFactory,
            SessionFactory,
        )

        _, gym_profile, api = gym_setup
        gym_trainer = TrainerProfileFactory(gym=gym_profile)
        today = date.today()

        # 2 active clients
        ClientMembershipTrainerFactory(trainer=gym_trainer, status="active")
        ClientMembershipTrainerFactory(trainer=gym_trainer, status="active")

        # 3 sessions: 2 completed, 1 cancelled
        SessionFactory(trainer=gym_trainer, session_date=today)
        SessionFactory(trainer=gym_trainer, session_date=today)
        CancelledSessionFactory(trainer=gym_trainer, session_date=today)

        # 1 product with 1 enquiry
        product = Product.objects.create(
            trainer=gym_trainer,
            name="Product",
            description="desc",
            category=Product.Category.PROGRAM,
            price="1000.00",
            status=Product.Status.ACTIVE,
        )
        client_profile = ClientProfileFactory()
        ProductEnquiry.objects.create(
            product=product,
            client=client_profile,
            message="Interested",
        )

        resp = api.get(TRAINERS_URL, {"period": "all"})
        item = resp.data["data"][0]

        assert item["active_clients"] == 2
        assert item["total_sessions"] == 3
        assert item["completed_sessions"] == 2
        assert item["cancelled_sessions"] == 1
        assert item["marketplace_products"] == 1
        assert item["marketplace_enquiries"] == 1

    def test_trainer_name_is_full_name(self, gym_setup):
        from apps.profiles.tests.factories import TrainerProfileFactory

        _, gym_profile, api = gym_setup
        TrainerProfileFactory(gym=gym_profile, full_name="Jane Smith")

        resp = api.get(TRAINERS_URL, {"period": "all"})
        item = resp.data["data"][0]
        assert item["trainer_name"] == "Jane Smith"

    def test_empty_list_when_no_gym_trainers(self, gym_setup):
        _, _, api = gym_setup
        resp = api.get(TRAINERS_URL, {"period": "all"})
        assert resp.data["data"] == []
