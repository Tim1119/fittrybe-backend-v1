"""
Badges app serializers.
"""

from rest_framework import serializers

from apps.badges.models import Badge, BadgeAssignment
from apps.profiles.models import ClientProfile


class ClientMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientProfile
        fields = ["id", "display_name", "username", "profile_photo_url"]
        read_only_fields = fields


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = [
            "id",
            "name",
            "badge_type",
            "description",
            "icon_url",
            "is_system",
            "milestone_threshold",
        ]
        read_only_fields = ["id"]


class BadgeAssignmentSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)
    client = ClientMiniSerializer(read_only=True)
    trainer = serializers.SerializerMethodField()
    assigned_by_name = serializers.SerializerMethodField()

    class Meta:
        model = BadgeAssignment
        fields = [
            "id",
            "badge",
            "client",
            "trainer",
            "assigned_by_name",
            "note",
            "post_to_chatroom",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_trainer(self, obj):
        if obj.trainer_id is None:
            return None
        return {"id": obj.trainer.id, "full_name": obj.trainer.full_name}

    def get_assigned_by_name(self, obj):
        if obj.assigned_by:
            return obj.assigned_by.display_name or obj.assigned_by.username
        return "System"


class RecognitionSlotSerializer(serializers.Serializer):
    client_id = serializers.IntegerField()
    badge_id = serializers.IntegerField()
    note = serializers.CharField(required=False, allow_blank=True, default="")
