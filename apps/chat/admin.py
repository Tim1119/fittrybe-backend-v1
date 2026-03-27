from django.contrib import admin

from apps.chat.models import (
    Chatroom,
    ChatroomMember,
    DirectMessage,
    DirectMessageThread,
    Message,
    PinnedMessage,
)


@admin.register(Chatroom)
class ChatroomAdmin(admin.ModelAdmin):
    list_display = ["name", "trainer", "gym", "is_active", "member_count", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name"]


@admin.register(ChatroomMember)
class ChatroomMemberAdmin(admin.ModelAdmin):
    list_display = ["chatroom", "user", "role", "is_active", "joined_at"]
    list_filter = ["role", "is_active"]
    search_fields = ["user__email", "chatroom__name"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "chatroom", "sender", "message_type", "is_deleted", "sent_at"]
    list_filter = ["message_type", "is_deleted", "audience"]
    search_fields = ["content", "sender__email"]


@admin.register(PinnedMessage)
class PinnedMessageAdmin(admin.ModelAdmin):
    list_display = ["chatroom", "message", "pinned_by", "pinned_at"]


@admin.register(DirectMessageThread)
class DirectMessageThreadAdmin(admin.ModelAdmin):
    list_display = ["user_1", "user_2", "user_1_unread", "user_2_unread", "updated_at"]
    search_fields = ["user_1__email", "user_2__email"]


@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ["id", "thread", "sender", "message_type", "is_deleted", "sent_at"]
    list_filter = ["is_deleted"]
    search_fields = ["content", "sender__email"]
