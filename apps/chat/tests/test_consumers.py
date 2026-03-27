"""
WebSocket consumer tests — ChatroomConsumer and DirectMessageConsumer.
Uses InMemoryChannelLayer to avoid Redis dependency in tests.

A test-specific ASGI application is built directly (without
AllowedHostsOriginValidator) so that close-code semantics are predictable
in the test environment.
"""

import json

import pytest
from asgiref.sync import sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test.utils import override_settings
from rest_framework_simplejwt.tokens import AccessToken

from apps.chat.middleware import JWTAuthMiddleware
from apps.chat.routing import websocket_urlpatterns
from apps.chat.tests.conftest import (
    CHANNEL_LAYERS_TEST,
    add_member,
    make_client_user,
    make_membership,
    make_trainer_user,
)

pytestmark = pytest.mark.django_db(transaction=True)

# Build the test application once — channels.layers override is applied per test
_ws_application = JWTAuthMiddleware(URLRouter(websocket_urlpatterns))


def _token(user):
    return str(AccessToken.for_user(user))


def _room_url(room_id, token=None):
    if token:
        return f"/ws/chat/room/{room_id}/?token={token}"
    return f"/ws/chat/room/{room_id}/"


def _dm_url(user_id, token=None):
    if token:
        return f"/ws/chat/dm/{user_id}/?token={token}"
    return f"/ws/chat/dm/{user_id}/"


# ─────────────────────────────────────────────────────────────────────────────
# ChatroomConsumer — connection / auth
# ─────────────────────────────────────────────────────────────────────────────


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
async def test_authenticated_user_connects_to_chatroom():
    t_user, t_profile = await sync_to_async(make_trainer_user)(
        email="ws_trainer1@test.com"
    )
    from apps.chat.models import Chatroom

    room = await sync_to_async(Chatroom.objects.get)(trainer=t_profile)
    comm = WebsocketCommunicator(_ws_application, _room_url(room.id, _token(t_user)))
    connected, _ = await comm.connect()
    assert connected
    await comm.disconnect()


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
async def test_no_token_closes_4001():
    comm = WebsocketCommunicator(_ws_application, "/ws/chat/room/99/")
    connected, code = await comm.connect()
    assert not connected
    assert code == 4001


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
async def test_invalid_token_closes_4001():
    comm = WebsocketCommunicator(
        _ws_application, "/ws/chat/room/99/?token=not_a_valid_jwt"
    )
    connected, code = await comm.connect()
    assert not connected
    assert code == 4001


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
async def test_non_member_closes_4003():
    t_user, t_profile = await sync_to_async(make_trainer_user)(
        email="ws_trainer2@test.com"
    )
    from apps.chat.models import Chatroom

    room = await sync_to_async(Chatroom.objects.get)(trainer=t_profile)
    outsider, _ = await sync_to_async(make_client_user)(email="ws_outsider@test.com")
    comm = WebsocketCommunicator(_ws_application, _room_url(room.id, _token(outsider)))
    connected, code = await comm.connect()
    assert not connected
    assert code == 4003


# ─────────────────────────────────────────────────────────────────────────────
# ChatroomConsumer — messaging
# ─────────────────────────────────────────────────────────────────────────────


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
async def test_send_message_broadcast_to_members():
    t_user, t_profile = await sync_to_async(make_trainer_user)(
        email="ws_trainer3@test.com"
    )
    from apps.chat.models import Chatroom

    room = await sync_to_async(Chatroom.objects.get)(trainer=t_profile)
    c_user, c_profile = await sync_to_async(make_client_user)(
        email="ws_client1@test.com"
    )
    await sync_to_async(make_membership)(c_profile, trainer=t_profile)
    await sync_to_async(add_member)(room, c_user)

    comm1 = WebsocketCommunicator(_ws_application, _room_url(room.id, _token(t_user)))
    comm2 = WebsocketCommunicator(_ws_application, _room_url(room.id, _token(c_user)))
    await comm1.connect()
    await comm2.connect()

    await comm1.send_json_to({"type": "message.send", "content": "Hello!"})

    msg1 = json.loads(await comm1.receive_from())
    msg2 = json.loads(await comm2.receive_from())
    assert msg1["type"] == "message.new"
    assert msg2["type"] == "message.new"
    assert msg1["content"] == "Hello!"

    await comm1.disconnect()
    await comm2.disconnect()


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
async def test_removed_member_can_connect_but_cannot_send():
    t_user, t_profile = await sync_to_async(make_trainer_user)(
        email="ws_trainer4@test.com"
    )
    from apps.chat.models import Chatroom

    room = await sync_to_async(Chatroom.objects.get)(trainer=t_profile)
    c_user, c_profile = await sync_to_async(make_client_user)(
        email="ws_removed1@test.com"
    )
    await sync_to_async(make_membership)(c_profile, trainer=t_profile)
    member = await sync_to_async(add_member)(room, c_user)
    member.is_active = False
    await sync_to_async(member.save)()

    comm = WebsocketCommunicator(_ws_application, _room_url(room.id, _token(c_user)))
    connected, _ = await comm.connect()
    assert connected  # removed members can connect (read-only)

    await comm.send_json_to({"type": "message.send", "content": "Ghost"})
    response = json.loads(await comm.receive_from())
    assert response["type"] == "error"
    assert response["code"] == "removed"

    await comm.disconnect()


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
async def test_non_admin_cannot_send_announcement():
    t_user, t_profile = await sync_to_async(make_trainer_user)(
        email="ws_trainer5@test.com"
    )
    from apps.chat.models import Chatroom

    room = await sync_to_async(Chatroom.objects.get)(trainer=t_profile)
    c_user, c_profile = await sync_to_async(make_client_user)(
        email="ws_member2@test.com"
    )
    await sync_to_async(make_membership)(c_profile, trainer=t_profile)
    await sync_to_async(add_member)(room, c_user)

    comm = WebsocketCommunicator(_ws_application, _room_url(room.id, _token(c_user)))
    await comm.connect()

    await comm.send_json_to(
        {
            "type": "message.send",
            "content": "Fake announcement",
            "message_type": "announcement",
        }
    )
    response = json.loads(await comm.receive_from())
    assert response["type"] == "error"
    assert response["code"] == "forbidden"

    await comm.disconnect()


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
async def test_admin_can_send_announcement():
    t_user, t_profile = await sync_to_async(make_trainer_user)(
        email="ws_trainer5b@test.com"
    )
    from apps.chat.models import Chatroom

    room = await sync_to_async(Chatroom.objects.get)(trainer=t_profile)
    comm = WebsocketCommunicator(_ws_application, _room_url(room.id, _token(t_user)))
    await comm.connect()
    await comm.send_json_to(
        {
            "type": "message.send",
            "content": "Big news",
            "message_type": "announcement",
        }
    )
    msg = json.loads(await comm.receive_from())
    assert msg["type"] == "message.new"
    assert msg["message_type"] == "announcement"
    await comm.disconnect()


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
async def test_individual_message_only_to_sender_and_target():
    t_user, t_profile = await sync_to_async(make_trainer_user)(
        email="ws_trainer6@test.com"
    )
    from apps.chat.models import Chatroom

    room = await sync_to_async(Chatroom.objects.get)(trainer=t_profile)
    c1_user, c1_profile = await sync_to_async(make_client_user)(email="ws_c1@test.com")
    c2_user, c2_profile = await sync_to_async(make_client_user)(email="ws_c2@test.com")
    await sync_to_async(make_membership)(c1_profile, trainer=t_profile)
    await sync_to_async(make_membership)(c2_profile, trainer=t_profile)
    await sync_to_async(add_member)(room, c1_user)
    await sync_to_async(add_member)(room, c2_user)

    comm_t = WebsocketCommunicator(_ws_application, _room_url(room.id, _token(t_user)))
    comm_c1 = WebsocketCommunicator(
        _ws_application, _room_url(room.id, _token(c1_user))
    )
    comm_c2 = WebsocketCommunicator(
        _ws_application, _room_url(room.id, _token(c2_user))
    )
    await comm_t.connect()
    await comm_c1.connect()
    await comm_c2.connect()

    await comm_t.send_json_to(
        {
            "type": "message.send",
            "content": "Private to c1",
            "audience": "individual",
            "target_user_id": str(c1_user.id),
        }
    )

    msg_t = json.loads(await comm_t.receive_from())
    msg_c1 = json.loads(await comm_c1.receive_from())
    assert msg_t["type"] == "message.new"
    assert msg_c1["type"] == "message.new"
    # c2 should NOT receive the individual message
    assert await comm_c2.receive_nothing()

    await comm_t.disconnect()
    await comm_c1.disconnect()
    await comm_c2.disconnect()


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
async def test_typing_indicator_not_sent_to_self():
    t_user, t_profile = await sync_to_async(make_trainer_user)(
        email="ws_trainer7@test.com"
    )
    from apps.chat.models import Chatroom

    room = await sync_to_async(Chatroom.objects.get)(trainer=t_profile)
    c_user, c_profile = await sync_to_async(make_client_user)(email="ws_typer@test.com")
    await sync_to_async(make_membership)(c_profile, trainer=t_profile)
    await sync_to_async(add_member)(room, c_user)

    comm_t = WebsocketCommunicator(_ws_application, _room_url(room.id, _token(t_user)))
    comm_c = WebsocketCommunicator(_ws_application, _room_url(room.id, _token(c_user)))
    await comm_t.connect()
    await comm_c.connect()

    await comm_t.send_json_to({"type": "typing.start"})

    event = json.loads(await comm_c.receive_from())
    assert event["type"] == "typing.indicator"
    assert event["is_typing"] is True
    # Trainer does NOT receive their own typing event
    assert await comm_t.receive_nothing()

    await comm_t.disconnect()
    await comm_c.disconnect()


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
async def test_message_delete_broadcasts_deletion():
    t_user, t_profile = await sync_to_async(make_trainer_user)(
        email="ws_trainer8@test.com"
    )
    from apps.chat.models import Chatroom, Message

    room = await sync_to_async(Chatroom.objects.get)(trainer=t_profile)
    c_user, c_profile = await sync_to_async(make_client_user)(email="ws_del1@test.com")
    await sync_to_async(make_membership)(c_profile, trainer=t_profile)
    await sync_to_async(add_member)(room, c_user)

    msg = await sync_to_async(Message.objects.create)(
        chatroom=room, sender=t_user, content="Delete me"
    )

    comm_t = WebsocketCommunicator(_ws_application, _room_url(room.id, _token(t_user)))
    comm_c = WebsocketCommunicator(_ws_application, _room_url(room.id, _token(c_user)))
    await comm_t.connect()
    await comm_c.connect()

    await comm_t.send_json_to({"type": "message.delete", "message_id": msg.id})

    del_t = json.loads(await comm_t.receive_from())
    del_c = json.loads(await comm_c.receive_from())
    assert del_t["type"] == "message.deleted"
    assert del_c["type"] == "message.deleted"

    await comm_t.disconnect()
    await comm_c.disconnect()


# ─────────────────────────────────────────────────────────────────────────────
# DirectMessageConsumer
# ─────────────────────────────────────────────────────────────────────────────


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
async def test_dm_valid_connection():
    t_user, t_profile = await sync_to_async(make_trainer_user)(
        email="ws_dm_t1@test.com"
    )
    c_user, c_profile = await sync_to_async(make_client_user)(email="ws_dm_c1@test.com")
    await sync_to_async(make_membership)(c_profile, trainer=t_profile)

    comm = WebsocketCommunicator(_ws_application, _dm_url(c_user.id, _token(t_user)))
    connected, _ = await comm.connect()
    assert connected
    await comm.disconnect()


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
async def test_dm_no_shared_community_closes_4003():
    t_user, t_profile = await sync_to_async(make_trainer_user)(
        email="ws_dm_t2@test.com"
    )
    outsider, _ = await sync_to_async(make_client_user)(email="ws_dm_out@test.com")
    comm = WebsocketCommunicator(_ws_application, _dm_url(outsider.id, _token(t_user)))
    connected, code = await comm.connect()
    assert not connected
    assert code == 4003


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
async def test_dm_send_both_users_receive():
    t_user, t_profile = await sync_to_async(make_trainer_user)(
        email="ws_dm_t3@test.com"
    )
    c_user, c_profile = await sync_to_async(make_client_user)(email="ws_dm_c3@test.com")
    await sync_to_async(make_membership)(c_profile, trainer=t_profile)

    comm_t = WebsocketCommunicator(_ws_application, _dm_url(c_user.id, _token(t_user)))
    comm_c = WebsocketCommunicator(_ws_application, _dm_url(t_user.id, _token(c_user)))
    await comm_t.connect()
    await comm_c.connect()

    await comm_t.send_json_to({"type": "message.send", "content": "Hey client!"})

    msg_t = json.loads(await comm_t.receive_from())
    msg_c = json.loads(await comm_c.receive_from())
    assert msg_t["type"] == "message.new"
    assert msg_c["type"] == "message.new"
    assert msg_t["content"] == "Hey client!"

    await comm_t.disconnect()
    await comm_c.disconnect()


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
async def test_dm_read_marks_messages_read():
    t_user, t_profile = await sync_to_async(make_trainer_user)(
        email="ws_dm_t4@test.com"
    )
    c_user, c_profile = await sync_to_async(make_client_user)(email="ws_dm_c4@test.com")
    await sync_to_async(make_membership)(c_profile, trainer=t_profile)

    comm_t = WebsocketCommunicator(_ws_application, _dm_url(c_user.id, _token(t_user)))
    comm_c = WebsocketCommunicator(_ws_application, _dm_url(t_user.id, _token(c_user)))
    await comm_t.connect()
    await comm_c.connect()

    # Trainer sends a message
    await comm_t.send_json_to({"type": "message.send", "content": "Unread msg"})
    # Drain the broadcast
    await comm_t.receive_from()
    await comm_c.receive_from()

    # Client marks thread as read
    await comm_c.send_json_to({"type": "message.read"})
    # Small pause so the DB update completes before we assert
    import asyncio

    await asyncio.sleep(0.1)

    from apps.chat.models import DirectMessageThread

    thread = await sync_to_async(DirectMessageThread.objects.get)(
        user_1__in=[t_user, c_user], user_2__in=[t_user, c_user]
    )
    if thread.user_1_id == c_user.id:
        assert thread.user_1_unread == 0
    else:
        assert thread.user_2_unread == 0

    await comm_t.disconnect()
    await comm_c.disconnect()
