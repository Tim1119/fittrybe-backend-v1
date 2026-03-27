"""
Chat app models — Chatroom, Message, DirectMessage, DM threads.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import BaseModel


class Chatroom(BaseModel):
    trainer = models.OneToOneField(
        "profiles.TrainerProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chatroom",
    )
    gym = models.OneToOneField(
        "profiles.GymProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chatroom",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    zoom_link = models.CharField(max_length=500, blank=True)
    member_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["trainer"],
                condition=models.Q(trainer__isnull=False),
                name="unique_trainer_chatroom",
            ),
            models.UniqueConstraint(
                fields=["gym"],
                condition=models.Q(gym__isnull=False),
                name="unique_gym_chatroom",
            ),
        ]

    def clean(self):
        if bool(self.trainer_id) == bool(self.gym_id):
            raise ValidationError("Exactly one of trainer or gym must be set.")

    def get_owner_user(self):
        if self.trainer_id:
            return self.trainer.user
        return self.gym.user

    def __str__(self):
        return self.name


class PinnedMessage(BaseModel):
    chatroom = models.ForeignKey(
        Chatroom,
        on_delete=models.CASCADE,
        related_name="pinned_messages",
    )
    message = models.ForeignKey(
        "Message",
        on_delete=models.CASCADE,
        related_name="pins",
    )
    pinned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    pinned_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = ("chatroom", "message")
        ordering = ["-pinned_at"]

    def __str__(self):
        return f"Pinned msg {self.message_id} in {self.chatroom.name}"


class ChatroomMember(BaseModel):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    chatroom = models.ForeignKey(
        Chatroom,
        on_delete=models.CASCADE,
        related_name="members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chatroom_memberships",
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    last_read_at = models.DateTimeField(null=True, blank=True)
    muted_until = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("chatroom", "user")

    def __str__(self):
        return f"{self.user.display_name} in {self.chatroom.name}"


class Message(BaseModel):
    class MessageType(models.TextChoices):
        TEXT = "text", "Text"
        IMAGE = "image", "Image"
        FILE = "file", "File"
        ZOOM_LINK = "zoom_link", "Zoom Link"
        SYSTEM = "system", "System"
        REMINDER = "reminder", "Reminder"
        ANNOUNCEMENT = "announcement", "Announcement"
        MOTIVATION = "motivation", "Motivation"

    class Audience(models.TextChoices):
        FULL_GROUP = "full_group", "Full Group"
        INDIVIDUAL = "individual", "Individual"

    chatroom = models.ForeignKey(
        Chatroom,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    content = models.TextField(blank=True)
    message_type = models.CharField(
        max_length=20,
        choices=MessageType.choices,
        default=MessageType.TEXT,
    )
    attachment_url = models.CharField(max_length=500, blank=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
    )
    audience = models.CharField(
        max_length=20,
        choices=Audience.choices,
        default=Audience.FULL_GROUP,
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="targeted_messages",
    )
    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["sent_at"]

    def get_sender_type(self):
        user = self.sender
        if user.role == "gym":
            return "gym"
        elif user.role == "trainer":
            try:
                t = user.trainer_profile
                if t.trainer_type == "gym_trainer":
                    return "gym_trainer"
            except Exception:
                pass
            return "independent_trainer"
        return "client"

    def __str__(self):
        return f"Message({self.id}) in {self.chatroom.name}"


class DirectMessageThread(BaseModel):
    user_1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dm_threads_as_user1",
    )
    user_2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dm_threads_as_user2",
    )
    last_message = models.ForeignKey(
        "DirectMessage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    user_1_unread = models.PositiveIntegerField(default=0)
    user_2_unread = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("user_1", "user_2")

    def get_other_user(self, user):
        return self.user_2 if self.user_1_id == user.id else self.user_1

    def get_unread_count(self, user):
        if self.user_1_id == user.id:
            return self.user_1_unread
        return self.user_2_unread

    def __str__(self):
        return f"DM: {self.user_1.display_name} ↔ {self.user_2.display_name}"


class DirectMessage(BaseModel):
    thread = models.ForeignKey(
        DirectMessageThread,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_dms",
    )
    content = models.TextField(blank=True)
    message_type = models.CharField(
        max_length=20,
        choices=Message.MessageType.choices,
        default=Message.MessageType.TEXT,
    )
    attachment_url = models.CharField(max_length=500, blank=True)
    is_deleted = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["sent_at"]

    def __str__(self):
        return f"DM({self.id}) from {self.sender.display_name}"


def get_or_create_dm_thread(user_a, user_b):
    """
    Always store the smaller UUID as user_1 to prevent duplicate threads
    between the same two users.
    """
    if str(user_a.id) < str(user_b.id):
        u1, u2 = user_a, user_b
    else:
        u1, u2 = user_b, user_a
    thread, _ = DirectMessageThread.objects.get_or_create(user_1=u1, user_2=u2)
    return thread
