"""
Serializers for the profiles app.
"""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.profiles.models import (
    Availability,
    Certification,
    ClientProfile,
    GymProfile,
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
            "wizard_step",
            "wizard_completed",
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
    profile_completion_percentage = serializers.SerializerMethodField()
    public_url = serializers.SerializerMethodField()

    class Meta:
        model = GymProfile
        fields = (
            "id",
            "gym_name",
            "slug",
            "admin_full_name",
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
            "wizard_step",
            "wizard_completed",
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
    profile_completion_percentage = serializers.SerializerMethodField()
    public_url = serializers.SerializerMethodField()

    class Meta:
        model = GymProfile
        fields = (
            "id",
            "gym_name",
            "slug",
            "about",
            "location",
            "city",
            "logo_url",
            "cover_photo_url",
            "avg_rating",
            "rating_count",
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

    class Meta:
        model = ClientProfile
        fields = (
            "id",
            "display_name",
            "username",
            "profile_photo_url",
            "profile_completion_percentage",
        )
        read_only_fields = ("id", "username")

    @extend_schema_field(serializers.IntegerField())
    def get_profile_completion_percentage(self, obj):
        return obj.profile_completion_percentage


# ---------------------------------------------------------------------------
# Wizard serializers
# ---------------------------------------------------------------------------


class WizardStep1TrainerSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainerProfile
        fields = (
            "full_name",
            "bio",
            "location",
            "years_experience",
            "phone_number",
        )


class WizardStep1GymSerializer(serializers.ModelSerializer):
    class Meta:
        model = GymProfile
        fields = (
            "gym_name",
            "admin_full_name",
            "about",
            "location",
            "city",
            "contact_phone",
            "business_email",
        )


class _CertificationInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    issuing_body = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=""
    )
    year_obtained = serializers.IntegerField(required=False, allow_null=True)


class _ServiceInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default=""
    )
    session_type = serializers.ChoiceField(
        choices=Service.SessionType.choices,
        required=False,
        default=Service.SessionType.BOTH,
    )
    display_order = serializers.IntegerField(required=False, default=0, min_value=0)


class WizardStep2Serializer(serializers.Serializer):
    """Trainer step 2: specialisations, certifications, services, pricing."""

    specialisation_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
    )
    certifications = _CertificationInputSerializer(many=True, required=False)
    services = _ServiceInputSerializer(many=True, required=False)
    pricing_range = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=""
    )

    def validate_specialisation_ids(self, value):
        if len(value) > 10:
            raise serializers.ValidationError(
                "You can select at most 10 specialisations."
            )
        return value


class WizardStep2GymSerializer(serializers.Serializer):
    """Gym step 2: services only."""

    services = _ServiceInputSerializer(many=True, required=False)


class WizardStep3TrainerSerializer(serializers.Serializer):
    availability = AvailabilitySerializer(many=True)

    def validate_availability(self, value):
        days = [item["day_of_week"] for item in value]
        if len(days) != len(set(days)):
            raise serializers.ValidationError(
                "Duplicate days of the week are not allowed."
            )
        return value


class WizardStep3GymSerializer(WizardStep3TrainerSerializer):
    """Same structure as trainer, FK set in the view."""


# ---------------------------------------------------------------------------
# Photo upload
# ---------------------------------------------------------------------------


class PhotoUploadSerializer(serializers.Serializer):
    photo = serializers.ImageField()


class CoverUploadSerializer(serializers.Serializer):
    cover = serializers.ImageField()
