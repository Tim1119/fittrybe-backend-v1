"""
Celery tasks for the clients app.
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def send_payment_reminders():
    """
    Daily at 9am — remind clients with overdue renewal dates.
    Sends an email to each active member whose renewal_date is today
    or in the past, then updates last_reminder_at.
    """
    from datetime import date

    from apps.clients.emails import send_client_reminder_email
    from apps.clients.models import ClientMembership

    today = date.today()
    overdue = ClientMembership.objects.filter(
        status=ClientMembership.Status.ACTIVE,
        renewal_date__lte=today,
        deleted_at__isnull=True,
    ).select_related("client__user", "trainer", "gym")

    for membership in overdue:
        owner_name = (
            membership.trainer.full_name
            if membership.trainer_id
            else membership.gym.gym_name
        )
        try:
            send_client_reminder_email(membership, owner_name)
        except Exception:
            logger.exception("Failed to send reminder for membership %s", membership.pk)
        membership.last_reminder_at = timezone.now()
        membership.save(update_fields=["last_reminder_at"])


@shared_task
def update_membership_statuses():
    """
    Daily at midnight — auto-lapse active memberships whose renewal_date
    has passed.
    """
    from datetime import date

    from apps.clients.models import ClientMembership

    today = date.today()
    ClientMembership.objects.filter(
        status=ClientMembership.Status.ACTIVE,
        renewal_date__lt=today,
        deleted_at__isnull=True,
    ).update(status=ClientMembership.Status.LAPSED)
