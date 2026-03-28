"""
Tests for FCMDevice registration and unregistration endpoints.
"""

import pytest

from apps.notifications.models import FCMDevice

REGISTER_URL = "/api/v1/notifications/device/"


def unregister_url(token):
    return f"/api/v1/notifications/device/{token}/"


@pytest.mark.django_db
class TestFCMDeviceRegister:
    def test_register_device_success(self, trainer_user, trainer_client):
        resp = trainer_client.post(
            REGISTER_URL,
            {"token": "abc123token", "platform": "android"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["status"] == "success"
        assert FCMDevice.objects.filter(
            user=trainer_user, token="abc123token", is_active=True
        ).exists()

    def test_register_device_idempotent(self, trainer_user, trainer_client):
        """Re-registering same token just reactivates it."""
        FCMDevice.objects.create(
            user=trainer_user,
            token="abc123token",
            platform="android",
            is_active=False,
        )
        resp = trainer_client.post(
            REGISTER_URL,
            {"token": "abc123token", "platform": "android"},
            format="json",
        )
        assert resp.status_code == 200
        device = FCMDevice.objects.get(user=trainer_user, token="abc123token")
        assert device.is_active is True

    def test_register_missing_token(self, trainer_client):
        resp = trainer_client.post(
            REGISTER_URL,
            {"platform": "android"},
            format="json",
        )
        assert resp.status_code == 400

    def test_register_invalid_platform(self, trainer_client):
        resp = trainer_client.post(
            REGISTER_URL,
            {"token": "sometoken", "platform": "smartwatch"},
            format="json",
        )
        assert resp.status_code == 400

    def test_register_unauthenticated(self):
        from rest_framework.test import APIClient

        client = APIClient()
        resp = client.post(
            REGISTER_URL,
            {"token": "abc123token", "platform": "android"},
            format="json",
        )
        assert resp.status_code == 401


@pytest.mark.django_db
class TestFCMDeviceUnregister:
    def test_unregister_device_success(self, trainer_user, trainer_client):
        FCMDevice.objects.create(
            user=trainer_user,
            token="token_to_remove",
            platform="ios",
            is_active=True,
        )
        resp = trainer_client.delete(unregister_url("token_to_remove"))
        assert resp.status_code == 200
        device = FCMDevice.objects.get(user=trainer_user, token="token_to_remove")
        assert device.is_active is False

    def test_unregister_wrong_user(self, trainer_user, other_client):
        FCMDevice.objects.create(
            user=trainer_user,
            token="other_token",
            platform="android",
            is_active=True,
        )
        resp = other_client.delete(unregister_url("other_token"))
        assert resp.status_code == 404

    def test_unregister_nonexistent_token(self, trainer_client):
        resp = trainer_client.delete(unregister_url("nonexistent_token_xyz"))
        assert resp.status_code == 404

    def test_unregister_unauthenticated(self, trainer_user):
        from rest_framework.test import APIClient

        FCMDevice.objects.create(
            user=trainer_user,
            token="open_token",
            platform="web",
            is_active=True,
        )
        client = APIClient()
        resp = client.delete(unregister_url("open_token"))
        assert resp.status_code == 401
