"""
Chat WebSocket consumers — ChatroomConsumer (CHAT-01) and
DirectMessageConsumer (CHAT-03).
"""

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer


class ChatroomConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.chatroom_id = self.scope["url_route"]["kwargs"]["chatroom_id"]
        self.room_group_name = f"chat_room_{self.chatroom_id}"
        self.user = self.scope["user"]

        is_member = await self._is_any_member()
        if not is_member:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_error("invalid_json", "Invalid JSON.")
            return

        handlers = {
            "message.send": self.handle_message_send,
            "message.delete": self.handle_message_delete,
            "message.read": self.handle_message_read,
            "typing.start": lambda d: self.handle_typing(True),
            "typing.stop": lambda d: self.handle_typing(False),
        }
        handler = handlers.get(data.get("type"))
        if handler:
            await handler(data)
        else:
            await self.send_error(
                "unknown_event",
                f"Unknown event: {data.get('type')}",
            )

    async def handle_message_send(self, data):
        is_active = await self._is_active_member()
        if not is_active:
            await self.send_error(
                "removed",
                "You are no longer a member of this community.",
            )
            return

        content = data.get("content", "").strip()
        message_type = data.get("message_type", "text")
        attachment_url = data.get("attachment_url", "")
        reply_to_id = data.get("reply_to_id")
        audience = data.get("audience", "full_group")
        target_user_id = data.get("target_user_id")
        scheduled_at = data.get("scheduled_at")

        if not content and not attachment_url:
            await self.send_error(
                "empty_message",
                "Message must have content or attachment.",
            )
            return

        admin_types = {"announcement", "reminder", "motivation", "zoom_link"}
        if message_type in admin_types:
            is_admin = await self._is_admin()
            if not is_admin:
                await self.send_error(
                    "forbidden",
                    "Only admins can send this message type.",
                )
                return

        message = await self._save_message(
            content=content,
            message_type=message_type,
            attachment_url=attachment_url,
            reply_to_id=reply_to_id,
            audience=audience,
            target_user_id=target_user_id,
            scheduled_at=scheduled_at,
        )

        serialized = await self._serialize_message(message)

        if audience == "individual" and target_user_id:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "broadcast_individual_message",
                    "message": serialized,
                    "sender_id": str(self.user.id),
                    "target_user_id": str(target_user_id),
                },
            )
        else:
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "broadcast_message", "message": serialized},
            )

    async def handle_message_delete(self, data):
        message_id = data.get("message_id")
        if not message_id:
            return
        deleted = await self._delete_message(message_id)
        if not deleted:
            await self.send_error("forbidden", "Cannot delete.")
            return
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "broadcast_deletion", "message_id": message_id},
        )

    async def handle_message_read(self, data):
        await self._update_last_read()

    async def handle_typing(self, is_typing):
        is_active = await self._is_active_member()
        if not is_active:
            return
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_typing",
                "user_id": str(self.user.id),
                "display_name": self.user.display_name,
                "is_typing": is_typing,
            },
        )

    # ── Broadcast handlers ────────────────────────────────────────────────────

    async def broadcast_message(self, event):
        await self.send(
            text_data=json.dumps({"type": "message.new", **event["message"]})
        )

    async def broadcast_individual_message(self, event):
        my_id = str(self.user.id)
        if my_id in (event["sender_id"], event["target_user_id"]):
            await self.send(
                text_data=json.dumps({"type": "message.new", **event["message"]})
            )

    async def broadcast_deletion(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message.deleted",
                    "message_id": event["message_id"],
                }
            )
        )

    async def broadcast_typing(self, event):
        if str(self.user.id) != event["user_id"]:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "typing.indicator",
                        "user_id": event["user_id"],
                        "display_name": event["display_name"],
                        "is_typing": event["is_typing"],
                    }
                )
            )

    # ── DB helpers ────────────────────────────────────────────────────────────

    @database_sync_to_async
    def _is_any_member(self):
        from apps.chat.models import ChatroomMember

        return ChatroomMember.objects.filter(
            chatroom_id=self.chatroom_id, user=self.user
        ).exists()

    @database_sync_to_async
    def _is_active_member(self):
        from apps.chat.models import ChatroomMember

        return ChatroomMember.objects.filter(
            chatroom_id=self.chatroom_id, user=self.user, is_active=True
        ).exists()

    @database_sync_to_async
    def _is_admin(self):
        from apps.chat.models import ChatroomMember

        return ChatroomMember.objects.filter(
            chatroom_id=self.chatroom_id,
            user=self.user,
            role=ChatroomMember.Role.ADMIN,
            is_active=True,
        ).exists()

    @database_sync_to_async
    def _save_message(self, **kwargs):
        from apps.chat.models import Message

        return Message.objects.create(
            chatroom_id=self.chatroom_id,
            sender=self.user,
            **kwargs,
        )

    @database_sync_to_async
    def _delete_message(self, message_id):
        from apps.chat.models import Message

        try:
            msg = Message.objects.select_related(
                "chatroom__trainer__user",
                "chatroom__gym__user",
            ).get(
                id=message_id,
                chatroom_id=self.chatroom_id,
                is_deleted=False,
            )
        except Message.DoesNotExist:
            return False

        is_sender = msg.sender_id == self.user.id
        chatroom = msg.chatroom
        is_owner = (
            chatroom.trainer_id and chatroom.trainer.user_id == self.user.id
        ) or (chatroom.gym_id and chatroom.gym.user_id == self.user.id)
        if not (is_sender or is_owner):
            return False

        msg.is_deleted = True
        msg.content = ""
        msg.attachment_url = ""
        msg.save(update_fields=["is_deleted", "content", "attachment_url"])
        return True

    @database_sync_to_async
    def _update_last_read(self):
        from django.utils import timezone

        from apps.chat.models import ChatroomMember

        ChatroomMember.objects.filter(
            chatroom_id=self.chatroom_id, user=self.user
        ).update(last_read_at=timezone.now())

    @database_sync_to_async
    def _serialize_message(self, message):
        sender_type = message.get_sender_type()
        photo = ""
        try:
            user = self.user
            if user.role == "trainer":
                photo = user.trainer_profile.profile_photo_url or ""
            elif user.role == "gym":
                photo = user.gym_profile.logo_url or ""
            elif user.role == "client":
                photo = user.client_profile.profile_photo_url or ""
        except Exception:
            pass
        return {
            "id": message.id,
            "sender_id": str(self.user.id),
            "display_name": self.user.display_name,
            "photo_url": photo,
            "sender_type": sender_type,
            "content": message.content,
            "message_type": message.message_type,
            "audience": message.audience,
            "attachment_url": message.attachment_url,
            "reply_to_id": message.reply_to_id,
            "scheduled_at": (
                message.scheduled_at.isoformat() if message.scheduled_at else None
            ),
            "sent_at": message.sent_at.isoformat(),
        }

    async def send_error(self, code, message):
        await self.send(
            text_data=json.dumps({"type": "error", "code": code, "message": message})
        )


class DirectMessageConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.other_user_id = self.scope["url_route"]["kwargs"]["user_id"]
        self.user = self.scope["user"]

        sorted_ids = sorted([str(self.user.id), str(self.other_user_id)])
        self.room_group_name = f"dm_{'_'.join(sorted_ids)}"

        is_valid = await self._validate_connection()
        if not is_valid:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return
        event_type = data.get("type")
        if event_type == "message.send":
            await self.handle_dm_send(data)
        elif event_type == "message.read":
            await self.handle_dm_read()

    async def handle_dm_send(self, data):
        content = data.get("content", "").strip()
        attachment_url = data.get("attachment_url", "")
        if not content and not attachment_url:
            return
        message = await self._save_dm(content, attachment_url)
        serialized = await self._serialize_dm(message)
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "broadcast_dm", "message": serialized},
        )

    async def handle_dm_read(self):
        await self._mark_read()

    async def broadcast_dm(self, event):
        await self.send(
            text_data=json.dumps({"type": "message.new", **event["message"]})
        )

    @database_sync_to_async
    def _validate_connection(self):
        from django.db.models import Q

        from apps.accounts.models import User
        from apps.clients.models import ClientMembership

        try:
            other = User.objects.get(id=self.other_user_id, is_active=True)
        except User.DoesNotExist:
            return False
        self._other_user = other
        user, other = self.user, other
        return (
            ClientMembership.objects.filter(deleted_at__isnull=True)
            .filter(
                Q(client__user=user, trainer__user=other)
                | Q(client__user=other, trainer__user=user)
                | Q(client__user=user, gym__user=other)
                | Q(client__user=other, gym__user=user)
            )
            .exists()
        )

    @database_sync_to_async
    def _save_dm(self, content, attachment_url=""):
        from apps.chat.models import DirectMessage, get_or_create_dm_thread

        thread = get_or_create_dm_thread(self.user, self._other_user)
        msg = DirectMessage.objects.create(
            thread=thread,
            sender=self.user,
            content=content,
            attachment_url=attachment_url,
        )
        if self.user.id == thread.user_1_id:
            thread.user_2_unread += 1
        else:
            thread.user_1_unread += 1
        thread.last_message = msg
        thread.save(update_fields=["last_message", "user_1_unread", "user_2_unread"])
        return msg

    @database_sync_to_async
    def _mark_read(self):
        from django.utils import timezone

        from apps.chat.models import DirectMessage, get_or_create_dm_thread

        thread = get_or_create_dm_thread(self.user, self._other_user)
        if self.user.id == thread.user_1_id:
            thread.user_1_unread = 0
        else:
            thread.user_2_unread = 0
        thread.save(update_fields=["user_1_unread", "user_2_unread"])
        DirectMessage.objects.filter(thread=thread, read_at__isnull=True).exclude(
            sender=self.user
        ).update(read_at=timezone.now())

    @database_sync_to_async
    def _serialize_dm(self, message):
        return {
            "id": message.id,
            "sender_id": str(self.user.id),
            "display_name": self.user.display_name,
            "content": message.content,
            "message_type": message.message_type,
            "attachment_url": message.attachment_url,
            "sent_at": message.sent_at.isoformat(),
        }
