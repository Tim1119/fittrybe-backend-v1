"""
CHAT-01 REST tests — community chatroom and messages.
"""

import io

import pytest
from django.utils import timezone

from apps.chat.models import ChatroomMember, Message, PinnedMessage
from apps.chat.tests.conftest import add_member, auth_client, make_client_user

# ─────────────────────────────────────────────────────────────────────────────
# Chatroom list / detail / update
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_list_chatrooms(trainer_setup):
    user, _, room, client = trainer_setup
    resp = client.get("/api/v1/chat/rooms/")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.data["data"]]
    assert room.id in ids


@pytest.mark.django_db
def test_removed_member_can_get_room(trainer_setup):
    _, _, room, _ = trainer_setup
    client_user, _, client_api = _make_removed_member(room)
    resp = client_api.get(f"/api/v1/chat/rooms/{room.id}/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_admin_can_patch_room_name(trainer_setup):
    _, _, room, client = trainer_setup
    resp = client.patch(f"/api/v1/chat/rooms/{room.id}/update/", {"name": "New Name"})
    assert resp.status_code == 200
    assert resp.data["data"]["name"] == "New Name"


@pytest.mark.django_db
def test_member_cannot_patch_room(trainer_setup):
    _, _, room, _ = trainer_setup
    _, _, client_api = _make_client_member(room)
    resp = client_api.patch(f"/api/v1/chat/rooms/{room.id}/update/", {"name": "Hack"})
    assert resp.status_code == 403


@pytest.mark.django_db
def test_admin_can_patch_zoom_link(trainer_setup):
    _, _, room, client = trainer_setup
    resp = client.patch(
        f"/api/v1/chat/rooms/{room.id}/update/",
        {"zoom_link": "https://zoom.us/j/123"},
    )
    assert resp.status_code == 200
    assert resp.data["data"]["zoom_link"] == "https://zoom.us/j/123"


# ─────────────────────────────────────────────────────────────────────────────
# Messages — GET
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_message_list_oldest_first(trainer_setup):
    user, _, room, client = trainer_setup
    msg1 = Message.objects.create(chatroom=room, sender=user, content="First")
    msg2 = Message.objects.create(chatroom=room, sender=user, content="Second")
    resp = client.get(f"/api/v1/chat/rooms/{room.id}/messages/")
    assert resp.status_code == 200
    ids = [m["id"] for m in resp.data["data"]]
    assert ids.index(msg1.id) < ids.index(msg2.id)


@pytest.mark.django_db
def test_individual_message_visibility(trainer_setup, client_in_chatroom):
    admin_user, _, room, admin_client = trainer_setup
    client_user, _, client_api = client_in_chatroom
    # Create a third user not in the room
    other_user, _, other_api = _make_client_member(room)

    # Admin sends individual message to client_user
    resp = admin_client.post(
        f"/api/v1/chat/rooms/{room.id}/messages/",
        {
            "content": "Just for you",
            "audience": "individual",
            "target_user_id": str(client_user.id),
        },
    )
    assert resp.status_code == 201
    msg_id = resp.data["data"]["id"]

    # Sender and target can see it
    resp_sender = admin_client.get(f"/api/v1/chat/rooms/{room.id}/messages/")
    resp_target = client_api.get(f"/api/v1/chat/rooms/{room.id}/messages/")
    resp_other = other_api.get(f"/api/v1/chat/rooms/{room.id}/messages/")

    assert any(m["id"] == msg_id for m in resp_sender.data["data"])
    assert any(m["id"] == msg_id for m in resp_target.data["data"])
    assert not any(m["id"] == msg_id for m in resp_other.data["data"])


# ─────────────────────────────────────────────────────────────────────────────
# Messages — POST
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_active_member_can_post_message(trainer_setup):
    _, _, room, client = trainer_setup
    resp = client.post(
        f"/api/v1/chat/rooms/{room.id}/messages/",
        {"content": "Hello world"},
    )
    assert resp.status_code == 201


@pytest.mark.django_db
def test_removed_member_cannot_post(trainer_setup):
    _, _, room, _ = trainer_setup
    client_user, _, client_api = _make_removed_member(room)
    resp = client_api.post(
        f"/api/v1/chat/rooms/{room.id}/messages/",
        {"content": "I should not send this"},
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_admin_can_post_announcement(trainer_setup):
    _, _, room, client = trainer_setup
    resp = client.post(
        f"/api/v1/chat/rooms/{room.id}/messages/",
        {"content": "Big news", "message_type": "announcement"},
    )
    assert resp.status_code == 201


@pytest.mark.django_db
def test_non_admin_cannot_post_announcement(trainer_setup):
    _, _, room, _ = trainer_setup
    _, _, client_api = _make_client_member(room)
    resp = client_api.post(
        f"/api/v1/chat/rooms/{room.id}/messages/",
        {"content": "Announcement?", "message_type": "announcement"},
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_admin_can_post_reminder_with_scheduled_at(trainer_setup):
    _, _, room, client = trainer_setup
    scheduled = (timezone.now() + timezone.timedelta(days=1)).isoformat()
    resp = client.post(
        f"/api/v1/chat/rooms/{room.id}/messages/",
        {
            "content": "Remember to train!",
            "message_type": "reminder",
            "scheduled_at": scheduled,
        },
    )
    assert resp.status_code == 201


@pytest.mark.django_db
def test_post_individual_message_requires_target(trainer_setup, client_in_chatroom):
    _, _, room, client = trainer_setup
    resp = client.post(
        f"/api/v1/chat/rooms/{room.id}/messages/",
        {"content": "Hey", "audience": "individual"},
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_post_empty_message_rejected(trainer_setup):
    _, _, room, client = trainer_setup
    resp = client.post(f"/api/v1/chat/rooms/{room.id}/messages/", {})
    assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Media upload
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_upload_valid_image(trainer_setup, tmp_path):
    _, _, room, client = trainer_setup
    # Minimal valid JPEG bytes
    jpeg_bytes = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01"
        b"\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06"
        b"\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b"
        b"\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c"
        b"\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e\xd9"
    )
    f = io.BytesIO(jpeg_bytes)
    f.name = "test.jpg"
    f.seek(0)
    resp = client.post(
        f"/api/v1/chat/rooms/{room.id}/upload/",
        {"file": f},
        format="multipart",
    )
    assert resp.status_code == 200
    assert "url" in resp.data["data"]
    assert resp.data["data"]["url"].startswith("/media/chat/images/")


@pytest.mark.django_db
def test_upload_too_large_rejected(trainer_setup):
    _, _, room, client = trainer_setup
    big_file = io.BytesIO(b"x" * (2 * 1024 * 1024 + 1))
    big_file.name = "big.jpg"
    big_file.content_type = "image/jpeg"
    resp = client.post(
        f"/api/v1/chat/rooms/{room.id}/upload/",
        {"file": big_file},
        format="multipart",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_upload_non_image_rejected(trainer_setup):
    _, _, room, client = trainer_setup
    pdf_file = io.BytesIO(b"%PDF-1.4 test content")
    pdf_file.name = "doc.pdf"
    resp = client.post(
        f"/api/v1/chat/rooms/{room.id}/upload/",
        {"file": pdf_file},
        format="multipart",
    )
    assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Message delete
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_sender_can_delete_own_message(trainer_setup, client_in_chatroom):
    _, _, room, _ = trainer_setup
    client_user, _, client_api = client_in_chatroom
    msg = Message.objects.create(
        chatroom=room, sender=client_user, content="My message"
    )
    resp = client_api.delete(f"/api/v1/chat/rooms/{room.id}/messages/{msg.id}/")
    assert resp.status_code == 200
    msg.refresh_from_db()
    assert msg.is_deleted is True
    assert msg.content == ""


@pytest.mark.django_db
def test_admin_can_delete_any_message(trainer_setup, client_in_chatroom):
    admin_user, _, room, admin_client = trainer_setup
    client_user, _, _ = client_in_chatroom
    msg = Message.objects.create(
        chatroom=room, sender=client_user, content="Client msg"
    )
    resp = admin_client.delete(f"/api/v1/chat/rooms/{room.id}/messages/{msg.id}/")
    assert resp.status_code == 200
    msg.refresh_from_db()
    assert msg.is_deleted is True


@pytest.mark.django_db
def test_non_admin_cannot_delete_others_message(trainer_setup, client_in_chatroom):
    admin_user, _, room, admin_client = trainer_setup
    client_user, _, client_api = client_in_chatroom
    # Admin posts a message
    msg = Message.objects.create(chatroom=room, sender=admin_user, content="Admin msg")
    # Client tries to delete it
    resp = client_api.delete(f"/api/v1/chat/rooms/{room.id}/messages/{msg.id}/")
    assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Pin / unpin
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_admin_can_pin_message(trainer_setup):
    admin_user, _, room, admin_client = trainer_setup
    msg = Message.objects.create(chatroom=room, sender=admin_user, content="Pin me")
    resp = admin_client.post(f"/api/v1/chat/rooms/{room.id}/pin/{msg.id}/")
    assert resp.status_code == 201
    assert PinnedMessage.objects.filter(chatroom=room, message=msg).exists()


@pytest.mark.django_db
def test_pin_same_message_twice_is_idempotent(trainer_setup):
    admin_user, _, room, admin_client = trainer_setup
    msg = Message.objects.create(
        chatroom=room, sender=admin_user, content="Pin me twice"
    )
    admin_client.post(f"/api/v1/chat/rooms/{room.id}/pin/{msg.id}/")
    resp = admin_client.post(f"/api/v1/chat/rooms/{room.id}/pin/{msg.id}/")
    assert resp.status_code == 200
    assert PinnedMessage.objects.filter(chatroom=room, message=msg).count() == 1


@pytest.mark.django_db
def test_admin_can_unpin_message(trainer_setup):
    admin_user, _, room, admin_client = trainer_setup
    msg = Message.objects.create(chatroom=room, sender=admin_user, content="Unpin me")
    PinnedMessage.objects.create(chatroom=room, message=msg, pinned_by=admin_user)
    resp = admin_client.delete(f"/api/v1/chat/rooms/{room.id}/unpin/{msg.id}/")
    assert resp.status_code == 200
    assert not PinnedMessage.objects.filter(chatroom=room, message=msg).exists()


@pytest.mark.django_db
def test_non_admin_cannot_pin(trainer_setup):
    admin_user, _, room, _ = trainer_setup
    _, _, client_api = _make_client_member(room)
    msg = Message.objects.create(chatroom=room, sender=admin_user, content="Cannot pin")
    resp = client_api.post(f"/api/v1/chat/rooms/{room.id}/pin/{msg.id}/")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_non_admin_cannot_unpin(trainer_setup):
    admin_user, _, room, _ = trainer_setup
    _, _, client_api = _make_client_member(room)
    msg = Message.objects.create(
        chatroom=room, sender=admin_user, content="Cannot unpin"
    )
    PinnedMessage.objects.create(chatroom=room, message=msg, pinned_by=admin_user)
    resp = client_api.delete(f"/api/v1/chat/rooms/{room.id}/unpin/{msg.id}/")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_get_pinned_messages_newest_first(trainer_setup):
    admin_user, _, room, admin_client = trainer_setup
    msg1 = Message.objects.create(
        chatroom=room, sender=admin_user, content="First pinned"
    )
    msg2 = Message.objects.create(
        chatroom=room, sender=admin_user, content="Second pinned"
    )
    PinnedMessage.objects.create(chatroom=room, message=msg1, pinned_by=admin_user)
    PinnedMessage.objects.create(chatroom=room, message=msg2, pinned_by=admin_user)
    resp = admin_client.get(f"/api/v1/chat/rooms/{room.id}/pin/")
    assert resp.status_code == 200
    ids = [p["message"]["id"] for p in resp.data["data"]]
    # msg2 was pinned after msg1 → appears first
    assert ids.index(msg2.id) < ids.index(msg1.id)


# ─────────────────────────────────────────────────────────────────────────────
# Mark read / unread count
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_mark_read_updates_last_read_at(trainer_setup, client_in_chatroom):
    _, _, room, _ = trainer_setup
    client_user, _, client_api = client_in_chatroom
    member = ChatroomMember.objects.get(chatroom=room, user=client_user)
    assert member.last_read_at is None
    resp = client_api.post(f"/api/v1/chat/rooms/{room.id}/read/")
    assert resp.status_code == 200
    member.refresh_from_db()
    assert member.last_read_at is not None


@pytest.mark.django_db
def test_unread_count_correct(trainer_setup, client_in_chatroom):
    admin_user, _, room, _ = trainer_setup
    client_user, _, client_api = client_in_chatroom
    Message.objects.create(chatroom=room, sender=admin_user, content="Msg 1")
    Message.objects.create(chatroom=room, sender=admin_user, content="Msg 2")
    resp = client_api.get(f"/api/v1/chat/rooms/{room.id}/unread/")
    assert resp.status_code == 200
    assert resp.data["data"]["unread_count"] == 2


@pytest.mark.django_db
def test_unread_count_excludes_own_messages(trainer_setup):
    admin_user, _, room, admin_client = trainer_setup
    Message.objects.create(chatroom=room, sender=admin_user, content="My own msg")
    resp = admin_client.get(f"/api/v1/chat/rooms/{room.id}/unread/")
    assert resp.data["data"]["unread_count"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Mute
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_mute_sets_muted_until(trainer_setup, client_in_chatroom):
    _, _, room, _ = trainer_setup
    client_user, _, client_api = client_in_chatroom
    resp = client_api.post(f"/api/v1/chat/rooms/{room.id}/mute/", {"hours": 8})
    assert resp.status_code == 200
    member = ChatroomMember.objects.get(chatroom=room, user=client_user)
    assert member.muted_until is not None


@pytest.mark.django_db
def test_unmute_clears_muted_until(trainer_setup, client_in_chatroom):
    _, _, room, _ = trainer_setup
    client_user, _, client_api = client_in_chatroom
    member = ChatroomMember.objects.get(chatroom=room, user=client_user)
    member.muted_until = timezone.now() + timezone.timedelta(hours=8)
    member.save()
    resp = client_api.post(f"/api/v1/chat/rooms/{room.id}/mute/", {"hours": 0})
    assert resp.status_code == 200
    member.refresh_from_db()
    assert member.muted_until is None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


_counter = 0


def _make_client_member(room):
    global _counter
    _counter += 1
    client_user, client_profile = make_client_user(
        email=f"chatmember{_counter}@test.com",
        name=f"Member {_counter}",
    )
    add_member(room, client_user)
    api = auth_client(client_user)
    return client_user, client_profile, api


def _make_removed_member(room):
    global _counter
    _counter += 1
    client_user, client_profile = make_client_user(
        email=f"removed{_counter}@test.com",
        name=f"Removed {_counter}",
    )
    member = add_member(room, client_user)
    member.is_active = False
    member.save()
    api = auth_client(client_user)
    return client_user, client_profile, api
