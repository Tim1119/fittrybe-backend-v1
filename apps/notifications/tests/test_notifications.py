"""
Tests for in-app Notification list, mark-read, mark-all-read, unread-count.
"""

import pytest

from apps.notifications.models import Notification

LIST_URL = "/api/v1/notifications/"
UNREAD_COUNT_URL = "/api/v1/notifications/unread-count/"
READ_ALL_URL = "/api/v1/notifications/read-all/"


def mark_read_url(pk):
    return f"/api/v1/notifications/{pk}/read/"


def make_notification(recipient, sender=None, is_read=False, **kwargs):
    return Notification.objects.create(
        recipient=recipient,
        sender=sender,
        notification_type="chat_message",
        title="Test Title",
        body="Test body",
        is_read=is_read,
        **kwargs,
    )


@pytest.mark.django_db
class TestNotificationList:
    def test_list_returns_own_notifications(
        self, trainer_user, trainer_client, other_user
    ):
        make_notification(trainer_user, sender=other_user)
        make_notification(trainer_user, sender=other_user)
        resp = trainer_client.get(LIST_URL)
        assert resp.status_code == 200
        assert resp.data["status"] == "success"
        assert len(resp.data["data"]) == 2

    def test_list_excludes_other_users_notifications(
        self, trainer_user, trainer_client, other_user, other_client
    ):
        make_notification(other_user, sender=trainer_user)
        resp = trainer_client.get(LIST_URL)
        assert resp.status_code == 200
        assert len(resp.data["data"]) == 0

    def test_list_unauthenticated(self):
        from rest_framework.test import APIClient

        resp = APIClient().get(LIST_URL)
        assert resp.status_code == 401


@pytest.mark.django_db
class TestNotificationMarkRead:
    def test_mark_read_success(self, trainer_user, trainer_client, other_user):
        notif = make_notification(trainer_user, sender=other_user)
        resp = trainer_client.post(mark_read_url(notif.pk))
        assert resp.status_code == 200
        notif.refresh_from_db()
        assert notif.is_read is True
        assert notif.read_at is not None

    def test_mark_read_wrong_user(self, trainer_user, other_client):
        notif = make_notification(trainer_user)
        resp = other_client.post(mark_read_url(notif.pk))
        assert resp.status_code == 404

    def test_mark_read_unauthenticated(self, trainer_user):
        from rest_framework.test import APIClient

        notif = make_notification(trainer_user)
        resp = APIClient().post(mark_read_url(notif.pk))
        assert resp.status_code == 401


@pytest.mark.django_db
class TestNotificationMarkAllRead:
    def test_mark_all_read(self, trainer_user, trainer_client, other_user):
        make_notification(trainer_user, sender=other_user, is_read=False)
        make_notification(trainer_user, sender=other_user, is_read=False)
        make_notification(trainer_user, sender=other_user, is_read=True)
        resp = trainer_client.post(READ_ALL_URL)
        assert resp.status_code == 200
        assert resp.data["data"]["marked_count"] == 2
        assert (
            Notification.objects.filter(recipient=trainer_user, is_read=False).count()
            == 0
        )

    def test_mark_all_read_unauthenticated(self):
        from rest_framework.test import APIClient

        resp = APIClient().post(READ_ALL_URL)
        assert resp.status_code == 401


@pytest.mark.django_db
class TestUnreadCount:
    def test_unread_count_correct(self, trainer_user, trainer_client, other_user):
        make_notification(trainer_user, is_read=False)
        make_notification(trainer_user, is_read=False)
        make_notification(trainer_user, is_read=True)
        resp = trainer_client.get(UNREAD_COUNT_URL)
        assert resp.status_code == 200
        assert resp.data["data"]["unread_count"] == 2

    def test_unread_count_decrements_after_mark_read(
        self, trainer_user, trainer_client, other_user
    ):
        notif = make_notification(trainer_user, is_read=False)
        make_notification(trainer_user, is_read=False)
        # Mark one as read
        trainer_client.post(mark_read_url(notif.pk))
        resp = trainer_client.get(UNREAD_COUNT_URL)
        assert resp.data["data"]["unread_count"] == 1

    def test_unread_count_unauthenticated(self):
        from rest_framework.test import APIClient

        resp = APIClient().get(UNREAD_COUNT_URL)
        assert resp.status_code == 401
