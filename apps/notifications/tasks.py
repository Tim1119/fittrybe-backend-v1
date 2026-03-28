"""
Notifications Celery tasks.
"""

from celery import shared_task


@shared_task(bind=True, max_retries=3)
def send_push_notification(self, user_id, title, body, data=None):
    """
    Async FCM push notification task.
    Called from consumers and views via .delay()
    """
    from apps.accounts.models import User

    from .fcm import send_push_to_user

    try:
        user = User.objects.get(id=user_id, is_active=True)
        send_push_to_user(user, title, body, data)
    except User.DoesNotExist:
        pass
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_push_to_multiple(self, user_ids, title, body, data=None):
    """Send push to a list of user IDs."""
    from apps.accounts.models import User

    from .fcm import send_push_to_user

    users = User.objects.filter(id__in=user_ids, is_active=True)
    for user in users:
        send_push_to_user(user, title, body, data)
