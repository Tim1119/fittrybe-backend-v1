"""
CHAT-04 Member management tests.
"""

import pytest

from apps.chat.models import ChatroomMember
from apps.chat.tests.conftest import add_member, make_client_user
from apps.clients.models import ClientMembership


@pytest.mark.django_db
def test_member_list_has_membership_status(trainer_setup, client_in_chatroom):
    _, trainer_profile, room, admin_client = trainer_setup
    resp = admin_client.get(f"/api/v1/chat/rooms/{room.id}/members/")
    assert resp.status_code == 200
    members = resp.data["data"]
    # At least one member should have a membership_status field
    assert all("membership_status" in m for m in members)


@pytest.mark.django_db
def test_admin_can_remove_member(trainer_setup, client_in_chatroom):
    _, _, room, admin_client = trainer_setup
    client_user, _, _ = client_in_chatroom
    resp = admin_client.delete(
        f"/api/v1/chat/rooms/{room.id}/members/{client_user.id}/"
    )
    assert resp.status_code == 200
    member = ChatroomMember.objects.get(chatroom=room, user=client_user)
    assert member.is_active is False


@pytest.mark.django_db
def test_remove_member_soft_deletes_membership(trainer_setup, client_in_chatroom):
    _, trainer_profile, room, admin_client = trainer_setup
    client_user, client_profile, _ = client_in_chatroom
    resp = admin_client.delete(
        f"/api/v1/chat/rooms/{room.id}/members/{client_user.id}/"
    )
    assert resp.status_code == 200
    # ClientMembership should be soft-deleted (deleted_at set)
    membership = ClientMembership.all_objects.get(
        client=client_profile, trainer=trainer_profile
    )
    assert membership.deleted_at is not None


@pytest.mark.django_db
def test_cannot_remove_yourself(trainer_setup):
    admin_user, _, room, admin_client = trainer_setup
    resp = admin_client.delete(f"/api/v1/chat/rooms/{room.id}/members/{admin_user.id}/")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_non_admin_cannot_remove_member(trainer_setup, client_in_chatroom):
    _, _, room, _ = trainer_setup
    client_user, _, client_api = client_in_chatroom
    # Add another member to try removing
    other_user, _ = make_client_user(email="other_remove@test.com")
    add_member(room, other_user)
    resp = client_api.delete(f"/api/v1/chat/rooms/{room.id}/members/{other_user.id}/")
    assert resp.status_code == 403
