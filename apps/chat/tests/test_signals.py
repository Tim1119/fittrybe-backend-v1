"""
Signal tests — auto chatroom creation and membership sync.
"""

import pytest

from apps.chat.models import Chatroom, ChatroomMember
from apps.chat.tests.conftest import (
    make_client_user,
    make_gym_user,
    make_membership,
    make_trainer_user,
)


@pytest.mark.django_db
def test_publishing_trainer_creates_chatroom():
    user, profile = make_trainer_user(email="sig_trainer@test.com")
    # is_published=True was set in make_trainer_user → signal fires
    assert Chatroom.objects.filter(trainer=profile).exists()


@pytest.mark.django_db
def test_trainer_chatroom_default_name():
    user, profile = make_trainer_user(email="sig_trainer2@test.com", name="Ada Okafor")
    room = Chatroom.objects.get(trainer=profile)
    assert room.name == "Ada Okafor's Community"


@pytest.mark.django_db
def test_publishing_gym_creates_chatroom():
    user, profile = make_gym_user(email="sig_gym@test.com", name="FitHub Lagos")
    assert Chatroom.objects.filter(gym=profile).exists()


@pytest.mark.django_db
def test_gym_chatroom_default_name():
    user, profile = make_gym_user(email="sig_gym2@test.com", name="FitHub Lagos")
    room = Chatroom.objects.get(gym=profile)
    assert room.name == "FitHub Lagos's Community"


@pytest.mark.django_db
def test_trainer_auto_added_as_admin():
    user, profile = make_trainer_user(email="sig_trainer3@test.com")
    room = Chatroom.objects.get(trainer=profile)
    member = ChatroomMember.objects.get(chatroom=room, user=user)
    assert member.role == ChatroomMember.Role.ADMIN
    assert member.is_active is True


@pytest.mark.django_db
def test_gym_auto_added_as_admin():
    user, profile = make_gym_user(email="sig_gym3@test.com")
    room = Chatroom.objects.get(gym=profile)
    member = ChatroomMember.objects.get(chatroom=room, user=user)
    assert member.role == ChatroomMember.Role.ADMIN
    assert member.is_active is True


@pytest.mark.django_db
def test_republishing_does_not_create_duplicate_chatroom():
    user, profile = make_trainer_user(email="sig_trainer4@test.com")
    count_before = Chatroom.objects.filter(trainer=profile).count()
    # Save again (triggers signal again)
    profile.save()
    count_after = Chatroom.objects.filter(trainer=profile).count()
    assert count_before == count_after == 1


@pytest.mark.django_db
def test_client_membership_adds_to_chatroom():
    t_user, t_profile = make_trainer_user(email="sig_trainer5@test.com")
    room = Chatroom.objects.get(trainer=t_profile)
    c_user, c_profile = make_client_user(email="sig_client1@test.com")
    make_membership(c_profile, trainer=t_profile)
    assert ChatroomMember.objects.filter(
        chatroom=room, user=c_user, is_active=True
    ).exists()


@pytest.mark.django_db
def test_soft_deleting_membership_deactivates_chatroom_member():
    t_user, t_profile = make_trainer_user(email="sig_trainer6@test.com")
    room = Chatroom.objects.get(trainer=t_profile)
    c_user, c_profile = make_client_user(email="sig_client2@test.com")
    membership = make_membership(c_profile, trainer=t_profile)
    assert ChatroomMember.objects.filter(
        chatroom=room, user=c_user, is_active=True
    ).exists()

    membership.delete()  # soft delete → triggers signal
    assert ChatroomMember.objects.filter(
        chatroom=room, user=c_user, is_active=False
    ).exists()


@pytest.mark.django_db
def test_member_count_increments_on_join():
    t_user, t_profile = make_trainer_user(email="sig_trainer7@test.com")
    room = Chatroom.objects.get(trainer=t_profile)
    initial_count = room.member_count
    c_user, c_profile = make_client_user(email="sig_client3@test.com")
    make_membership(c_profile, trainer=t_profile)
    room.refresh_from_db()
    assert room.member_count == initial_count + 1


@pytest.mark.django_db
def test_member_count_decrements_on_remove():
    t_user, t_profile = make_trainer_user(email="sig_trainer8@test.com")
    room = Chatroom.objects.get(trainer=t_profile)
    c_user, c_profile = make_client_user(email="sig_client4@test.com")
    membership = make_membership(c_profile, trainer=t_profile)
    room.refresh_from_db()
    count_after_join = room.member_count

    membership.delete()
    room.refresh_from_db()
    assert room.member_count == count_after_join - 1
