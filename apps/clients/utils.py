"""
Shared helpers for the clients app.
"""

from django.db.models import Q


def get_managed_clients(user):
    """
    Returns ClientMembership queryset for all clients visible to this
    trainer or gym.

    Trainer (independent or gym-affiliated):
      → memberships where trainer = user.trainer_profile

    Gym admin:
      → memberships where gym = user.gym_profile (direct gym clients)
        PLUS memberships where trainer__gym = user.gym_profile
             (clients of trainers who belong to this gym)
    """
    from apps.clients.models import ClientMembership

    if user.role == "trainer":
        return (
            ClientMembership.objects.filter(
                trainer=user.trainer_profile,
                deleted_at__isnull=True,
            )
            .select_related("client__user", "trainer")
            .order_by("-created_at")
        )

    if user.role == "gym":
        return (
            ClientMembership.objects.filter(
                Q(gym=user.gym_profile) | Q(trainer__gym=user.gym_profile),
                deleted_at__isnull=True,
            )
            .select_related("client__user", "trainer", "gym")
            .distinct()
            .order_by("-created_at")
        )

    return __import__(
        "apps.clients.models", fromlist=["ClientMembership"]
    ).ClientMembership.objects.none()


def user_owns_membership(membership, user):
    """
    Return True if the authenticated trainer/gym owns this membership.
    """
    try:
        if user.role == "trainer":
            return (
                membership.trainer_id is not None
                and membership.trainer_id == user.trainer_profile.id
            )
        if user.role == "gym":
            direct = (
                membership.gym_id is not None
                and membership.gym_id == user.gym_profile.id
            )
            via_trainer = (
                membership.trainer_id is not None
                and membership.trainer.gym_id is not None
                and membership.trainer.gym_id == user.gym_profile.id
            )
            return direct or via_trainer
    except Exception:
        pass
    return False
