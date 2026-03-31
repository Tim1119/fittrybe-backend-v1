"""
Sessions app serializers.
"""

from rest_framework import serializers

from apps.clients.models import ClientMembership
from apps.profiles.models import ClientProfile
from apps.sessions.models import Session


class ClientMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientProfile
        fields = ["id", "display_name", "username", "profile_photo_url"]
        read_only_fields = fields


class TrainerMiniSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    slug = serializers.SlugField(read_only=True)
    profile_photo_url = serializers.URLField(read_only=True)


class SessionSerializer(serializers.ModelSerializer):
    trainer = TrainerMiniSerializer(read_only=True)
    client = ClientMiniSerializer(read_only=True)

    class Meta:
        model = Session
        fields = [
            "id",
            "trainer",
            "client",
            "session_date",
            "session_time",
            "duration_minutes",
            "session_type",
            "virtual_platform",
            "notes",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SessionCreateSerializer(serializers.Serializer):
    client_id = serializers.IntegerField()
    session_date = serializers.DateField()
    session_time = serializers.TimeField(required=False, allow_null=True)
    duration_minutes = serializers.IntegerField(min_value=1, default=60)
    session_type = serializers.ChoiceField(
        choices=Session.SessionType.choices,
        default=Session.SessionType.PHYSICAL,
    )
    virtual_platform = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=""
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(
        choices=Session.Status.choices,
        default=Session.Status.COMPLETED,
    )

    def validate_client_id(self, value):
        try:
            client = ClientProfile.objects.get(id=value)
        except ClientProfile.DoesNotExist:
            raise serializers.ValidationError("Client not found.")
        self._client = client
        return value

    def validate(self, attrs):
        client = getattr(self, "_client", None)
        if client is None:
            return attrs

        trainer = self.context.get("trainer")
        if trainer is None:
            return attrs

        has_membership = ClientMembership.objects.filter(
            client=client,
            trainer=trainer,
            status=ClientMembership.Status.ACTIVE,
            deleted_at__isnull=True,
        ).exists()

        if not has_membership:
            raise serializers.ValidationError(
                {"client_id": "This client is not in your community."}
            )
        return attrs


class SessionUpdateSerializer(serializers.Serializer):
    session_date = serializers.DateField(required=False)
    session_time = serializers.TimeField(required=False, allow_null=True)
    duration_minutes = serializers.IntegerField(min_value=1, required=False)
    session_type = serializers.ChoiceField(
        choices=Session.SessionType.choices, required=False
    )
    virtual_platform = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Session.Status.choices, required=False)
