"""
Celery tasks for subscription lifecycle management.
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def check_trial_expirations():
    """Move expired TRIAL subscriptions to GRACE and send warning emails."""
    from apps.subscriptions.models import Subscription

    expired = Subscription.objects.filter(
        status=Subscription.Status.TRIAL, trial_end__lt=timezone.now()
    ).select_related("user", "plan")

    count = 0
    for sub in expired:
        sub.enter_grace_period()
        send_grace_period_warning.delay(sub.id)
        count += 1

    logger.info("Moved %d trial subscriptions to grace period.", count)
    return count


@shared_task
def check_grace_period_expirations():
    """Lock subscriptions whose grace period has ended."""
    from apps.subscriptions.models import Subscription

    expired = Subscription.objects.filter(
        status=Subscription.Status.GRACE, grace_period_end__lt=timezone.now()
    ).select_related("user", "plan")

    count = 0
    for sub in expired:
        sub.lock()
        count += 1

    logger.info("Locked %d subscriptions after grace period.", count)
    return count


@shared_task
def send_trial_reminder(subscription_id):
    """Send trial expiry reminder email (3 days or 1 day remaining)."""
    from apps.subscriptions.models import Subscription

    try:
        sub = Subscription.objects.select_related("user", "plan").get(
            pk=subscription_id
        )
    except Subscription.DoesNotExist:
        return

    days = sub.days_remaining_in_trial()
    if days not in (1, 3):
        return

    _send_trial_reminder_email(sub.user, days, sub.trial_end)


@shared_task
def send_grace_period_warning(subscription_id):
    """Send grace period warning email."""
    from apps.subscriptions.models import Subscription

    try:
        sub = Subscription.objects.select_related("user", "plan").get(
            pk=subscription_id
        )
    except Subscription.DoesNotExist:
        return

    _send_grace_warning_email(sub.user, sub.grace_period_end)


@shared_task
def send_grace_period_reminder(subscription_id):
    """Send daily reminder during grace period."""
    from apps.subscriptions.models import Subscription

    try:
        sub = Subscription.objects.select_related("user", "plan").get(
            pk=subscription_id
        )
    except Subscription.DoesNotExist:
        return

    if sub.status != Subscription.Status.GRACE:
        return

    _send_grace_warning_email(sub.user, sub.grace_period_end)


# ---------------------------------------------------------------------------
# Email helpers (thin wrappers to keep tasks testable)
# ---------------------------------------------------------------------------


def _send_trial_reminder_email(user, days_remaining, trial_end):
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string

    mobile_scheme = getattr(settings, "MOBILE_URL", "fittrybe://")
    web_url = f"{settings.FRONTEND_URL}/subscription/upgrade/"
    mobile_url = f"{mobile_scheme}subscription/upgrade"
    context = {
        "user_email": user.email,
        "days_remaining": days_remaining,
        "trial_end": trial_end,
        "web_url": web_url,
        "mobile_url": mobile_url,
        "frontend_url": settings.FRONTEND_URL,
        "logo_url": f"{settings.FRONTEND_URL}/static/accounts/images/logo.png",
        # legacy
        "checkout_url": web_url,
    }
    html = render_to_string("subscriptions/emails/trial_reminder.html", context)
    text = (
        f"Your Fit Trybe trial ends in {days_remaining} day(s).\n\n"
        f"Upgrade now:\n"
        f"  In browser: {web_url}\n"
        f"  In app:     {mobile_url}"
    )
    msg = EmailMultiAlternatives(
        subject=f"Your Fit Trybe trial ends in {days_remaining} day(s)",
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=True)


def _send_grace_warning_email(user, grace_period_end):
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string

    mobile_scheme = getattr(settings, "MOBILE_URL", "fittrybe://")
    web_url = f"{settings.FRONTEND_URL}/subscription/upgrade/"
    mobile_url = f"{mobile_scheme}subscription/upgrade"
    context = {
        "user_email": user.email,
        "grace_period_end": grace_period_end,
        "web_url": web_url,
        "mobile_url": mobile_url,
        "frontend_url": settings.FRONTEND_URL,
        "logo_url": f"{settings.FRONTEND_URL}/static/accounts/images/logo.png",
        # legacy
        "checkout_url": web_url,
    }
    html = render_to_string("subscriptions/emails/grace_period_warning.html", context)
    text = (
        f"Your Fit Trybe subscription has expired.\n\n"
        f"You have until {grace_period_end} to renew.\n\n"
        f"Renew now:\n"
        f"  In browser: {web_url}\n"
        f"  In app:     {mobile_url}"
    )
    msg = EmailMultiAlternatives(
        subject="Action required: Renew your Fit Trybe subscription",
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=True)
