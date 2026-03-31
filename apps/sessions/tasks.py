"""
Sessions app Celery tasks — delegates badge checks after session log.
"""

from celery import shared_task


@shared_task
def check_session_badges(client_id, trainer_id):
    """Delegates to badges app after each session log."""
    from apps.badges.tasks import check_milestone_badges

    check_milestone_badges.delay(client_id, trainer_id)
