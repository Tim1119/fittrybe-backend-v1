"""
Chat app REST views — CHAT-01 through CHAT-04.
"""

import os
import uuid

from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.chat.models import (
    Chatroom,
    ChatroomMember,
    DirectMessage,
    DirectMessageThread,
    Message,
    PinnedMessage,
    get_or_create_dm_thread,
)
from apps.chat.serializers import (
    ChatroomMemberSerializer,
    ChatroomSerializer,
    DirectMessageSerializer,
    DMThreadSerializer,
    MessageSerializer,
    PinnedMessageSerializer,
)
from apps.core.error_codes import ErrorCode
from apps.core.pagination import StandardPagination
from apps.core.responses import APIResponse

# ──────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────────────────────


def _get_chatroom_or_404(pk):
    try:
        return Chatroom.objects.get(pk=pk), None
    except Chatroom.DoesNotExist:
        return None, APIResponse.error(
            message="Chatroom not found.",
            code=ErrorCode.NOT_FOUND,
            status_code=404,
        )


def _get_any_member_or_403(chatroom, user):
    """Member with any is_active value (read-only access)."""
    try:
        return ChatroomMember.objects.get(chatroom=chatroom, user=user), None
    except ChatroomMember.DoesNotExist:
        return None, APIResponse.error(
            message="You are not a member of this chatroom.",
            code=ErrorCode.PERMISSION_DENIED,
            status_code=403,
        )


def _get_active_member_or_403(chatroom, user):
    """Active member only (write access)."""
    try:
        member = ChatroomMember.objects.get(
            chatroom=chatroom, user=user, is_active=True
        )
        return member, None
    except ChatroomMember.DoesNotExist:
        return None, APIResponse.error(
            message="You are no longer a member of this community.",
            code=ErrorCode.PERMISSION_DENIED,
            status_code=403,
        )


def _require_admin_or_403(chatroom, user):
    try:
        member = ChatroomMember.objects.get(
            chatroom=chatroom,
            user=user,
            role=ChatroomMember.Role.ADMIN,
            is_active=True,
        )
        return member, None
    except ChatroomMember.DoesNotExist:
        return None, APIResponse.error(
            message="Only admins can perform this action.",
            code=ErrorCode.PERMISSION_DENIED,
            status_code=403,
        )


# ──────────────────────────────────────────────────────────────────────────────
# CHAT-01 — Community Chatroom
# ──────────────────────────────────────────────────────────────────────────────


@extend_schema(
    summary="List my chatrooms",
    description=(
        "Returns all chatrooms the authenticated user belongs to. "
        "Includes rooms where the user is no longer active (read-only). "
        "Response includes unread count, mute status, pinned messages."
    ),
    responses={200: OpenApiResponse(description="Chatroom list")},
    tags=["Chat"],
)
class ChatroomListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = ChatroomMember.objects.filter(user=request.user).values_list(
            "chatroom_id", flat=True
        )
        rooms = Chatroom.objects.filter(pk__in=memberships).select_related(
            "trainer__user", "gym__user"
        )
        serializer = ChatroomSerializer(rooms, many=True, context={"request": request})
        return APIResponse.success(data=serializer.data)


@extend_schema(
    summary="Get chatroom detail",
    description="Returns details of a single chatroom. User must be a member.",
    responses={
        200: OpenApiResponse(description="Chatroom detail"),
        403: OpenApiResponse(description="Not a member"),
        404: OpenApiResponse(description="Chatroom not found"),
    },
    tags=["Chat"],
)
class ChatroomDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        chatroom, err = _get_chatroom_or_404(pk)
        if err:
            return err
        _, err = _get_any_member_or_403(chatroom, request.user)
        if err:
            return err
        serializer = ChatroomSerializer(chatroom, context={"request": request})
        return APIResponse.success(data=serializer.data)


@extend_schema(
    summary="Update chatroom settings",
    description=(
        "Admin can update chatroom name, description, or zoom_link. "
        "Partial updates supported — only send fields you want to change."
    ),
    request=inline_serializer(
        "ChatroomUpdateRequest",
        fields={
            "name": drf_serializers.CharField(required=False),
            "description": drf_serializers.CharField(required=False),
            "zoom_link": drf_serializers.CharField(required=False),
        },
    ),
    responses={
        200: OpenApiResponse(description="Chatroom updated"),
        403: OpenApiResponse(description="Not an admin"),
        404: OpenApiResponse(description="Chatroom not found"),
    },
    tags=["Chat"],
)
class ChatroomUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        chatroom, err = _get_chatroom_or_404(pk)
        if err:
            return err
        _, err = _require_admin_or_403(chatroom, request.user)
        if err:
            return err

        allowed = {"name", "description", "zoom_link"}
        for field in allowed:
            if field in request.data:
                setattr(chatroom, field, request.data[field])
        chatroom.save()

        serializer = ChatroomSerializer(chatroom, context={"request": request})
        return APIResponse.success(data=serializer.data)


_ADMIN_ONLY_TYPES = {"announcement", "reminder", "motivation", "zoom_link"}


@extend_schema(
    summary="List / send community messages",
    description=(
        "GET: Returns paginated message history (oldest first). "
        "Individual-audience messages are only visible to sender and target. "
        "POST: Send a message to the community. "
        "Active members only. Announcement/reminder/motivation require admin."
    ),
    responses={
        200: OpenApiResponse(description="Paginated message list"),
        201: OpenApiResponse(description="Message created"),
        400: OpenApiResponse(description="Validation error"),
        403: OpenApiResponse(description="Not a member or not an admin"),
    },
    tags=["Chat"],
)
class MessageListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        chatroom, err = _get_chatroom_or_404(pk)
        if err:
            return err
        _, err = _get_any_member_or_403(chatroom, request.user)
        if err:
            return err

        qs = (
            Message.objects.filter(chatroom=chatroom, is_deleted=False)
            .filter(
                Q(audience=Message.Audience.FULL_GROUP)
                | Q(sender=request.user)
                | Q(target_user=request.user)
            )
            .select_related("sender", "reply_to__sender", "target_user")
        )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = MessageSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, pk):
        chatroom, err = _get_chatroom_or_404(pk)
        if err:
            return err
        _, err = _get_active_member_or_403(chatroom, request.user)
        if err:
            return err

        content = request.data.get("content", "").strip()
        attachment_url = request.data.get("attachment_url", "")
        if not content and not attachment_url:
            return APIResponse.error(
                message="Message must have content or attachment_url.",
                code=ErrorCode.VALIDATION_ERROR,
                status_code=400,
            )

        message_type = request.data.get("message_type", Message.MessageType.TEXT)
        if message_type in _ADMIN_ONLY_TYPES:
            _, err = _require_admin_or_403(chatroom, request.user)
            if err:
                return err

        audience = request.data.get("audience", Message.Audience.FULL_GROUP)
        target_user_id = request.data.get("target_user_id")

        if audience == Message.Audience.INDIVIDUAL:
            if not target_user_id:
                return APIResponse.error(
                    message="target_user_id is required for individual messages.",
                    code=ErrorCode.VALIDATION_ERROR,
                    status_code=400,
                )
            if not ChatroomMember.objects.filter(
                chatroom=chatroom,
                user_id=target_user_id,
                is_active=True,
            ).exists():
                return APIResponse.error(
                    message="Target user is not an active member of this chatroom.",
                    code=ErrorCode.VALIDATION_ERROR,
                    status_code=400,
                )

        reply_to_id = request.data.get("reply_to_id")
        scheduled_at = request.data.get("scheduled_at")

        msg = Message.objects.create(
            chatroom=chatroom,
            sender=request.user,
            content=content,
            message_type=message_type,
            attachment_url=attachment_url,
            audience=audience,
            target_user_id=target_user_id,
            reply_to_id=reply_to_id,
            scheduled_at=scheduled_at,
        )
        serializer = MessageSerializer(msg, context={"request": request})
        return APIResponse.created(data=serializer.data)


@extend_schema(
    summary="Upload media to chatroom",
    description=(
        "Upload an image file (JPEG, PNG, GIF, WebP) up to 2MB. "
        "Returns the URL to use as attachment_url when sending a message. "
        "Active members only."
    ),
    responses={
        200: OpenApiResponse(description="Upload successful, returns url"),
        400: OpenApiResponse(description="Invalid file type or size"),
        403: OpenApiResponse(description="Not an active member"),
    },
    tags=["Chat"],
)
class MediaUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    MAX_SIZE = 2 * 1024 * 1024  # 2 MB

    def post(self, request, pk):
        chatroom, err = _get_chatroom_or_404(pk)
        if err:
            return err
        _, err = _get_active_member_or_403(chatroom, request.user)
        if err:
            return err

        file = request.FILES.get("file")
        if not file:
            return APIResponse.error(
                message="No file provided.",
                code=ErrorCode.VALIDATION_ERROR,
                status_code=400,
            )

        if file.content_type not in self.ALLOWED_TYPES:
            return APIResponse.error(
                message="Only JPEG, PNG, GIF, and WebP images are allowed.",
                code=ErrorCode.VALIDATION_ERROR,
                status_code=400,
            )

        if file.size > self.MAX_SIZE:
            return APIResponse.error(
                message="File size must not exceed 2MB.",
                code=ErrorCode.VALIDATION_ERROR,
                status_code=400,
            )

        ext = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else "jpg"
        filename = f"{uuid.uuid4()}.{ext}"
        upload_dir = os.path.join("chat", "images")

        from django.conf import settings as django_settings

        full_dir = os.path.join(django_settings.MEDIA_ROOT, upload_dir)
        os.makedirs(full_dir, exist_ok=True)

        full_path = os.path.join(full_dir, filename)
        with open(full_path, "wb+") as dest:
            for chunk in file.chunks():
                dest.write(chunk)

        url = f"/media/{upload_dir}/{filename}"
        return APIResponse.success(data={"url": url})


@extend_schema(
    summary="Delete a community message",
    description=(
        "Soft-deletes a message (sets is_deleted=True, clears content). "
        "Sender can delete their own messages. Chatroom admin can delete any message."
    ),
    responses={
        200: OpenApiResponse(description="Message deleted"),
        403: OpenApiResponse(description="Not allowed"),
        404: OpenApiResponse(description="Message not found"),
    },
    tags=["Chat"],
)
class MessageDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, msg_pk):
        chatroom, err = _get_chatroom_or_404(pk)
        if err:
            return err
        _, err = _get_any_member_or_403(chatroom, request.user)
        if err:
            return err

        try:
            msg = Message.objects.get(pk=msg_pk, chatroom=chatroom, is_deleted=False)
        except Message.DoesNotExist:
            return APIResponse.error(
                message="Message not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        is_sender = msg.sender_id == request.user.id
        is_owner = (
            chatroom.trainer_id and chatroom.trainer.user_id == request.user.id
        ) or (chatroom.gym_id and chatroom.gym.user_id == request.user.id)

        if not (is_sender or is_owner):
            return APIResponse.error(
                message="You can only delete your own messages.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        msg.is_deleted = True
        msg.content = ""
        msg.attachment_url = ""
        msg.save(update_fields=["is_deleted", "content", "attachment_url"])
        return APIResponse.success(message="Message deleted.")


@extend_schema(
    summary="Pin a message",
    description=(
        "Admin pins a message in the chatroom. "
        "Idempotent — pinning already-pinned message returns 200."
    ),
    responses={
        201: OpenApiResponse(description="Message pinned"),
        403: OpenApiResponse(description="Not an admin"),
        404: OpenApiResponse(description="Message not found"),
    },
    tags=["Chat"],
)
class PinMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, msg_pk):
        chatroom, err = _get_chatroom_or_404(pk)
        if err:
            return err
        _, err = _require_admin_or_403(chatroom, request.user)
        if err:
            return err

        try:
            message = Message.objects.get(pk=msg_pk, chatroom=chatroom)
        except Message.DoesNotExist:
            return APIResponse.error(
                message="Message not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        pin, created = PinnedMessage.objects.get_or_create(
            chatroom=chatroom,
            message=message,
            defaults={"pinned_by": request.user},
        )
        serializer = PinnedMessageSerializer(pin, context={"request": request})
        status_code = 201 if created else 200
        return APIResponse.success(
            data=serializer.data,
            status_code=status_code,
            message="Message pinned." if created else "Message already pinned.",
        )


@extend_schema(
    summary="Unpin a message",
    description="Admin unpins a specific message from the chatroom.",
    responses={
        200: OpenApiResponse(description="Message unpinned"),
        403: OpenApiResponse(description="Not an admin"),
        404: OpenApiResponse(description="Pin not found"),
    },
    tags=["Chat"],
)
class UnpinMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, msg_pk):
        chatroom, err = _get_chatroom_or_404(pk)
        if err:
            return err
        _, err = _require_admin_or_403(chatroom, request.user)
        if err:
            return err

        deleted, _ = PinnedMessage.objects.filter(
            chatroom=chatroom, message_id=msg_pk
        ).delete()
        if not deleted:
            return APIResponse.error(
                message="Pin not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        return APIResponse.success(message="Message unpinned.")


@extend_schema(
    summary="List pinned messages",
    description="Returns all pinned messages for a chatroom, ordered newest-first.",
    responses={200: OpenApiResponse(description="Pinned messages")},
    tags=["Chat"],
)
class PinnedMessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        chatroom, err = _get_chatroom_or_404(pk)
        if err:
            return err
        _, err = _get_any_member_or_403(chatroom, request.user)
        if err:
            return err

        pins = chatroom.pinned_messages.select_related(
            "message__sender", "pinned_by"
        ).all()
        serializer = PinnedMessageSerializer(
            pins, many=True, context={"request": request}
        )
        return APIResponse.success(data=serializer.data)


@extend_schema(
    summary="Mark chatroom as read",
    description="Updates last_read_at for the authenticated user in this chatroom.",
    responses={200: OpenApiResponse(description="Marked as read")},
    tags=["Chat"],
)
class MarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        chatroom, err = _get_chatroom_or_404(pk)
        if err:
            return err
        _, err = _get_any_member_or_403(chatroom, request.user)
        if err:
            return err

        ChatroomMember.objects.filter(chatroom=chatroom, user=request.user).update(
            last_read_at=timezone.now()
        )
        return APIResponse.success(message="Marked as read.")


@extend_schema(
    summary="Get unread message count",
    description="Returns the number of unread messages for the authenticated user.",
    responses={200: OpenApiResponse(description="Unread count")},
    tags=["Chat"],
)
class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        chatroom, err = _get_chatroom_or_404(pk)
        if err:
            return err
        member, err = _get_any_member_or_403(chatroom, request.user)
        if err:
            return err

        qs = (
            Message.objects.filter(
                chatroom=chatroom,
                is_deleted=False,
            )
            .exclude(sender=request.user)
            .filter(
                Q(audience=Message.Audience.FULL_GROUP) | Q(target_user=request.user)
            )
        )
        if member.last_read_at:
            qs = qs.filter(sent_at__gt=member.last_read_at)
        return APIResponse.success(data={"unread_count": qs.count()})


@extend_schema(
    summary="Mute / unmute chatroom notifications",
    description=(
        "Mute chatroom for a number of hours. " "hours=0 unmutes immediately."
    ),
    request=inline_serializer(
        "MuteRequest",
        fields={"hours": drf_serializers.IntegerField(min_value=0)},
    ),
    responses={200: OpenApiResponse(description="Mute updated")},
    tags=["Chat"],
)
class MuteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        chatroom, err = _get_chatroom_or_404(pk)
        if err:
            return err
        member, err = _get_any_member_or_403(chatroom, request.user)
        if err:
            return err

        hours = request.data.get("hours", 0)
        try:
            hours = int(hours)
        except (TypeError, ValueError):
            return APIResponse.error(
                message="hours must be an integer.",
                code=ErrorCode.VALIDATION_ERROR,
                status_code=400,
            )

        if hours == 0:
            member.muted_until = None
        else:
            member.muted_until = timezone.now() + timezone.timedelta(hours=hours)
        member.save(update_fields=["muted_until"])
        return APIResponse.success(
            message="Muted." if hours else "Unmuted.",
            data={"muted_until": member.muted_until},
        )


# ──────────────────────────────────────────────────────────────────────────────
# CHAT-04 — Member Management
# ──────────────────────────────────────────────────────────────────────────────


@extend_schema(
    summary="List chatroom members",
    description="Returns active members of a chatroom with their membership status.",
    responses={200: OpenApiResponse(description="Member list")},
    tags=["Chat"],
)
class ChatroomMemberListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        chatroom, err = _get_chatroom_or_404(pk)
        if err:
            return err
        _, err = _get_any_member_or_403(chatroom, request.user)
        if err:
            return err

        members = (
            ChatroomMember.objects.filter(chatroom=chatroom, is_active=True)
            .select_related("user")
            .order_by("joined_at")
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(members, request)
        serializer = ChatroomMemberSerializer(
            page, many=True, context={"request": request}
        )
        return paginator.get_paginated_response(serializer.data)


@extend_schema(
    summary="Remove a member from chatroom",
    description=(
        "Admin removes a member from the chatroom. "
        "Sets is_active=False and soft-deletes the related ClientMembership. "
        "Cannot remove yourself."
    ),
    responses={
        200: OpenApiResponse(description="Member removed"),
        400: OpenApiResponse(description="Cannot remove yourself"),
        403: OpenApiResponse(description="Not an admin"),
        404: OpenApiResponse(description="Member not found"),
    },
    tags=["Chat"],
)
class RemoveMemberView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, user_id):
        chatroom, err = _get_chatroom_or_404(pk)
        if err:
            return err
        _, err = _require_admin_or_403(chatroom, request.user)
        if err:
            return err

        if str(request.user.id) == str(user_id):
            return APIResponse.error(
                message="You cannot remove yourself from the chatroom.",
                code=ErrorCode.VALIDATION_ERROR,
                status_code=400,
            )

        try:
            member = ChatroomMember.objects.get(chatroom=chatroom, user_id=user_id)
        except ChatroomMember.DoesNotExist:
            return APIResponse.error(
                message="Member not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        member.is_active = False
        member.save(update_fields=["is_active"])

        # Soft-delete the related ClientMembership
        from apps.clients.models import ClientMembership

        if chatroom.trainer_id:
            ClientMembership.objects.filter(
                client__user_id=user_id,
                trainer_id=chatroom.trainer_id,
            ).update(deleted_at=timezone.now())
        elif chatroom.gym_id:
            ClientMembership.objects.filter(
                client__user_id=user_id,
                gym_id=chatroom.gym_id,
            ).update(deleted_at=timezone.now())

        # Update member count
        from apps.chat.signals import _update_member_count

        _update_member_count(chatroom)

        return APIResponse.success(message="Member removed.")


# ──────────────────────────────────────────────────────────────────────────────
# CHAT-02 — DM Inbox
# ──────────────────────────────────────────────────────────────────────────────


@extend_schema(
    summary="List DM threads",
    description="Returns all DM threads for the authenticated user, newest first.",
    responses={200: OpenApiResponse(description="DM thread list")},
    tags=["Chat"],
)
class DMThreadListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        threads = (
            DirectMessageThread.objects.filter(
                Q(user_1=request.user) | Q(user_2=request.user)
            )
            .select_related("user_1", "user_2", "last_message__sender")
            .order_by("-updated_at")
        )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(threads, request)
        serializer = DMThreadSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


# ──────────────────────────────────────────────────────────────────────────────
# CHAT-03 — DM Thread
# ──────────────────────────────────────────────────────────────────────────────


def _validate_shared_community(user_a, user_b):
    """Return True if the two users share a ClientMembership."""
    from apps.clients.models import ClientMembership

    return (
        ClientMembership.objects.filter(deleted_at__isnull=True)
        .filter(
            Q(client__user=user_a, trainer__user=user_b)
            | Q(client__user=user_b, trainer__user=user_a)
            | Q(client__user=user_a, gym__user=user_b)
            | Q(client__user=user_b, gym__user=user_a)
        )
        .exists()
    )


@extend_schema(
    summary="Send a direct message",
    description=(
        "Send a DM to another user. Both users must share a community "
        "(ClientMembership). Thread is created automatically on first message."
    ),
    request=inline_serializer(
        "DMSendRequest",
        fields={
            "content": drf_serializers.CharField(required=False),
            "attachment_url": drf_serializers.CharField(required=False),
            "message_type": drf_serializers.CharField(required=False),
        },
    ),
    responses={
        201: OpenApiResponse(description="DM sent"),
        403: OpenApiResponse(description="Not in same community"),
        404: OpenApiResponse(description="User not found"),
    },
    tags=["Chat"],
)
class DMSendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        from apps.accounts.models import User

        try:
            other = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return APIResponse.error(
                message="User not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        if not _validate_shared_community(request.user, other):
            return APIResponse.error(
                message="You can only message users in your community.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        content = request.data.get("content", "").strip()
        attachment_url = request.data.get("attachment_url", "")
        if not content and not attachment_url:
            return APIResponse.error(
                message="Message must have content or attachment_url.",
                code=ErrorCode.VALIDATION_ERROR,
                status_code=400,
            )

        thread = get_or_create_dm_thread(request.user, other)
        message_type = request.data.get("message_type", "text")
        msg = DirectMessage.objects.create(
            thread=thread,
            sender=request.user,
            content=content,
            attachment_url=attachment_url,
            message_type=message_type,
        )

        # Update thread
        if request.user.id == thread.user_1_id:
            thread.user_2_unread += 1
        else:
            thread.user_1_unread += 1
        thread.last_message = msg
        thread.save(update_fields=["last_message", "user_1_unread", "user_2_unread"])

        serializer = DirectMessageSerializer(msg, context={"request": request})
        return APIResponse.created(data=serializer.data)


@extend_schema(
    summary="Get DM message history",
    description=(
        "Returns paginated DM messages with the specified user, oldest first. "
        "Automatically resets the requesting user's unread count to 0."
    ),
    responses={
        200: OpenApiResponse(description="DM messages"),
        404: OpenApiResponse(description="No thread found"),
    },
    tags=["Chat"],
)
class DMMessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        from apps.accounts.models import User

        try:
            other = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return APIResponse.error(
                message="User not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        # Find existing thread without creating one
        from django.db.models import Q as DQ

        u1_id = str(min(str(request.user.id), str(other.id)))
        u2_id = str(max(str(request.user.id), str(other.id)))
        try:
            thread = DirectMessageThread.objects.get(
                user_1_id=u1_id if str(request.user.id) <= str(other.id) else u2_id,
                user_2_id=u2_id if str(request.user.id) <= str(other.id) else u1_id,
            )
        except DirectMessageThread.DoesNotExist:
            # Try both orderings
            try:
                thread = DirectMessageThread.objects.get(
                    DQ(user_1=request.user, user_2=other)
                    | DQ(user_1=other, user_2=request.user)
                )
            except DirectMessageThread.DoesNotExist:
                return APIResponse.error(
                    message="No conversation found.",
                    code=ErrorCode.NOT_FOUND,
                    status_code=404,
                )

        # Reset unread count
        if request.user.id == thread.user_1_id:
            thread.user_1_unread = 0
            thread.save(update_fields=["user_1_unread"])
        else:
            thread.user_2_unread = 0
            thread.save(update_fields=["user_2_unread"])

        qs = thread.messages.select_related("sender").all()
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = DirectMessageSerializer(
            page, many=True, context={"request": request}
        )
        return paginator.get_paginated_response(serializer.data)


@extend_schema(
    summary="Mark DM thread as read",
    description=(
        "Resets the requesting user's unread count to 0 and marks all "
        "unread messages from the other user as read."
    ),
    responses={
        200: OpenApiResponse(description="Marked as read"),
        404: OpenApiResponse(description="Thread not found"),
    },
    tags=["Chat"],
)
class DMMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        from apps.accounts.models import User

        try:
            other = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return APIResponse.error(
                message="User not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        try:
            thread = DirectMessageThread.objects.get(
                Q(user_1=request.user, user_2=other)
                | Q(user_1=other, user_2=request.user)
            )
        except DirectMessageThread.DoesNotExist:
            return APIResponse.error(
                message="Thread not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        if request.user.id == thread.user_1_id:
            thread.user_1_unread = 0
            thread.save(update_fields=["user_1_unread"])
        else:
            thread.user_2_unread = 0
            thread.save(update_fields=["user_2_unread"])

        DirectMessage.objects.filter(
            thread=thread,
            read_at__isnull=True,
        ).exclude(
            sender=request.user
        ).update(read_at=timezone.now())

        return APIResponse.success(message="Thread marked as read.")
