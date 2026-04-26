"""Tests for tracker addon activate/status endpoints."""

import pytest

ADDON_ACTIVATE_URL = "/api/v1/trackers/addon/activate/"
ADDON_STATUS_URL = "/api/v1/trackers/addon/status/"


@pytest.mark.django_db
class TestAddonStatus:
    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.get(ADDON_STATUS_URL)
        assert resp.status_code == 401

    def test_trainer_returns_403(self, trainer_user):
        _, _, api = trainer_user
        resp = api.get(ADDON_STATUS_URL)
        assert resp.status_code == 403

    def test_client_without_addon_returns_false(self, client_no_addon):
        _, _, api = client_no_addon
        resp = api.get(ADDON_STATUS_URL)
        assert resp.status_code == 200
        assert resp.data["status"] == "success"
        assert resp.data["data"]["addon_active"] is False

    def test_client_with_addon_returns_true(self, client_with_addon):
        _, _, api = client_with_addon
        resp = api.get(ADDON_STATUS_URL)
        assert resp.status_code == 200
        assert resp.data["data"]["addon_active"] is True


@pytest.mark.django_db
class TestAddonActivate:
    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.post(ADDON_ACTIVATE_URL)
        assert resp.status_code == 401

    def test_trainer_returns_403(self, trainer_user):
        _, _, api = trainer_user
        resp = api.post(ADDON_ACTIVATE_URL)
        assert resp.status_code == 403

    def test_client_can_activate(self, client_no_addon):
        _, _, api = client_no_addon
        resp = api.post(ADDON_ACTIVATE_URL)
        assert resp.status_code == 200
        assert resp.data["data"]["addon_active"] is True

    def test_activate_persists_in_db(self, client_no_addon):
        user, profile, api = client_no_addon
        api.post(ADDON_ACTIVATE_URL)
        profile.refresh_from_db()
        assert profile.tracker_addon_active is True

    def test_status_returns_true_after_activate(self, client_no_addon):
        _, _, api = client_no_addon
        api.post(ADDON_ACTIVATE_URL)
        resp = api.get(ADDON_STATUS_URL)
        assert resp.data["data"]["addon_active"] is True
