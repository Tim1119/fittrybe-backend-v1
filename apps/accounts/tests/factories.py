import factory
from factory.django import DjangoModelFactory
from faker import Faker

from apps.accounts.models import User

fake = Faker()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.LazyAttribute(lambda _: fake.unique.email())
    password = factory.PostGenerationMethodCall("set_password", "StrongPass123!")
    role = "trainer"
    is_active = True
    is_email_verified = True


class UnverifiedUserFactory(UserFactory):
    is_active = False
    is_email_verified = False


class TrainerFactory(UserFactory):
    role = "trainer"


class GymFactory(UserFactory):
    role = "gym"


class ClientFactory(UserFactory):
    role = "client"
