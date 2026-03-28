"""
Notifications serializers.
"""

from rest_framework import serializers

from .models import FCMDevice, Notification


class FCMDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCMDevice
        fields = ["id", "token", "platform", "is_active", "created_at"]
        read_only_fields = ["id", "is_active", "created_at"]

    def validate_platform(self, value):
        if value not in FCMDevice.Platform.values:
            raise serializers.ValidationError(
                f"Invalid platform. Choose from: {', '.join(FCMDevice.Platform.values)}"
            )
        return value


class NotificationSenderSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    display_name = serializers.CharField()
    photo_url = serializers.SerializerMethodField()

    def get_photo_url(self, obj):
        try:
            if obj.role == "trainer":
                return obj.trainer_profile.profile_photo_url or ""
            elif obj.role == "gym":
                return obj.gym_profile.logo_url or ""
            elif obj.role == "client":
                return obj.client_profile.profile_photo_url or ""
        except Exception:
            pass
        return ""


class NotificationSerializer(serializers.ModelSerializer):
    sender = NotificationSenderSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "notification_type",
            "title",
            "body",
            "data",
            "is_read",
            "read_at",
            "created_at",
            "sender",
        ]
        read_only_fields = fields
