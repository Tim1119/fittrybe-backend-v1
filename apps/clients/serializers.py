"""
Serializers for the clients app.
"""

from django.conf import settings
from rest_framework import serializers

from apps.clients.models import ClientMembership, InviteLink


class ClientProfileMiniSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="user.id", read_only=True)
    display_name = serializers.CharField(read_only=True)
    username = serializers.CharField(read_only=True)
    profile_photo_url = serializers.URLField(read_only=True)


class TrainerMiniSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="user.id", read_only=True)
    full_name = serializers.CharField(read_only=True)
    slug = serializers.SlugField(read_only=True)
    profile_photo_url = serializers.URLField(read_only=True)


class GymMiniSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="user.id", read_only=True)
    gym_name = serializers.CharField(read_only=True)


class ClientMembershipSerializer(serializers.ModelSerializer):
    client = ClientProfileMiniSerializer(read_only=True)
    trainer = TrainerMiniSerializer(read_only=True)
    gym = GymMiniSerializer(read_only=True)

    class Meta:
        model = ClientMembership
        fields = [
            "id",
            "client",
            "trainer",
            "gym",
            "status",
            "renewal_date",
            "payment_amount",
            "payment_currency",
            "payment_notes",
            "last_reminder_at",
            "sessions_count",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "client",
            "trainer",
            "gym",
            "sessions_count",
            "last_reminder_at",
            "created_at",
            "updated_at",
        ]


class InviteLinkSerializer(serializers.ModelSerializer):
    web_url = serializers.SerializerMethodField()
    deep_link = serializers.SerializerMethodField()
    owner_type = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()

    class Meta:
        model = InviteLink
        fields = [
            "id",
            "token",
            "web_url",
            "deep_link",
            "expires_at",
            "max_uses",
            "uses_count",
            "is_active",
            "created_at",
            "owner_type",
            "owner_name",
        ]
        read_only_fields = [
            "id",
            "token",
            "uses_count",
            "created_at",
            "owner_type",
            "owner_name",
        ]

    def get_web_url(self, obj):
        return f"{settings.FRONTEND_URL}/join/{obj.token}"

    def get_deep_link(self, obj):
        mobile_url = getattr(settings, "MOBILE_URL", "fittrybe://")
        return f"{mobile_url}join/{obj.token}"

    def get_owner_type(self, obj):
        return "trainer" if obj.trainer_id else "gym"

    def get_owner_name(self, obj):
        if obj.trainer_id:
            return obj.trainer.full_name
        return obj.gym.gym_name


class InvitePreviewSerializer(serializers.Serializer):
    type = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()
    bio_or_about = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()
    token = serializers.CharField(read_only=True)
    is_valid = serializers.SerializerMethodField()

    def get_type(self, obj):
        return "trainer" if obj.trainer_id else "gym"

    def get_name(self, obj):
        if obj.trainer_id:
            return obj.trainer.full_name
        return obj.gym.gym_name

    def get_photo_url(self, obj):
        if obj.trainer_id:
            return obj.trainer.profile_photo_url
        return obj.gym.logo_url

    def get_bio_or_about(self, obj):
        if obj.trainer_id:
            return obj.trainer.bio
        return obj.gym.about

    def get_location(self, obj):
        if obj.trainer_id:
            return obj.trainer.location
        return obj.gym.location

    def get_avg_rating(self, obj):
        if obj.trainer_id:
            return str(obj.trainer.avg_rating)
        return str(obj.gym.avg_rating)

    def get_is_valid(self, obj):
        valid, _ = obj.is_valid()
        return valid
