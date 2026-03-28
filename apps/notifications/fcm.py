"""
FCM helper — send push notifications via Firebase.
"""

import logging

from firebase_admin import messaging

from .models import FCMDevice

logger = logging.getLogger(__name__)


def send_push_to_user(user, title, body, data=None):
    """
    Send FCM push notification to all active devices for a given user.
    Deactivates stale tokens automatically.
    Called via Celery task — never call directly from views.
    """
    tokens = list(
        FCMDevice.objects.filter(user=user, is_active=True).values_list(
            "token", flat=True
        )
    )

    if not tokens:
        return

    # FCM data values must be strings
    data = {k: str(v) for k, v in (data or {}).items()}

    message = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=data,
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                sound="default",
                click_action="FLUTTER_NOTIFICATION_CLICK",
            ),
        ),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    sound="default",
                    badge=1,
                )
            )
        ),
        webpush=messaging.WebpushConfig(
            notification=messaging.WebpushNotification(
                icon="/static/img/icon.png",
            ),
        ),
    )

    try:
        response = messaging.send_each_for_multicast(message)
        for i, result in enumerate(response.responses):
            if not result.success:
                error_code = result.exception.code if result.exception else None
                if error_code in (
                    "registration-token-not-registered",
                    "invalid-registration-token",
                ):
                    FCMDevice.objects.filter(token=tokens[i]).update(is_active=False)
                    logger.info("Deactivated stale FCM token for %s", user.email)
        logger.info(
            "FCM sent to %s: %d success, %d failure",
            user.email,
            response.success_count,
            response.failure_count,
        )
    except Exception:
        logger.exception("Failed to send FCM notification to %s", user.email)


def send_push_to_users(users, title, body, data=None):
    """Send push to multiple users."""
    for user in users:
        send_push_to_user(user, title, body, data)
