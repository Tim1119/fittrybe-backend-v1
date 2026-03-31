"""Factories for sessions app tests."""

import datetime

import factory
from factory.django import DjangoModelFactory

from apps.profiles.tests.factories import ClientProfileFactory, TrainerProfileFactory
from apps.sessions.models import Session


class SessionFactory(DjangoModelFactory):
    class Meta:
        model = Session

    trainer = factory.SubFactory(TrainerProfileFactory)
    client = factory.SubFactory(ClientProfileFactory)
    session_date = factory.LazyFunction(datetime.date.today)
    session_time = None
    duration_minutes = 60
    session_type = Session.SessionType.PHYSICAL
    virtual_platform = ""
    notes = ""
    status = Session.Status.COMPLETED


class CancelledSessionFactory(SessionFactory):
    status = Session.Status.CANCELLED


class NoShowSessionFactory(SessionFactory):
    status = Session.Status.NO_SHOW
