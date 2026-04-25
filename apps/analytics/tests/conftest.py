"""Shared fixtures for analytics tests."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.profiles.models import ClientProfile, GymProfile, TrainerProfile

User = get_user_model()


def make_user(role, email, display_name="Test User", **kwargs):
    return User.objects.create_user(
        email=email,
        password="Test1234!",
        role=role,
        display_name=display_name,
        is_email_verified=True,
        is_active=True,
        **kwargs,
    )


def make_trainer(email="trainer@analytics.test", name="Test Trainer"):
    user = make_user("trainer", email, display_name=name)
    profile = TrainerProfile.objects.create(
        user=user,
        full_name=name,
        is_published=True,
        trainer_type="independent",
    )
    return user, profile


def make_gym(email="gym@analytics.test", name="Test Gym"):
    user = make_user("gym", email, display_name=name)
    profile = GymProfile.objects.create(
        user=user,
        gym_name=name,
        admin_full_name="Admin",
        is_published=True,
    )
    return user, profile


def make_client(email="client@analytics.test", name="Test Client"):
    user = make_user("client", email, display_name=name)
    profile = ClientProfile.objects.create(user=user, display_name=name)
    return user, profile


def auth_client(user):
    client = APIClient()
    token = AccessToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def trainer_setup(db):
    """Returns (trainer_user, trainer_profile, api_client)."""
    user, profile = make_trainer()
    client = auth_client(user)
    return user, profile, client


@pytest.fixture
def trainer2_setup(db):
    """A second independent trainer."""
    user, profile = make_trainer(email="trainer2@analytics.test", name="Trainer Two")
    client = auth_client(user)
    return user, profile, client


@pytest.fixture
def gym_setup(db):
    """Returns (gym_user, gym_profile, api_client)."""
    user, profile = make_gym()
    client = auth_client(user)
    return user, profile, client


@pytest.fixture
def client_setup(db):
    """Returns (client_user, client_profile, api_client)."""
    user, profile = make_client()
    api = auth_client(user)
    return user, profile, api


@pytest.fixture
def anon_client():
    return APIClient()
