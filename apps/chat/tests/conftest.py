"""
Shared fixtures for chat tests.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.chat.models import Chatroom, ChatroomMember
from apps.clients.models import ClientMembership
from apps.profiles.models import ClientProfile, GymProfile, TrainerProfile

User = get_user_model()

# ─────────────────────────────────────────────────────────────────────────────
# User factories
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


def make_trainer_user(email="trainer@chat.test", name="Test Trainer"):
    user = make_user("trainer", email, display_name=name)
    profile = TrainerProfile.objects.create(
        user=user,
        full_name=name,
        is_published=True,
        trainer_type="independent",
    )
    return user, profile


def make_gym_user(email="gym@chat.test", name="Test Gym"):
    user = make_user("gym", email, display_name=name)
    profile = GymProfile.objects.create(
        user=user,
        gym_name=name,
        admin_full_name="Admin",
        is_published=True,
    )
    return user, profile


def make_client_user(email="client@chat.test", name="Test Client"):
    user = make_user("client", email, display_name=name)
    profile = ClientProfile.objects.create(user=user, display_name=name)
    return user, profile


def make_chatroom(trainer=None, gym=None, name=None):
    """Get or create a chatroom. Signal may have already created one."""
    if trainer:
        name = name or f"{trainer.full_name}'s Community"
        room, _ = Chatroom.objects.get_or_create(
            trainer=trainer, defaults={"name": name}
        )
        return room
    else:
        name = name or f"{gym.gym_name}'s Community"
        room, _ = Chatroom.objects.get_or_create(gym=gym, defaults={"name": name})
        return room


def add_member(chatroom, user, role=ChatroomMember.Role.MEMBER, is_active=True):
    member, _ = ChatroomMember.objects.get_or_create(
        chatroom=chatroom,
        user=user,
        defaults={"role": role, "is_active": is_active},
    )
    return member


def make_membership(client_profile, trainer=None, gym=None):
    kwargs = {"client": client_profile, "status": "active"}
    if trainer:
        kwargs["trainer"] = trainer
    else:
        kwargs["gym"] = gym
    return ClientMembership.objects.create(**kwargs)


def auth_client(user):
    client = APIClient()
    token = AccessToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


# ─────────────────────────────────────────────────────────────────────────────
# pytest fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def trainer_setup(db):
    """Returns (trainer_user, trainer_profile, chatroom, api_client)."""
    user, profile = make_trainer_user()
    room = make_chatroom(trainer=profile)
    add_member(room, user, role=ChatroomMember.Role.ADMIN)
    client = auth_client(user)
    return user, profile, room, client


@pytest.fixture
def gym_setup(db):
    """Returns (gym_user, gym_profile, chatroom, api_client)."""
    user, profile = make_gym_user()
    room = make_chatroom(gym=profile)
    add_member(room, user, role=ChatroomMember.Role.ADMIN)
    client = auth_client(user)
    return user, profile, room, client


@pytest.fixture
def client_in_chatroom(db, trainer_setup):
    """Adds a client member to the trainer's chatroom."""
    _, trainer_profile, room, _ = trainer_setup
    client_user, client_profile = make_client_user()
    make_membership(client_profile, trainer=trainer_profile)
    add_member(room, client_user)
    api_client = auth_client(client_user)
    return client_user, client_profile, api_client


CHANNEL_LAYERS_TEST = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}
