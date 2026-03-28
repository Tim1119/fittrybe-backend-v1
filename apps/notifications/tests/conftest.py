"""
Shared fixtures for notifications tests.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

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


def auth_client(user):
    client = APIClient()
    token = AccessToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def trainer_user(db):
    return make_user("trainer", "trainer@notif.test", "Trainer One")


@pytest.fixture
def trainer_client(trainer_user):
    return auth_client(trainer_user)


@pytest.fixture
def other_user(db):
    return make_user("client", "other@notif.test", "Other User")


@pytest.fixture
def other_client(other_user):
    return auth_client(other_user)
