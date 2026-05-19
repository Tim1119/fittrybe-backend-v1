"""
Serializers for the profiles app.
"""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.profiles.models import (
    Availability,
    Certification,
    ClientProfile,
    Goal,
    GymProfile,
    GymTrainer,
    Review,
    Service,
    Specialisation,
    TrainerProfile,
)

# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


class SpecialisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialisation
        fields = ("id", "name", "slug", "is_predefined")
        read_only_fields = fields


class CertificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certification
        fields = ("id", "name", "issuing_body", "year_obtained")
        read_only_fields = ("id",)


class AvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Availability
        fields = (
            "id",
            "day_of_week",
            "start_time",
            "end_time",
            "session_type",
            "duration_minutes",
            "virtual_platform",
            "notes",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        start = attrs.get("start_time")
        end = attrs.get("end_time")
        if start and end and start >= end:
            raise serializers.ValidationError(
                {"end_time": "End time must be after start time."}
            )
        return attrs


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ("id", "name", "description", "session_type", "display_order")
        read_only_fields = ("id",)


# ---------------------------------------------------------------------------
# Trainer profile
# ---------------------------------------------------------------------------


class TrainerProfileSerializer(serializers.ModelSerializer):
    specialisations = SpecialisationSerializer(many=True, read_only=True)
    certifications = CertificationSerializer(many=True, read_only=True)
    availability = AvailabilitySerializer(many=True, read_only=True)
    services = ServiceSerializer(many=True, read_only=True)
    profile_completion_percentage = serializers.SerializerMethodField()
    public_url = serializers.SerializerMethodField()
    offers_products = serializers.BooleanField(read_only=True)

    class Meta:
        model = TrainerProfile
        fields = (
            "id",
            "full_name",
            "slug",
            "trainer_type",
            "bio",
            "location",
            "phone_number",
            "years_experience",
            "pricing_range",
            "profile_photo_url",
            "cover_photo_url",
            "is_published",
            "avg_rating",
            "rating_count",
            "offers_products",
            "specialisations",
            "certifications",
            "availability",
            "services",
            "profile_completion_percentage",
            "public_url",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "slug",
            "avg_rating",
            "rating_count",
            "created_at",
            "updated_at",
        )

    @extend_schema_field(serializers.IntegerField())
    def get_profile_completion_percentage(self, obj):
        return obj.profile_completion_percentage

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_public_url(self, obj):
        return obj.get_public_url()


class TrainerProfilePublicSerializer(serializers.ModelSerializer):
    specialisations = SpecialisationSerializer(many=True, read_only=True)
    availability = AvailabilitySerializer(many=True, read_only=True)
    services = ServiceSerializer(many=True, read_only=True)
    profile_completion_percentage = serializers.SerializerMethodField()
    public_url = serializers.SerializerMethodField()

    class Meta:
        model = TrainerProfile
        fields = (
            "id",
            "full_name",
            "slug",
            "trainer_type",
            "bio",
            "location",
            "years_experience",
            "pricing_range",
            "profile_photo_url",
            "cover_photo_url",
            "avg_rating",
            "rating_count",
            "specialisations",
            "availability",
            "services",
            "profile_completion_percentage",
            "public_url",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.IntegerField())
    def get_profile_completion_percentage(self, obj):
        return obj.profile_completion_percentage

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_public_url(self, obj):
        return obj.get_public_url()


# ---------------------------------------------------------------------------
# Gym profile
# ---------------------------------------------------------------------------


class GymProfileSerializer(serializers.ModelSerializer):
    availability = AvailabilitySerializer(many=True, read_only=True)
    services = ServiceSerializer(many=True, read_only=True)
    specialisations = SpecialisationSerializer(many=True, read_only=True)
    profile_completion_percentage = serializers.SerializerMethodField()
    public_url = serializers.SerializerMethodField()
    offers_products = serializers.BooleanField(read_only=True)

    class Meta:
        model = GymProfile
        fields = (
            "id",
            "full_name",
            "slug",
            "about",
            "location",
            "city",
            "contact_phone",
            "business_email",
            "logo_url",
            "cover_photo_url",
            "is_published",
            "avg_rating",
            "rating_count",
            "offers_products",
            "specialisations",
            "availability",
            "services",
            "profile_completion_percentage",
            "public_url",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "slug",
            "avg_rating",
            "rating_count",
            "created_at",
            "updated_at",
        )

    @extend_schema_field(serializers.IntegerField())
    def get_profile_completion_percentage(self, obj):
        return obj.profile_completion_percentage

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_public_url(self, obj):
        return obj.get_public_url()


class GymProfilePublicSerializer(serializers.ModelSerializer):
    availability = AvailabilitySerializer(many=True, read_only=True)
    services = ServiceSerializer(many=True, read_only=True)
    specialisations = SpecialisationSerializer(many=True, read_only=True)
    profile_completion_percentage = serializers.SerializerMethodField()
    public_url = serializers.SerializerMethodField()

    class Meta:
        model = GymProfile
        fields = (
            "id",
            "full_name",
            "slug",
            "about",
            "location",
            "city",
            "logo_url",
            "cover_photo_url",
            "avg_rating",
            "rating_count",
            "specialisations",
            "availability",
            "services",
            "profile_completion_percentage",
            "public_url",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.IntegerField())
    def get_profile_completion_percentage(self, obj):
        return obj.profile_completion_percentage

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_public_url(self, obj):
        return obj.get_public_url()


# ---------------------------------------------------------------------------
# Client profile
# ---------------------------------------------------------------------------


class ClientProfileSerializer(serializers.ModelSerializer):
    profile_completion_percentage = serializers.SerializerMethodField()
    specialisations = SpecialisationSerializer(many=True, read_only=True)
    primary_goals = serializers.SerializerMethodField()

    class Meta:
        model = ClientProfile
        fields = (
            "id",
            "full_name",
            "username",
            "profile_photo_url",
            "profile_completion_percentage",
            "specialisations",
            "primary_goals",
        )
        read_only_fields = ("id", "username")

    @extend_schema_field(serializers.IntegerField())
    def get_profile_completion_percentage(self, obj):
        return obj.profile_completion_percentage

    @extend_schema_field(serializers.ListField())
    def get_primary_goals(self, obj):
        from apps.profiles.serializers import GoalSerializer as _GoalSerializer

        return _GoalSerializer(obj.primary_goals.all(), many=True).data


# ---------------------------------------------------------------------------
# Goal serializer
# ---------------------------------------------------------------------------


class GoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Goal
        fields = ["id", "name", "slug", "is_predefined"]
        read_only_fields = ["id", "slug", "is_predefined"]


# ---------------------------------------------------------------------------
# Photo upload
# ---------------------------------------------------------------------------


class PhotoUploadSerializer(serializers.Serializer):
    photo = serializers.ImageField()


class CoverUploadSerializer(serializers.Serializer):
    cover = serializers.ImageField()


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------


class ReviewClientSerializer(serializers.Serializer):
    full_name = serializers.CharField(read_only=True)
    profile_photo_url = serializers.URLField(read_only=True)


class ReviewSerializer(serializers.ModelSerializer):
    client = ReviewClientSerializer(read_only=True)

    class Meta:
        model = Review
        fields = (
            "id",
            "rating",
            "content",
            "trainer_response",
            "client",
            "created_at",
        )
        read_only_fields = ("id", "trainer_response", "client", "created_at")


class ReviewSubmitSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5, required=True)
    content = serializers.CharField(min_length=1, max_length=500, required=True)


class ReviewResponseSerializer(serializers.Serializer):
    trainer_response = serializers.CharField(min_length=1, required=True)


# ---------------------------------------------------------------------------
# Gym trainer management
# ---------------------------------------------------------------------------


class GymTrainerListItemSerializer(serializers.ModelSerializer):
    trainer_id = serializers.IntegerField(source="trainer.id", read_only=True)
    full_name = serializers.CharField(source="trainer.full_name", read_only=True)
    email = serializers.EmailField(source="trainer.user.email", read_only=True)
    profile_photo_url = serializers.URLField(
        source="trainer.profile_photo_url", read_only=True
    )
    is_published = serializers.BooleanField(
        source="trainer.is_published", read_only=True
    )

    class Meta:
        model = GymTrainer
        fields = (
            "id",
            "trainer_id",
            "full_name",
            "email",
            "role",
            "profile_photo_url",
            "is_published",
            "created_at",
        )
        read_only_fields = fields
