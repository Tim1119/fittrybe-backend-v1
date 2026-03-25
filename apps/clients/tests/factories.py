"""Factories for clients app tests."""

import factory
from factory.django import DjangoModelFactory

from apps.clients.models import ClientMembership, InviteLink
from apps.profiles.tests.factories import (
    ClientProfileFactory,
    GymProfileFactory,
    TrainerProfileFactory,
)


class ClientMembershipTrainerFactory(DjangoModelFactory):
    """ClientMembership linked to a trainer (no gym)."""

    class Meta:
        model = ClientMembership

    client = factory.SubFactory(ClientProfileFactory)
    trainer = factory.SubFactory(TrainerProfileFactory)
    gym = None
    status = ClientMembership.Status.ACTIVE


class ClientMembershipGymFactory(DjangoModelFactory):
    """ClientMembership linked to a gym (no trainer)."""

    class Meta:
        model = ClientMembership

    client = factory.SubFactory(ClientProfileFactory)
    gym = factory.SubFactory(GymProfileFactory)
    trainer = None
    status = ClientMembership.Status.ACTIVE


class InviteLinkTrainerFactory(DjangoModelFactory):
    """InviteLink owned by a trainer."""

    class Meta:
        model = InviteLink

    trainer = factory.SubFactory(TrainerProfileFactory)
    gym = None
    is_active = True


class InviteLinkGymFactory(DjangoModelFactory):
    """InviteLink owned by a gym."""

    class Meta:
        model = InviteLink

    gym = factory.SubFactory(GymProfileFactory)
    trainer = None
    is_active = True
