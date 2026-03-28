"""
Notifications models — FCMDevice and Notification.
"""

from django.contrib.auth import get_user_model
from django.db import models

from apps.core.models import BaseModel

User = get_user_model()


class FCMDevice(BaseModel):
    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"
        WEB = "web", "Web"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="fcm_devices")
    token = models.CharField(max_length=500)
    platform = models.CharField(choices=Platform.choices, max_length=10)
    is_active = models.BooleanField(default=True, db_index=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "token")

    def __str__(self):
        return f"{self.user.email} [{self.platform}]"


class Notification(BaseModel):
    class NotificationType(models.TextChoices):
        CHAT_MESSAGE = "chat_message", "Chat Message"
        DIRECT_MESSAGE = "direct_message", "Direct Message"
        CLIENT_JOINED = "client_joined", "Client Joined"
        PAYMENT_REMINDER = "payment_reminder", "Payment Reminder"
        SUBSCRIPTION_LOCKED = "subscription_locked", "Subscription Locked"
        NEW_REVIEW = "new_review", "New Review"
        MARKETPLACE_ENQUIRY = "marketplace_enquiry", "Marketplace Enquiry"
        ENQUIRY_RESPONSE = "enquiry_response", "Enquiry Response"

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_notifications",
    )
    notification_type = models.CharField(
        choices=NotificationType.choices, max_length=30, db_index=True
    )
    title = models.CharField(max_length=200)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.notification_type}] → {self.recipient.email}"
