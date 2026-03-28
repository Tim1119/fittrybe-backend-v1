"""
Shared fixtures for marketplace tests.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.profiles.models import ClientProfile, GymProfile, TrainerProfile

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# User / profile factories
# ─────────────────────────────────────────────────────────────────────────────


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


def make_trainer(email="trainer@mkt.test", name="Test Trainer", location="Lagos"):
    user = make_user("trainer", email, display_name=name)
    profile = TrainerProfile.objects.create(
        user=user,
        full_name=name,
        is_published=True,
        trainer_type="independent",
        location=location,
    )
    return user, profile


def make_gym(email="gym@mkt.test", name="Test Gym", location="Abuja"):
    user = make_user("gym", email, display_name=name)
    profile = GymProfile.objects.create(
        user=user,
        gym_name=name,
        admin_full_name="Admin",
        is_published=True,
        location=location,
    )
    return user, profile


def make_client(email="client@mkt.test", name="Test Client"):
    user = make_user("client", email, display_name=name)
    profile = ClientProfile.objects.create(user=user, display_name=name)
    return user, profile


def auth_client(user):
    client = APIClient()
    token = AccessToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def make_product(trainer=None, gym=None, **kwargs):
    from apps.marketplace.models import Product

    defaults = {
        "name": "Test Product",
        "description": "A test product",
        "category": Product.Category.PROGRAM,
        "price": "5000.00",
        "status": Product.Status.ACTIVE,
    }
    defaults.update(kwargs)
    if trainer:
        defaults["trainer"] = trainer
    else:
        defaults["gym"] = gym
    return Product.objects.create(**defaults)


# ─────────────────────────────────────────────────────────────────────────────
# pytest fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def trainer_setup(db):
    """Returns (trainer_user, trainer_profile, api_client)."""
    user, profile = make_trainer()
    client = auth_client(user)
    return user, profile, client


@pytest.fixture
def trainer2_setup(db):
    """A second trainer (for ownership tests)."""
    user, profile = make_trainer(email="trainer2@mkt.test", name="Trainer Two")
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
    api_client = auth_client(user)
    return user, profile, api_client


@pytest.fixture
def anon_client():
    return APIClient()
