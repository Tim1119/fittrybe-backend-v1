"""Factories for badges app tests."""

import factory
from factory.django import DjangoModelFactory

from apps.badges.models import Badge, BadgeAssignment
from apps.profiles.tests.factories import ClientProfileFactory, TrainerProfileFactory


class BadgeFactory(DjangoModelFactory):
    class Meta:
        model = Badge
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Test Badge {n}")
    badge_type = Badge.BadgeType.MANUAL
    description = "A test badge."
    icon_url = ""
    is_system = False
    milestone_threshold = None


class MilestoneBadgeFactory(BadgeFactory):
    badge_type = Badge.BadgeType.MILESTONE
    milestone_threshold = 1


class BadgeAssignmentFactory(DjangoModelFactory):
    class Meta:
        model = BadgeAssignment

    badge = factory.SubFactory(BadgeFactory)
    client = factory.SubFactory(ClientProfileFactory)
    trainer = factory.SubFactory(TrainerProfileFactory)
    gym = None
    assigned_by = factory.LazyAttribute(lambda obj: obj.trainer.user)
    note = ""
    post_to_chatroom = True
