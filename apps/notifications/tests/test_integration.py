"""
Integration tests — chat consumers create Notification records and trigger
send_push_notification.delay when messages are saved.

Uses transaction=True (required for database_sync_to_async in tests).
"""

from unittest.mock import patch

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model

from apps.chat.models import Chatroom, ChatroomMember
from apps.clients.models import ClientMembership
from apps.notifications.models import Notification
from apps.profiles.models import ClientProfile, TrainerProfile

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


async def _make_user(role, email, display_name="User"):
    return await sync_to_async(User.objects.create_user)(
        email=email,
        password="Test1234!",
        role=role,
        display_name=display_name,
        is_email_verified=True,
        is_active=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Chatroom notification
# ─────────────────────────────────────────────────────────────────────────────


async def test_chat_message_creates_notifications_for_members():
    trainer_user = await _make_user("trainer", "trainer@integ.test", "Trainer")
    trainer_profile = await sync_to_async(TrainerProfile.objects.create)(
        user=trainer_user,
        full_name="Trainer",
        is_published=True,
        trainer_type="independent",
    )
    client_user = await _make_user("client", "client@integ.test", "Client")
    client_profile = await sync_to_async(ClientProfile.objects.create)(
        user=client_user, display_name="Client"
    )
    await sync_to_async(ClientMembership.objects.create)(
        client=client_profile, trainer=trainer_profile, status="active"
    )
    room, _ = await sync_to_async(Chatroom.objects.get_or_create)(
        trainer=trainer_profile, defaults={"name": "Test Room"}
    )
    await sync_to_async(ChatroomMember.objects.get_or_create)(
        chatroom=room,
        user=client_user,
        defaults={"role": ChatroomMember.Role.MEMBER, "is_active": True},
    )

    with patch("apps.notifications.tasks.send_push_notification.delay") as mock_delay:
        from apps.chat.consumers import ChatroomConsumer

        consumer = ChatroomConsumer.__new__(ChatroomConsumer)
        consumer.chatroom_id = room.id
        consumer.user = trainer_user

        msg = type("Msg", (), {"content": "Hello members!", "id": 999})()
        await consumer._notify_offline_members(msg)

    notif_exists = await sync_to_async(
        Notification.objects.filter(
            recipient=client_user,
            sender=trainer_user,
            notification_type="chat_message",
        ).exists
    )()
    assert notif_exists
    mock_delay.assert_called_once()


async def test_chat_message_push_delay_called_with_correct_args():
    trainer_user = await _make_user("trainer", "trainer2@integ.test", "Trainer2")
    trainer_profile = await sync_to_async(TrainerProfile.objects.create)(
        user=trainer_user,
        full_name="Trainer2",
        is_published=True,
        trainer_type="independent",
    )
    client_user = await _make_user("client", "client2@integ.test", "Client2")
    client_profile = await sync_to_async(ClientProfile.objects.create)(
        user=client_user, display_name="Client2"
    )
    await sync_to_async(ClientMembership.objects.create)(
        client=client_profile, trainer=trainer_profile, status="active"
    )
    room, _ = await sync_to_async(Chatroom.objects.get_or_create)(
        trainer=trainer_profile, defaults={"name": "Room2"}
    )
    await sync_to_async(ChatroomMember.objects.get_or_create)(
        chatroom=room,
        user=client_user,
        defaults={"role": ChatroomMember.Role.MEMBER, "is_active": True},
    )

    with patch("apps.notifications.tasks.send_push_notification.delay") as mock_delay:
        from apps.chat.consumers import ChatroomConsumer

        consumer = ChatroomConsumer.__new__(ChatroomConsumer)
        consumer.chatroom_id = room.id
        consumer.user = trainer_user

        msg = type("Msg", (), {"content": "Push test", "id": 998})()
        await consumer._notify_offline_members(msg)

    assert mock_delay.called
    call_args = str(mock_delay.call_args)
    assert str(client_user.id) in call_args


# ─────────────────────────────────────────────────────────────────────────────
# DM notification
# ─────────────────────────────────────────────────────────────────────────────


async def test_dm_creates_notification_for_recipient():
    trainer_user = await _make_user("trainer", "trainer3@integ.test", "Trainer3")
    trainer_profile = await sync_to_async(TrainerProfile.objects.create)(
        user=trainer_user,
        full_name="Trainer3",
        is_published=True,
        trainer_type="independent",
    )
    client_user = await _make_user("client", "client3@integ.test", "Client3")
    client_profile = await sync_to_async(ClientProfile.objects.create)(
        user=client_user, display_name="Client3"
    )
    await sync_to_async(ClientMembership.objects.create)(
        client=client_profile, trainer=trainer_profile, status="active"
    )

    from apps.chat.models import DirectMessage, get_or_create_dm_thread

    thread = await sync_to_async(get_or_create_dm_thread)(trainer_user, client_user)
    msg = await sync_to_async(DirectMessage.objects.create)(
        thread=thread,
        sender=trainer_user,
        content="Hey there!",
    )

    with patch("apps.notifications.tasks.send_push_notification.delay") as mock_delay:
        from apps.chat.consumers import DirectMessageConsumer

        consumer = DirectMessageConsumer.__new__(DirectMessageConsumer)
        consumer.user = trainer_user
        consumer._other_user = client_user

        await consumer._notify_dm_recipient(msg)

    notif_exists = await sync_to_async(
        Notification.objects.filter(
            recipient=client_user,
            sender=trainer_user,
            notification_type="direct_message",
        ).exists
    )()
    assert notif_exists
    mock_delay.assert_called_once()


async def test_dm_push_delay_called_with_recipient_id():
    trainer_user = await _make_user("trainer", "trainer4@integ.test", "Trainer4")
    trainer_profile = await sync_to_async(TrainerProfile.objects.create)(
        user=trainer_user,
        full_name="Trainer4",
        is_published=True,
        trainer_type="independent",
    )
    client_user = await _make_user("client", "client4@integ.test", "Client4")
    client_profile = await sync_to_async(ClientProfile.objects.create)(
        user=client_user, display_name="Client4"
    )
    await sync_to_async(ClientMembership.objects.create)(
        client=client_profile, trainer=trainer_profile, status="active"
    )

    from apps.chat.models import DirectMessage, get_or_create_dm_thread

    thread = await sync_to_async(get_or_create_dm_thread)(trainer_user, client_user)
    msg = await sync_to_async(DirectMessage.objects.create)(
        thread=thread,
        sender=trainer_user,
        content="Hey again!",
    )

    with patch("apps.notifications.tasks.send_push_notification.delay") as mock_delay:
        from apps.chat.consumers import DirectMessageConsumer

        consumer = DirectMessageConsumer.__new__(DirectMessageConsumer)
        consumer.user = trainer_user
        consumer._other_user = client_user

        await consumer._notify_dm_recipient(msg)

    assert mock_delay.called
    call_args = str(mock_delay.call_args)
    assert str(client_user.id) in call_args
