"""
Chat app serializers.
"""

from django.utils import timezone
from rest_framework import serializers

from apps.chat.models import (
    Chatroom,
    ChatroomMember,
    DirectMessage,
    DirectMessageThread,
    Message,
    PinnedMessage,
)


class SenderSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    display_name = serializers.CharField()
    role = serializers.CharField()
    profile_photo_url = serializers.SerializerMethodField()
    sender_type = serializers.SerializerMethodField()

    def get_profile_photo_url(self, user):
        try:
            if user.role == "trainer":
                return user.trainer_profile.profile_photo_url or ""
            elif user.role == "gym":
                return user.gym_profile.logo_url or ""
            elif user.role == "client":
                return user.client_profile.profile_photo_url or ""
        except Exception:
            pass
        return ""

    def get_sender_type(self, user):
        if user.role == "gym":
            return "gym"
        elif user.role == "trainer":
            try:
                if user.trainer_profile.trainer_type == "gym_trainer":
                    return "gym_trainer"
            except Exception:
                pass
            return "independent_trainer"
        return "client"


class _ShallowMessageSerializer(serializers.ModelSerializer):
    """Minimal nested serializer for reply_to to avoid deep recursion."""

    sender = SenderSerializer(read_only=True)
    content = serializers.SerializerMethodField()
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "sender",
            "content",
            "message_type",
            "attachment_url",
            "sent_at",
        ]

    def get_content(self, obj):
        return None if obj.is_deleted else obj.content

    def get_attachment_url(self, obj):
        return None if obj.is_deleted else obj.attachment_url


class MessageSerializer(serializers.ModelSerializer):
    sender = SenderSerializer(read_only=True)
    reply_to = _ShallowMessageSerializer(read_only=True)
    content = serializers.SerializerMethodField()
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "sender",
            "content",
            "message_type",
            "attachment_url",
            "audience",
            "scheduled_at",
            "target_user_id",
            "is_deleted",
            "reply_to",
            "sent_at",
        ]

    def get_content(self, obj):
        return None if obj.is_deleted else obj.content

    def get_attachment_url(self, obj):
        return None if obj.is_deleted else obj.attachment_url


class PinnedMessageSerializer(serializers.ModelSerializer):
    message = MessageSerializer(read_only=True)
    pinned_by = SenderSerializer(read_only=True)

    class Meta:
        model = PinnedMessage
        fields = ["id", "message", "pinned_by", "pinned_at"]


class ChatroomMemberSerializer(serializers.ModelSerializer):
    user = SenderSerializer(read_only=True)
    membership_status = serializers.SerializerMethodField()

    class Meta:
        model = ChatroomMember
        fields = [
            "id",
            "user",
            "role",
            "is_active",
            "last_read_at",
            "joined_at",
            "membership_status",
        ]

    def get_membership_status(self, obj):
        from apps.clients.models import ClientMembership

        chatroom = obj.chatroom
        user = obj.user

        if chatroom.trainer_id:
            try:
                m = ClientMembership.objects.get(
                    client__user=user,
                    trainer_id=chatroom.trainer_id,
                )
                return m.status
            except ClientMembership.DoesNotExist:
                pass
        elif chatroom.gym_id:
            try:
                m = ClientMembership.objects.get(
                    client__user=user,
                    gym_id=chatroom.gym_id,
                )
                return m.status
            except ClientMembership.DoesNotExist:
                pass
        return None


class ChatroomSerializer(serializers.ModelSerializer):
    pinned_messages = PinnedMessageSerializer(many=True, read_only=True)
    owner_type = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()
    owner_photo_url = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()
    is_muted = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Chatroom
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "zoom_link",
            "member_count",
            "pinned_messages",
            "owner_type",
            "owner_name",
            "owner_photo_url",
            "my_role",
            "is_muted",
            "unread_count",
            "created_at",
        ]

    def _get_member(self, chatroom):
        request = self.context.get("request")
        if not request:
            return None
        try:
            return ChatroomMember.objects.get(chatroom=chatroom, user=request.user)
        except ChatroomMember.DoesNotExist:
            return None

    def get_owner_type(self, obj):
        return "trainer" if obj.trainer_id else "gym"

    def get_owner_name(self, obj):
        if obj.trainer_id:
            return obj.trainer.full_name
        return obj.gym.gym_name

    def get_owner_photo_url(self, obj):
        if obj.trainer_id:
            return obj.trainer.profile_photo_url or ""
        return obj.gym.logo_url or ""

    def get_my_role(self, obj):
        member = self._get_member(obj)
        return member.role if member else None

    def get_is_muted(self, obj):
        member = self._get_member(obj)
        if member and member.muted_until:
            return member.muted_until > timezone.now()
        return False

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if not request:
            return 0
        member = self._get_member(obj)
        if not member:
            return 0
        from django.db.models import Q

        qs = (
            Message.objects.filter(
                chatroom=obj,
                is_deleted=False,
            )
            .exclude(sender=request.user)
            .filter(
                Q(audience=Message.Audience.FULL_GROUP) | Q(target_user=request.user)
            )
        )
        if member.last_read_at:
            qs = qs.filter(sent_at__gt=member.last_read_at)
        return qs.count()


class DirectMessageSerializer(serializers.ModelSerializer):
    sender = SenderSerializer(read_only=True)

    class Meta:
        model = DirectMessage
        fields = [
            "id",
            "sender",
            "content",
            "message_type",
            "attachment_url",
            "is_deleted",
            "read_at",
            "sent_at",
        ]


class DMThreadSerializer(serializers.ModelSerializer):
    other_user = serializers.SerializerMethodField()
    last_message = DirectMessageSerializer(read_only=True)
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = DirectMessageThread
        fields = [
            "id",
            "other_user",
            "last_message",
            "unread_count",
            "updated_at",
        ]

    def get_other_user(self, obj):
        request = self.context.get("request")
        if not request:
            return None
        other = obj.get_other_user(request.user)
        return SenderSerializer(other, context=self.context).data

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if not request:
            return 0
        return obj.get_unread_count(request.user)
