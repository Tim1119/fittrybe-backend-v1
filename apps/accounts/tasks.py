"""
Celery tasks for accounts app — async email dispatch.
"""

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)


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


@shared_task
def send_otp_verification_email_task(user_id):
    from apps.accounts.emails import send_otp_verification_email
    from apps.accounts.models import OTPCode, User, generate_otp

    try:
        user = User.objects.get(id=user_id)
        otp = generate_otp(user, OTPCode.Purpose.EMAIL_VERIFICATION)
        send_otp_verification_email(user, otp.code)
    except Exception:
        logger.exception("Failed to send OTP verification email to user %s", user_id)


@shared_task
def send_otp_password_reset_email_task(user_id):
    from apps.accounts.emails import send_otp_password_reset_email
    from apps.accounts.models import OTPCode, User, generate_otp

    try:
        user = User.objects.get(id=user_id)
        otp = generate_otp(user, OTPCode.Purpose.PASSWORD_RESET)
        send_otp_password_reset_email(user, otp.code)
    except Exception:
        logger.exception("Failed to send OTP password reset email to user %s", user_id)
