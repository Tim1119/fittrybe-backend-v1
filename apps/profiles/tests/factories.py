"""Factories for profile tests."""

import factory
from factory.django import DjangoModelFactory
from faker import Faker

from apps.accounts.tests.factories import ClientFactory, GymFactory, TrainerFactory
from apps.profiles.models import (
    Availability,
    Certification,
    ClientProfile,
    GymProfile,
    GymTrainer,
    Specialisation,
    TrainerProfile,
)

fake = Faker()


class SpecialisationFactory(DjangoModelFactory):
    class Meta:
        model = Specialisation
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Specialisation {n}")
    is_predefined = False


class TrainerProfileFactory(DjangoModelFactory):
    class Meta:
        model = TrainerProfile

    user = factory.SubFactory(TrainerFactory)
    full_name = factory.LazyAttribute(lambda _: fake.name())
    bio = ""
    location = ""
    phone_number = ""
    years_experience = 0
    pricing_range = ""
    profile_photo_url = ""
    cover_photo_url = ""
    is_published = False
    wizard_step = 0
    wizard_completed = False


class PublishedTrainerProfileFactory(TrainerProfileFactory):
    bio = "A great trainer."
    location = "Lagos"
    profile_photo_url = "http://example.com/photo.jpg"
    cover_photo_url = "http://example.com/cover.jpg"
    years_experience = 3
    pricing_range = "10000 - 20000 NGN"
    is_published = True
    wizard_step = 4
    wizard_completed = True


class GymProfileFactory(DjangoModelFactory):
    class Meta:
        model = GymProfile

    user = factory.SubFactory(GymFactory)
    gym_name = factory.Sequence(lambda n: f"Gym {n}")
    admin_full_name = factory.LazyAttribute(lambda _: fake.name())
    about = ""
    location = ""
    city = ""
    contact_phone = ""
    business_email = ""
    logo_url = ""
    cover_photo_url = ""
    is_published = False
    wizard_step = 0
    wizard_completed = False


class PublishedGymProfileFactory(GymProfileFactory):
    about = "A great gym."
    location = "Abuja"
    city = "Abuja"
    logo_url = "http://example.com/logo.jpg"
    cover_photo_url = "http://example.com/gym-cover.jpg"
    contact_phone = "08012345678"
    business_email = "gym@example.com"
    is_published = True
    wizard_step = 4
    wizard_completed = True


class GymTrainerFactory(DjangoModelFactory):
    class Meta:
        model = GymTrainer

    gym = factory.SubFactory(GymProfileFactory)
    trainer = factory.SubFactory(TrainerProfileFactory)
    role = GymTrainer.Role.TRAINER


class AvailabilityTrainerFactory(DjangoModelFactory):
    class Meta:
        model = Availability

    trainer = factory.SubFactory(TrainerProfileFactory)
    gym = None
    day_of_week = Availability.DayOfWeek.MONDAY
    start_time = "09:00"
    end_time = "10:00"
    session_type = Availability.SessionType.BOTH
    duration_minutes = 60


class AvailabilityGymFactory(DjangoModelFactory):
    class Meta:
        model = Availability

    gym = factory.SubFactory(GymProfileFactory)
    trainer = None
    day_of_week = Availability.DayOfWeek.MONDAY
    start_time = "06:00"
    end_time = "22:00"
    session_type = Availability.SessionType.PHYSICAL
    duration_minutes = 60


class CertificationFactory(DjangoModelFactory):
    class Meta:
        model = Certification

    trainer = factory.SubFactory(TrainerProfileFactory)
    name = factory.Sequence(lambda n: f"Cert {n}")
    issuing_body = "NASM"
    year_obtained = 2020


class ClientProfileFactory(DjangoModelFactory):
    class Meta:
        model = ClientProfile

    user = factory.SubFactory(ClientFactory)
    display_name = factory.LazyAttribute(lambda obj: obj.user.display_name or "User")
    profile_photo_url = ""
