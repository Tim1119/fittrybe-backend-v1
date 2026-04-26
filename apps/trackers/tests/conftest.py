"""Shared fixtures for trackers tests."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.profiles.models import ClientProfile, TrainerProfile

User = get_user_model()


def make_client_user(email="client@tracker.test"):
    user = User.objects.create_user(
        email=email,
        password="Test1234!",
        role="client",
        is_email_verified=True,
        is_active=True,
    )
    profile = ClientProfile.objects.create(user=user, display_name="Test Client")
    return user, profile


def make_client_with_addon(email="client_addon@tracker.test"):
    user, profile = make_client_user(email)
    profile.tracker_addon_active = True
    profile.save()
    return user, profile


def make_trainer_user(email="trainer@tracker.test"):
    user = User.objects.create_user(
        email=email,
        password="Test1234!",
        role="trainer",
        is_email_verified=True,
        is_active=True,
    )
    profile = TrainerProfile.objects.create(
        user=user,
        full_name="Test Trainer",
        trainer_type="independent",
        is_published=False,
    )
    return user, profile


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def anon_client():
    return APIClient()


@pytest.fixture
def client_with_addon(db):
    """Client with tracker addon active."""
    user, profile = make_client_with_addon()
    api = auth_client(user)
    return user, profile, api


@pytest.fixture
def client_no_addon(db):
    """Client without tracker addon."""
    user, profile = make_client_user(email="client_noaddon@tracker.test")
    api = auth_client(user)
    return user, profile, api


@pytest.fixture
def client2_with_addon(db):
    """Second client with tracker addon — for isolation tests."""
    user, profile = make_client_with_addon(email="client2_addon@tracker.test")
    api = auth_client(user)
    return user, profile, api


@pytest.fixture
def trainer_user(db):
    """Trainer user for 403 tests."""
    user, profile = make_trainer_user()
    api = auth_client(user)
    return user, profile, api
