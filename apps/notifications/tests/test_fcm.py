"""
Tests for FCM helper and Celery tasks (Firebase mocked).
"""

from unittest.mock import MagicMock, patch

import pytest

from apps.notifications.models import FCMDevice


@pytest.mark.django_db
class TestSendPushToUser:
    def test_sends_to_active_tokens(self, trainer_user):
        FCMDevice.objects.create(
            user=trainer_user, token="valid_token", platform="android", is_active=True
        )
        mock_response = MagicMock()
        mock_response.success_count = 1
        mock_response.failure_count = 0
        mock_response.responses = [MagicMock(success=True)]

        with patch(
            "apps.notifications.fcm.messaging.send_each_for_multicast",
            return_value=mock_response,
        ) as mock_send:
            from apps.notifications.fcm import send_push_to_user

            send_push_to_user(trainer_user, "Hello", "World")
            mock_send.assert_called_once()

    def test_no_send_when_no_devices(self, trainer_user):
        with patch(
            "apps.notifications.fcm.messaging.send_each_for_multicast"
        ) as mock_send:
            from apps.notifications.fcm import send_push_to_user

            send_push_to_user(trainer_user, "Hello", "World")
            mock_send.assert_not_called()

    def test_deactivates_stale_token_on_failure(self, trainer_user):
        FCMDevice.objects.create(
            user=trainer_user, token="stale_token", platform="android", is_active=True
        )
        mock_exc = MagicMock()
        mock_exc.code = "registration-token-not-registered"
        mock_failed = MagicMock(success=False, exception=mock_exc)
        mock_response = MagicMock(
            success_count=0, failure_count=1, responses=[mock_failed]
        )

        with patch(
            "apps.notifications.fcm.messaging.send_each_for_multicast",
            return_value=mock_response,
        ):
            from apps.notifications.fcm import send_push_to_user

            send_push_to_user(trainer_user, "Hello", "World")

        device = FCMDevice.objects.get(user=trainer_user, token="stale_token")
        assert device.is_active is False

    def test_deactivates_invalid_registration_token(self, trainer_user):
        FCMDevice.objects.create(
            user=trainer_user,
            token="invalid_token",
            platform="ios",
            is_active=True,
        )
        mock_exc = MagicMock()
        mock_exc.code = "invalid-registration-token"
        mock_failed = MagicMock(success=False, exception=mock_exc)
        mock_response = MagicMock(
            success_count=0, failure_count=1, responses=[mock_failed]
        )

        with patch(
            "apps.notifications.fcm.messaging.send_each_for_multicast",
            return_value=mock_response,
        ):
            from apps.notifications.fcm import send_push_to_user

            send_push_to_user(trainer_user, "Hello", "World")

        device = FCMDevice.objects.get(user=trainer_user, token="invalid_token")
        assert device.is_active is False


@pytest.mark.django_db
class TestSendPushNotificationTask:
    def test_task_calls_send_push_to_user(self, trainer_user):
        with patch("apps.notifications.fcm.send_push_to_user") as mock_fn:
            from apps.notifications.tasks import send_push_notification

            send_push_notification(str(trainer_user.id), "Title", "Body", {})
            mock_fn.assert_called_once_with(trainer_user, "Title", "Body", {})

    def test_task_with_nonexistent_user_does_nothing(self):
        with patch("apps.notifications.fcm.send_push_to_user") as mock_fn:
            from apps.notifications.tasks import send_push_notification

            send_push_notification("00000000-0000-0000-0000-000000000000", "T", "B")
            mock_fn.assert_not_called()
