"""
Badges app Celery tasks — milestone checks, chatroom posts,
and weekly top-badge awards.
"""

from celery import shared_task


@shared_task
def check_milestone_badges(client_id, trainer_id):
    """
    Called after every completed session.
    Awards milestone badge if client hit a threshold.
    """
    from apps.badges.models import Badge, BadgeAssignment
    from apps.notifications.tasks import send_push_notification
    from apps.profiles.models import ClientProfile, TrainerProfile

    try:
        client = ClientProfile.objects.get(id=client_id)
        trainer = TrainerProfile.objects.get(id=trainer_id)
    except (ClientProfile.DoesNotExist, TrainerProfile.DoesNotExist):
        return

    from apps.sessions.models import Session

    total = Session.objects.filter(
        client=client,
        status="completed",
        deleted_at__isnull=True,
    ).count()

    badge = Badge.objects.filter(
        badge_type="milestone",
        milestone_threshold=total,
        is_system=True,
    ).first()

    if not badge:
        return

    if BadgeAssignment.objects.filter(client=client, badge=badge).exists():
        return

    assignment = BadgeAssignment.objects.create(
        badge=badge,
        client=client,
        trainer=trainer,
        assigned_by=trainer.user,
        post_to_chatroom=True,
    )

    if assignment.post_to_chatroom:
        post_badge_to_chatroom.delay(str(assignment.id))

    send_push_notification.delay(
        user_id=str(client.user_id),
        title="You earned a badge! 🏅",
        body=f"You just earned the {badge.name} badge!",
        data={
            "type": "badge_earned",
            "badge_id": str(badge.id),
            "assignment_id": str(assignment.id),
        },
    )


@shared_task
def post_badge_to_chatroom(assignment_id):
    """
    Posts a recognition announcement to the trainer's chatroom
    when a badge is assigned.
    """
    from apps.badges.models import BadgeAssignment
    from apps.chat.models import Message

    try:
        assignment = BadgeAssignment.objects.select_related(
            "badge", "client", "trainer", "assigned_by"
        ).get(id=assignment_id)
    except BadgeAssignment.DoesNotExist:
        return

    trainer = assignment.trainer
    if not trainer:
        return

    try:
        chatroom = trainer.chatroom
    except Exception:
        return

    client_name = assignment.client.display_name or assignment.client.username
    assigner = assignment.assigned_by
    content = f"🏅 {client_name} just earned the {assignment.badge.name} badge!"
    if assignment.note:
        content += f' "{assignment.note}"'
    if assigner:
        content += f" — {assigner.display_name}"

    Message.objects.create(
        chatroom=chatroom,
        sender=assigner or trainer.user,
        content=content,
        message_type="announcement",
        audience="full_group",
    )


@shared_task
def award_weekly_top_badges():
    """
    Every Monday 6am via Celery Beat.
    Awards Weekly Top 1/2/3 to most active clients
    per trainer community (last 7 days).
    """
    from datetime import timedelta

    from django.db.models import Count
    from django.utils import timezone

    from apps.badges.models import Badge, BadgeAssignment
    from apps.profiles.models import ClientProfile, TrainerProfile
    from apps.sessions.models import Session

    week_ago = timezone.now().date() - timedelta(days=7)
    positions = ["Weekly Top 1", "Weekly Top 2", "Weekly Top 3"]

    for trainer in TrainerProfile.objects.filter(is_published=True):
        top_clients = (
            Session.objects.filter(
                trainer=trainer,
                status="completed",
                session_date__gte=week_ago,
                deleted_at__isnull=True,
            )
            .values("client")
            .annotate(session_count=Count("id"))
            .order_by("-session_count")[:3]
        )

        for i, row in enumerate(top_clients):
            badge = Badge.objects.filter(name=positions[i]).first()
            if not badge:
                continue
            try:
                client = ClientProfile.objects.get(id=row["client"])
            except ClientProfile.DoesNotExist:
                continue

            assignment = BadgeAssignment.objects.create(
                badge=badge,
                client=client,
                trainer=trainer,
                assigned_by=None,
                post_to_chatroom=True,
            )
            post_badge_to_chatroom.delay(str(assignment.id))
