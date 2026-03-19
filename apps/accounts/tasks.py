"""
Celery tasks for accounts app — async email dispatch.
"""

from celery import shared_task
from django.contrib.auth import get_user_model

User = get_user_model()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_verification_email_task(self, user_id):
    try:
        user = User.objects.get(id=user_id)
        from apps.accounts.emails import send_verification_email

        send_verification_email(user)
    except User.DoesNotExist:
        pass
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email_task(self, user_id):
    try:
        user = User.objects.get(id=user_id)
        from apps.accounts.emails import send_password_reset_email

        send_password_reset_email(user)
    except User.DoesNotExist:
        pass
    except Exception as exc:
        raise self.retry(exc=exc)
