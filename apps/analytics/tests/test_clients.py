"""Tests for GET /api/v1/analytics/clients/."""

import pytest

CLIENTS_URL = "/api/v1/analytics/clients/"


@pytest.mark.django_db
class TestClientsPermissions:
    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.get(CLIENTS_URL)
        assert resp.status_code == 401

    def test_client_returns_403(self, client_setup):
        _, _, api = client_setup
        resp = api.get(CLIENTS_URL)
        assert resp.status_code == 403

    def test_trainer_can_access(self, trainer_setup):
        _, _, api = trainer_setup
        resp = api.get(CLIENTS_URL)
        assert resp.status_code == 200

    def test_gym_can_access(self, gym_setup):
        _, _, api = gym_setup
        resp = api.get(CLIENTS_URL)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestClientsShape:
    def test_response_has_all_required_keys(self, trainer_setup):
        _, _, api = trainer_setup
        resp = api.get(CLIENTS_URL)
        data = resp.data["data"]
        expected = {
            "total_active",
            "total_lapsed",
            "total_pending",
            "new_this_period",
            "retention_rate",
            "period",
        }
        assert expected.issubset(data.keys())


@pytest.mark.django_db
class TestClientsTrainerData:
    def test_counts_by_status(self, trainer_setup):
        from apps.clients.tests.factories import ClientMembershipTrainerFactory

        _, trainer_profile, api = trainer_setup
        ClientMembershipTrainerFactory(trainer=trainer_profile, status="active")
        ClientMembershipTrainerFactory(trainer=trainer_profile, status="active")
        ClientMembershipTrainerFactory(trainer=trainer_profile, status="lapsed")
        ClientMembershipTrainerFactory(trainer=trainer_profile, status="pending")

        resp = api.get(CLIENTS_URL, {"period": "all"})
        d = resp.data["data"]
        assert d["total_active"] == 2
        assert d["total_lapsed"] == 1
        assert d["total_pending"] == 1

    def test_new_this_period_counts_recent_memberships(self, trainer_setup):
        from apps.clients.tests.factories import ClientMembershipTrainerFactory

        _, trainer_profile, api = trainer_setup
        ClientMembershipTrainerFactory(trainer=trainer_profile)
        ClientMembershipTrainerFactory(trainer=trainer_profile)

        resp = api.get(CLIENTS_URL, {"period": "month"})
        assert resp.data["data"]["new_this_period"] == 2

    def test_retention_rate_calculated_correctly(self, trainer_setup):
        from apps.clients.tests.factories import ClientMembershipTrainerFactory

        _, trainer_profile, api = trainer_setup
        # 4 active, 1 lapsed → rate = 4/(4+1) * 100 = 80.0
        for _ in range(4):
            ClientMembershipTrainerFactory(trainer=trainer_profile, status="active")
        ClientMembershipTrainerFactory(trainer=trainer_profile, status="lapsed")

        resp = api.get(CLIENTS_URL, {"period": "all"})
        assert resp.data["data"]["retention_rate"] == 80.0

    def test_retention_rate_zero_when_no_clients(self, trainer_setup):
        _, _, api = trainer_setup
        resp = api.get(CLIENTS_URL, {"period": "all"})
        assert resp.data["data"]["retention_rate"] == 0.0

    def test_trainer_only_sees_own_clients(self, trainer_setup, trainer2_setup):
        from apps.clients.tests.factories import ClientMembershipTrainerFactory

        _, trainer_profile, api = trainer_setup
        _, other_profile, _ = trainer2_setup
        ClientMembershipTrainerFactory(trainer=other_profile, status="active")

        resp = api.get(CLIENTS_URL, {"period": "all"})
        d = resp.data["data"]
        assert d["total_active"] == 0
        assert d["total_lapsed"] == 0


@pytest.mark.django_db
class TestClientsGymData:
    def test_gym_counts_scoped_to_gym(self, gym_setup):
        from apps.clients.tests.factories import ClientMembershipGymFactory

        _, gym_profile, api = gym_setup
        ClientMembershipGymFactory(gym=gym_profile, status="active")
        ClientMembershipGymFactory(gym=gym_profile, status="lapsed")

        resp = api.get(CLIENTS_URL, {"period": "all"})
        d = resp.data["data"]
        assert d["total_active"] == 1
        assert d["total_lapsed"] == 1
