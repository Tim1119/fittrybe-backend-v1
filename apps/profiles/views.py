"""
Profile views — wizard, my profile, public, search, photo uploads.
"""

import logging
import os
import uuid

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.error_codes import ErrorCode
from apps.core.pagination import StandardPagination
from apps.core.permissions import IsTrainer, IsTrainerOrGym
from apps.core.responses import APIResponse
from apps.profiles.models import (
    Availability,
    Certification,
    ClientProfile,
    GymProfile,
    Service,
    Specialisation,
    TrainerProfile,
)
from apps.profiles.serializers import (
    ClientProfileSerializer,
    CoverUploadSerializer,
    GymProfilePublicSerializer,
    GymProfileSerializer,
    PhotoUploadSerializer,
    SpecialisationSerializer,
    TrainerProfilePublicSerializer,
    TrainerProfileSerializer,
    WizardStep1GymSerializer,
    WizardStep1TrainerSerializer,
    WizardStep2GymSerializer,
    WizardStep2Serializer,
    WizardStep3GymSerializer,
    WizardStep3TrainerSerializer,
)

logger = logging.getLogger(__name__)

_MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}


def _get_trainer_profile(user):
    try:
        return user.trainer_profile
    except TrainerProfile.DoesNotExist:
        return None


def _get_gym_profile(user):
    try:
        return user.gym_profile
    except GymProfile.DoesNotExist:
        return None


def _get_client_profile(user):
    try:
        return user.client_profile
    except ClientProfile.DoesNotExist:
        return None


def _profile_not_found():
    return APIResponse.error(message="Profile not found.", code="PROFILE_NOT_FOUND")


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------


@extend_schema(
    summary="Wizard step 1 — basic info",
    description="""
Update basic profile information. Required for both trainers and gyms.

**Trainer fields:**
- `full_name` (string, required) — display name on profile
- `bio` (string, max 500 chars) — about text
- `location` (string) — city, country
- `years_experience` (integer) — years of experience
- `phone_number` (string, optional) — contact number

**Gym fields:**
- `gym_name` (string, required) — name of the gym
- `admin_full_name` (string, required) — full name of gym admin
- `about` (string, max 500 chars) — about the gym
- `location` (string) — address or area
- `city` (string) — city where gym is located
- `contact_phone` (string, optional) — gym contact number
- `business_email` (email, optional) — business email address

Sets `wizard_step` to at least 1.
Sets `onboarding_status` to `in_progress`.
Returns the full updated profile including `profile_completion_percentage`.

**Photo uploads are handled separately:**
- `POST /api/v1/profiles/photo/` — profile photo (optional)
- `POST /api/v1/profiles/cover/` — cover photo (optional)

These can be called during step 1 or any time after.
Step 1 only handles text fields.
    """,
    request=inline_serializer(
        name="WizardStep1Request",
        fields={
            "full_name": drf_serializers.CharField(
                required=False,
                help_text="TRAINER ONLY — Display name on profile",
            ),
            "bio": drf_serializers.CharField(
                required=False,
                help_text="TRAINER ONLY — About text, max 500 chars",
            ),
            "location": drf_serializers.CharField(
                required=False,
                help_text="TRAINER + GYM — City, country",
            ),
            "years_experience": drf_serializers.IntegerField(
                required=False,
                help_text="TRAINER ONLY — Years of experience",
            ),
            "phone_number": drf_serializers.CharField(
                required=False,
                help_text="TRAINER ONLY — Contact number",
            ),
            "gym_name": drf_serializers.CharField(
                required=False,
                help_text="GYM ONLY — Name of the gym",
            ),
            "admin_full_name": drf_serializers.CharField(
                required=False,
                help_text="GYM ONLY — Full name of gym admin",
            ),
            "about": drf_serializers.CharField(
                required=False,
                help_text="GYM ONLY — About the gym, max 500 chars",
            ),
            "city": drf_serializers.CharField(
                required=False,
                help_text="GYM ONLY — City where gym is located",
            ),
            "contact_phone": drf_serializers.CharField(
                required=False,
                help_text="GYM ONLY — Gym contact number",
            ),
            "business_email": drf_serializers.EmailField(
                required=False,
                help_text="GYM ONLY — Business email address",
            ),
        },
    ),
    responses={
        200: inline_serializer(
            name="WizardStep1Response",
            fields={
                "id": drf_serializers.IntegerField(),
                "full_name": drf_serializers.CharField(
                    help_text="Trainer: full_name | Gym: gym_name"
                ),
                "slug": drf_serializers.CharField(),
                "bio": drf_serializers.CharField(help_text="Trainer: bio | Gym: about"),
                "location": drf_serializers.CharField(),
                "wizard_step": drf_serializers.IntegerField(),
                "profile_completion_percentage": drf_serializers.IntegerField(
                    help_text="0–100 percentage of profile completion"
                ),
                "public_url": drf_serializers.CharField(),
            },
        ),
        400: OpenApiResponse(description="Validation error — missing required field"),
        401: OpenApiResponse(description="Not authenticated"),
        403: OpenApiResponse(description="Clients cannot set up profiles"),
    },
    tags=["Profile Wizard"],
)
class WizardStep1View(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    def put(self, request):
        user = request.user
        if user.role == "trainer":
            profile = _get_trainer_profile(user)
            if not profile:
                return _profile_not_found()
            serializer = WizardStep1TrainerSerializer(
                profile, data=request.data, partial=False
            )
        else:
            profile = _get_gym_profile(user)
            if not profile:
                return _profile_not_found()
            serializer = WizardStep1GymSerializer(
                profile, data=request.data, partial=False
            )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            serializer.save()
            profile.wizard_step = max(profile.wizard_step, 1)
            profile.save(update_fields=["wizard_step"])
            if user.onboarding_status != user.OnboardingStatus.COMPLETED:
                user.onboarding_status = user.OnboardingStatus.IN_PROGRESS
                user.save(update_fields=["onboarding_status"])

        out = (
            TrainerProfileSerializer(profile)
            if user.role == "trainer"
            else GymProfileSerializer(profile)
        )
        return APIResponse.success(data=out.data, message="Step 1 saved.")


@extend_schema(
    summary="Wizard step 2 — services and expertise",
    description="""
Update services and expertise. Replaces ALL existing data on every call.

**Trainer fields:**
- `specialisation_ids` (list of integers, max 10)
  — IDs from `GET /api/v1/profiles/specialisations/`
- `certifications` (list of objects, optional)
  — Each: `{name, issuing_body, year_obtained}`
- `services` (list of objects)
  — Each: `{name, description, session_type, display_order}`
  — `session_type`: `physical` | `virtual` | `both`
- `pricing_range` (string, optional)
  — e.g. `"From ₦15,000/session"`

**Gym fields:**
- `services` (list of objects only)
  — Gyms do not have specialisations or certifications

Sets `wizard_step` to at least 2.
    """,
    request=inline_serializer(
        name="WizardStep2Request",
        fields={
            "specialisation_ids": drf_serializers.ListField(
                child=drf_serializers.IntegerField(),
                required=False,
                help_text=(
                    "TRAINER ONLY — List of specialisation IDs (max 10). "
                    "Get IDs from GET /api/v1/profiles/specialisations/"
                ),
            ),
            "pricing_range": drf_serializers.CharField(
                required=False,
                help_text='TRAINER ONLY — e.g. "From ₦15,000/session"',
            ),
            "certifications": drf_serializers.ListField(
                required=False,
                help_text=(
                    "TRAINER ONLY — List of " "{name, issuing_body, year_obtained}"
                ),
            ),
            "services": drf_serializers.ListField(
                required=False,
                help_text=(
                    "TRAINER + GYM — List of "
                    "{name, description, session_type, display_order}. "
                    "session_type: physical | virtual | both"
                ),
            ),
        },
    ),
    responses={
        200: inline_serializer(
            name="WizardStep2Response",
            fields={
                "wizard_step": drf_serializers.IntegerField(),
                "profile_completion_percentage": drf_serializers.IntegerField(),
                "specialisations": drf_serializers.ListField(
                    help_text="Trainer only — saved specialisations"
                ),
                "certifications": drf_serializers.ListField(
                    help_text="Trainer only — saved certifications"
                ),
                "services": drf_serializers.ListField(
                    help_text="Trainer + Gym — saved services"
                ),
                "pricing_range": drf_serializers.CharField(help_text="Trainer only"),
            },
        ),
        400: OpenApiResponse(
            description="Validation error — e.g. more than 10 specialisations"
        ),
        401: OpenApiResponse(description="Not authenticated"),
        403: OpenApiResponse(description="Clients cannot access wizard"),
    },
    tags=["Profile Wizard"],
)
class WizardStep2View(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    def put(self, request):
        user = request.user
        is_trainer = user.role == "trainer"

        if is_trainer:
            profile = _get_trainer_profile(user)
            if not profile:
                return _profile_not_found()
            serializer = WizardStep2Serializer(data=request.data)
        else:
            profile = _get_gym_profile(user)
            if not profile:
                return _profile_not_found()
            serializer = WizardStep2GymSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        services_data = data.get("services", [])

        with transaction.atomic():
            if is_trainer:
                spec_ids = data.get("specialisation_ids", [])
                certs_data = data.get("certifications", [])
                pricing_range = data.get("pricing_range", "")

                if spec_ids:
                    specs = Specialisation.objects.filter(id__in=spec_ids)
                    profile.specialisations.set(specs)
                else:
                    profile.specialisations.clear()

                profile.certifications.all().delete()
                for cert in certs_data:
                    Certification.objects.create(
                        trainer=profile,
                        name=cert["name"],
                        issuing_body=cert.get("issuing_body", ""),
                        year_obtained=cert.get("year_obtained"),
                    )

                profile.pricing_range = pricing_range
                profile.save(update_fields=["pricing_range"])

            # Replace services for both roles
            profile.services.all().delete()
            for svc in services_data:
                kwargs = dict(
                    name=svc["name"],
                    description=svc.get("description", ""),
                    session_type=svc.get("session_type", Service.SessionType.BOTH),
                    display_order=svc.get("display_order", 0),
                )
                if is_trainer:
                    Service.objects.create(trainer=profile, **kwargs)
                else:
                    Service.objects.create(gym=profile, **kwargs)

            profile.wizard_step = max(profile.wizard_step, 2)
            profile.save(update_fields=["wizard_step"])

        out = (
            TrainerProfileSerializer(profile)
            if is_trainer
            else GymProfileSerializer(profile)
        )
        return APIResponse.success(data=out.data, message="Step 2 saved.")


@extend_schema(
    summary="Wizard step 3 — availability",
    description="""
Set weekly availability schedule. Works for both trainers and gyms.

**Trainers** — set working hours and session types.
**Gyms** — set opening hours and class schedules.

Each availability object:
- `day_of_week`: `monday` | `tuesday` | `wednesday` | `thursday`
  | `friday` | `saturday` | `sunday`
- `start_time`: HH:MM 24-hour format, e.g. `"08:00"`
- `end_time`: HH:MM 24-hour format, e.g. `"17:00"`
- `session_type`: `physical` | `virtual` | `both` (default `both`)
- `duration_minutes`: integer (default 60)
- `virtual_platform`: string (e.g. `"Zoom"`, relevant when virtual)
- `notes`: string (optional, e.g. `"Morning HIIT class"`)

Replaces ALL existing availability on every call.
Each day of the week can only appear once per submission.
`start_time` must be before `end_time`.
Sets `wizard_step` to at least 3.
    """,
    request=inline_serializer(
        name="WizardStep3Request",
        fields={
            "availability": drf_serializers.ListField(
                help_text=(
                    "List of availability objects. "
                    'Example: [{"day_of_week": "monday", '
                    '"start_time": "08:00", "end_time": "17:00", '
                    '"session_type": "both", "duration_minutes": 60, '
                    '"virtual_platform": "", "notes": ""}]'
                ),
            ),
        },
    ),
    responses={
        200: inline_serializer(
            name="WizardStep3Response",
            fields={
                "wizard_step": drf_serializers.IntegerField(),
                "profile_completion_percentage": drf_serializers.IntegerField(),
                "availability": drf_serializers.ListField(
                    help_text="Full list of saved availability slots"
                ),
            },
        ),
        400: OpenApiResponse(
            description="Validation error — duplicate days or start_time >= end_time"
        ),
        401: OpenApiResponse(description="Not authenticated"),
        403: OpenApiResponse(description="Clients cannot access wizard"),
    },
    tags=["Profile Wizard"],
)
class WizardStep3View(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    def put(self, request):
        user = request.user
        is_trainer = user.role == "trainer"

        if is_trainer:
            profile = _get_trainer_profile(user)
            serializer_class = WizardStep3TrainerSerializer
        else:
            profile = _get_gym_profile(user)
            serializer_class = WizardStep3GymSerializer

        if not profile:
            return _profile_not_found()

        serializer = serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        availability_data = serializer.validated_data["availability"]

        with transaction.atomic():
            profile.availability.all().delete()
            for av in availability_data:
                kwargs = dict(
                    day_of_week=av["day_of_week"],
                    start_time=av["start_time"],
                    end_time=av["end_time"],
                    session_type=av.get("session_type", Availability.SessionType.BOTH),
                    duration_minutes=av.get("duration_minutes", 60),
                    virtual_platform=av.get("virtual_platform", ""),
                    notes=av.get("notes", ""),
                )
                if is_trainer:
                    Availability.objects.create(trainer=profile, **kwargs)
                else:
                    Availability.objects.create(gym=profile, **kwargs)

            profile.wizard_step = max(profile.wizard_step, 3)
            profile.save(update_fields=["wizard_step"])

        out = (
            TrainerProfileSerializer(profile)
            if is_trainer
            else GymProfileSerializer(profile)
        )
        return APIResponse.success(data=out.data, message="Step 3 saved.")


class WizardStep4View(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    @extend_schema(
        summary="Wizard step 4 — publish profile",
        description="""
Publish the profile and make it publicly discoverable.

**Requirements before publishing:**
- Profile completion must be >= 60%
- Subscription must be active or in trial (not locked/cancelled)

**What happens on publish:**
- `is_published` = `true`
- `wizard_completed` = `true`
- `onboarding_status` = `completed`
- Profile appears in search results
- Public URL becomes accessible

No request body needed — just POST to this endpoint.
        """,
        request=None,
        responses={
            200: inline_serializer(
                name="WizardStep4Response",
                fields={
                    "public_url": drf_serializers.URLField(
                        help_text="Publicly accessible URL of the published profile"
                    ),
                    "profile_completion_percentage": drf_serializers.IntegerField(),
                    "wizard_completed": drf_serializers.BooleanField(),
                    "is_published": drf_serializers.BooleanField(),
                },
            ),
            400: OpenApiResponse(
                description=(
                    "Profile completion below 60% — "
                    "response includes missing_fields list, "
                    "current percentage, and minimum_required"
                )
            ),
            401: OpenApiResponse(description="Not authenticated"),
            403: OpenApiResponse(
                description="Subscription locked or cancelled — renew to publish"
            ),
        },
        tags=["Profile Wizard"],
    )
    def post(self, request):
        user = request.user
        is_trainer = user.role == "trainer"
        profile = _get_trainer_profile(user) if is_trainer else _get_gym_profile(user)
        if not profile:
            return _profile_not_found()

        if profile.profile_completion_percentage < 60:
            return APIResponse.error(
                message=(
                    "Your profile is not complete enough to publish. "
                    "Please fill in more details."
                ),
                code=ErrorCode.VALIDATION_ERROR,
                errors={
                    "missing_fields": profile.get_missing_fields(),
                    "profile_completion_percentage": (
                        profile.profile_completion_percentage
                    ),
                    "minimum_required": 60,
                },
                status_code=400,
            )

        try:
            if not user.subscription.is_access_allowed():
                return Response(
                    {"error": "Subscription is locked or cancelled."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        except Exception:
            pass

        with transaction.atomic():
            profile.is_published = True
            profile.wizard_completed = True
            profile.wizard_step = 4
            profile.save(
                update_fields=["is_published", "wizard_completed", "wizard_step"]
            )
            user.complete_onboarding()

        return APIResponse.success(
            data={
                "public_url": profile.get_public_url(),
                "profile_completion_percentage": profile.profile_completion_percentage,
            },
            message="Profile published.",
        )


@extend_schema(
    summary="Get wizard status",
    description="""
Returns the current wizard progress and what fields are still missing.
Use this to determine which step to show the user next and what to complete.

**`wizard_step` values:**
- `0` — not started
- `1` — basic info saved
- `2` — expertise / services saved
- `3` — availability saved
- `4` — published

**`missing_fields`** — list of field names still empty.
Use this to guide the user toward 100% completion.

**`profile_completion_percentage`** — must reach 60% before publishing.
    """,
    request=None,
    responses={
        200: inline_serializer(
            name="WizardStatusResponse",
            fields={
                "wizard_step": drf_serializers.IntegerField(
                    help_text="Current step 0–4"
                ),
                "wizard_completed": drf_serializers.BooleanField(),
                "is_published": drf_serializers.BooleanField(),
                "profile_completion_percentage": drf_serializers.IntegerField(
                    help_text="0–100"
                ),
                "missing_fields": drf_serializers.ListField(
                    child=drf_serializers.CharField(),
                    help_text="Names of incomplete fields",
                ),
            },
        ),
        401: OpenApiResponse(description="Not authenticated"),
        403: OpenApiResponse(description="Clients do not have a wizard"),
    },
    tags=["Profile Wizard"],
)
class WizardStatusView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    def get(self, request):
        user = request.user
        is_trainer = user.role == "trainer"
        profile = _get_trainer_profile(user) if is_trainer else _get_gym_profile(user)
        if not profile:
            return _profile_not_found()

        return APIResponse.success(
            data={
                "wizard_step": profile.wizard_step,
                "wizard_completed": profile.wizard_completed,
                "is_published": profile.is_published,
                "profile_completion_percentage": profile.profile_completion_percentage,
                "missing_fields": profile.get_missing_fields(),
            },
            message="Wizard status retrieved.",
        )


# ---------------------------------------------------------------------------
# My profile
# ---------------------------------------------------------------------------


class MyProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def _resolve(self, user):
        if user.role == "trainer":
            return _get_trainer_profile(user), TrainerProfileSerializer
        elif user.role == "gym":
            return _get_gym_profile(user), GymProfileSerializer
        return _get_client_profile(user), ClientProfileSerializer

    @extend_schema(
        summary="Get my profile",
        description="""
Returns the full profile for the currently authenticated user.

**Trainer** — returns `TrainerProfileSerializer` fields:
`full_name`, `bio`, `location`, `phone_number`, `years_experience`,
`pricing_range`, `specialisations`, `certifications`, `availability`,
`services`, `profile_photo_url`, `cover_photo_url`, `is_published`,
`avg_rating`, `wizard_step`, `wizard_completed`, `profile_completion_percentage`.

**Gym** — returns `GymProfileSerializer` fields:
`gym_name`, `admin_full_name`, `about`, `location`, `city`,
`contact_phone`, `business_email`, `logo_url`, `cover_photo_url`,
`availability`, `services`, `is_published`, `avg_rating`,
`wizard_step`, `wizard_completed`, `profile_completion_percentage`.

**Client** — returns `ClientProfileSerializer` fields:
`display_name`, `username`, `profile_photo_url`,
`profile_completion_percentage`.
        """,
        responses={
            200: OpenApiResponse(
                response=TrainerProfileSerializer,
                description=(
                    "Full profile object — shape varies by role "
                    "(trainer / gym / client)"
                ),
            ),
            401: OpenApiResponse(description="Not authenticated"),
            404: OpenApiResponse(description="Profile not found"),
        },
        tags=["Profiles"],
    )
    def get(self, request):
        profile, serializer_class = self._resolve(request.user)
        if not profile:
            return _profile_not_found()
        return APIResponse.success(
            data=serializer_class(profile).data,
            message="Profile retrieved.",
        )

    @extend_schema(
        summary="Update my profile",
        description="""
Partially update the current user's profile. All fields are optional.

**Trainer** — writable fields: `full_name`, `bio`, `location`,
`phone_number`, `years_experience`, `pricing_range`,
`profile_photo_url`, `cover_photo_url`, `trainer_type`.

**Gym** — writable fields: `gym_name`, `admin_full_name`, `about`,
`location`, `city`, `contact_phone`, `business_email`,
`logo_url`, `cover_photo_url`.

**Client** — writable fields: `display_name`, `profile_photo_url`.

Nested relations (`specialisations`, `certifications`,
`availability`, `services`) are managed via the wizard endpoints.
        """,
        request=inline_serializer(
            name="MyProfileUpdateRequest",
            fields={
                "full_name": drf_serializers.CharField(
                    required=False,
                    help_text="TRAINER — display name on profile",
                ),
                "bio": drf_serializers.CharField(
                    required=False,
                    help_text="TRAINER — about text, max 500 chars",
                ),
                "location": drf_serializers.CharField(
                    required=False,
                    help_text="TRAINER + GYM — city, country",
                ),
                "phone_number": drf_serializers.CharField(
                    required=False,
                    help_text="TRAINER — contact number",
                ),
                "years_experience": drf_serializers.IntegerField(
                    required=False,
                    help_text="TRAINER — years of experience",
                ),
                "pricing_range": drf_serializers.CharField(
                    required=False,
                    help_text='TRAINER — e.g. "From ₦15,000/session"',
                ),
                "gym_name": drf_serializers.CharField(
                    required=False,
                    help_text="GYM — name of the gym",
                ),
                "admin_full_name": drf_serializers.CharField(
                    required=False,
                    help_text="GYM — full name of gym admin",
                ),
                "about": drf_serializers.CharField(
                    required=False,
                    help_text="GYM — about the gym, max 500 chars",
                ),
                "city": drf_serializers.CharField(
                    required=False,
                    help_text="GYM — city where gym is located",
                ),
                "contact_phone": drf_serializers.CharField(
                    required=False,
                    help_text="GYM — gym contact number",
                ),
                "business_email": drf_serializers.EmailField(
                    required=False,
                    help_text="GYM — business email address",
                ),
                "display_name": drf_serializers.CharField(
                    required=False,
                    help_text="CLIENT — public display name",
                ),
            },
        ),
        responses={
            200: OpenApiResponse(
                response=TrainerProfileSerializer,
                description=(
                    "Updated profile — shape varies by role " "(trainer / gym / client)"
                ),
            ),
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Not authenticated"),
            404: OpenApiResponse(description="Profile not found"),
        },
        tags=["Profiles"],
    )
    def put(self, request):
        profile, serializer_class = self._resolve(request.user)
        if not profile:
            return _profile_not_found()
        serializer = serializer_class(profile, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            serializer.save()
        return APIResponse.success(data=serializer.data, message="Profile updated.")


# ---------------------------------------------------------------------------
# Public profiles
# ---------------------------------------------------------------------------


@extend_schema(
    summary="Public trainer profile",
    description="""
Returns a published trainer profile by slug. No authentication required.

Returns 404 if the profile does not exist or has not been published yet.

**Excluded from public view:** `phone_number` (contact via platform only).

**Included:** `full_name`, `slug`, `trainer_type`, `bio`, `location`,
`years_experience`, `pricing_range`, `profile_photo_url`, `cover_photo_url`,
`avg_rating`, `rating_count`, `specialisations`, `availability`, `services`,
`profile_completion_percentage`, `public_url`.
    """,
    responses={
        200: OpenApiResponse(
            response=TrainerProfilePublicSerializer,
            description="Published trainer profile",
        ),
        404: OpenApiResponse(description="Not found or not yet published"),
    },
    tags=["Public Profiles"],
    auth=[],
)
class PublicTrainerProfileView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        try:
            profile = TrainerProfile.objects.get(slug=slug, is_published=True)
        except TrainerProfile.DoesNotExist:
            return Response(
                {"error": "Trainer profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return APIResponse.success(
            data=TrainerProfilePublicSerializer(profile).data,
            message="Trainer profile retrieved.",
        )


@extend_schema(
    summary="Public gym profile",
    description="""
Returns a published gym profile by slug. No authentication required.

Returns 404 if the profile does not exist or has not been published yet.

**Excluded from public view:** `contact_phone`, `business_email`
(contact via platform only).

**Included:** `gym_name`, `slug`, `about`, `location`, `city`,
`logo_url`, `cover_photo_url`, `avg_rating`, `rating_count`,
`availability`, `services`, `profile_completion_percentage`, `public_url`.
    """,
    responses={
        200: OpenApiResponse(
            response=GymProfilePublicSerializer,
            description="Published gym profile",
        ),
        404: OpenApiResponse(description="Not found or not yet published"),
    },
    tags=["Public Profiles"],
    auth=[],
)
class PublicGymProfileView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        try:
            profile = GymProfile.objects.get(slug=slug, is_published=True)
        except GymProfile.DoesNotExist:
            return Response(
                {"error": "Gym profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return APIResponse.success(
            data=GymProfilePublicSerializer(profile).data,
            message="Gym profile retrieved.",
        )


@extend_schema(
    summary="Search profiles",
    description="""
Search published trainer and gym profiles. No authentication required.

Results are paginated. Default page size is 20.

**Query parameters:**
- `q` — full-text search on name and bio/about
- `type` — `trainer` (default) or `gym`
- `location` — filter by location string (case-insensitive contains)
- `specialisation` — trainer specialisation slug
  (e.g. `yoga`, `hiit` — get slugs from `/api/v1/profiles/specialisations/`)
- `session_type` — filter by availability session type:
  `physical` | `virtual` | `both`

**Response shape** varies by `type`:
- `trainer` → `TrainerProfilePublicSerializer` (includes specialisations, services)
- `gym` → `GymProfilePublicSerializer` (includes availability, services)
    """,
    parameters=[
        OpenApiParameter(
            "q",
            str,
            description="Search term — matches name and bio/about text",
            required=False,
        ),
        OpenApiParameter(
            "type",
            str,
            description="Profile type: trainer (default) or gym",
            required=False,
            enum=["trainer", "gym"],
        ),
        OpenApiParameter(
            "location",
            str,
            description="Filter by location (case-insensitive contains)",
            required=False,
        ),
        OpenApiParameter(
            "specialisation",
            str,
            description=(
                "Trainer specialisation slug — "
                "get slugs from GET /api/v1/profiles/specialisations/"
            ),
            required=False,
        ),
        OpenApiParameter(
            "session_type",
            str,
            description="Filter by availability session type",
            required=False,
            enum=["physical", "virtual", "both"],
        ),
    ],
    responses={
        200: OpenApiResponse(
            description=(
                "Paginated list of profiles. "
                "Shape varies by type param (trainer or gym)."
            )
        )
    },
    tags=["Public Profiles"],
    auth=[],
)
class ProfileSearchView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        q = request.query_params.get("q", "")
        profile_type = request.query_params.get("type", "trainer")
        location = request.query_params.get("location", "")
        specialisation = request.query_params.get("specialisation", "")
        session_type = request.query_params.get("session_type", "")

        paginator = StandardPagination()

        if profile_type == "gym":
            qs = GymProfile.objects.filter(is_published=True).select_related("user")
            if q:
                qs = qs.filter(Q(gym_name__icontains=q) | Q(about__icontains=q))
            if location:
                qs = qs.filter(location__icontains=location)
            if session_type:
                qs = qs.filter(availability__session_type=session_type).distinct()
            page = paginator.paginate_queryset(qs, request)
            serializer = GymProfilePublicSerializer(page, many=True)
        else:
            qs = (
                TrainerProfile.objects.filter(is_published=True)
                .select_related("user")
                .prefetch_related("specialisations", "availability")
            )
            if q:
                qs = qs.filter(Q(full_name__icontains=q) | Q(bio__icontains=q))
            if location:
                qs = qs.filter(location__icontains=location)
            if specialisation:
                qs = qs.filter(specialisations__slug=specialisation).distinct()
            if session_type:
                qs = qs.filter(availability__session_type=session_type).distinct()
            page = paginator.paginate_queryset(qs, request)
            serializer = TrainerProfilePublicSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


# ---------------------------------------------------------------------------
# Photo uploads
# ---------------------------------------------------------------------------


def _save_uploaded_file(uploaded_file, subfolder):
    """Save uploaded file and return its URL."""
    from pathlib import Path

    upload_dir = Path(settings.MEDIA_ROOT) / subfolder
    upload_dir.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(uploaded_file.name)[1].lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = upload_dir / filename
    with open(dest, "wb") as fh:
        for chunk in uploaded_file.chunks():
            fh.write(chunk)
    return f"{settings.MEDIA_URL}{subfolder}/{filename}"


def _validate_upload(uploaded):
    if not uploaded:
        return Response(
            {"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST
        )
    if uploaded.content_type not in _ALLOWED_IMAGE_TYPES:
        return Response(
            {"error": "Only JPG and PNG images are accepted."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if uploaded.size > _MAX_PHOTO_BYTES:
        return Response(
            {"error": "File must be under 5 MB."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return None


@extend_schema(
    summary="Upload profile photo",
    description="""
Upload a profile photo for the authenticated user. JPG or PNG only, max 5 MB.

**Role-specific behaviour:**
- **Trainer** — saves to `profile_photo_url`
- **Gym** — saves to `logo_url`
- **Client** — saves to `profile_photo_url`

Returns the saved file URL. Send as `multipart/form-data` with key `photo`.
    """,
    request=PhotoUploadSerializer,
    responses={
        200: inline_serializer(
            name="PhotoUploadResponse",
            fields={
                "url": drf_serializers.CharField(
                    help_text="Relative URL of the saved photo, "
                    "e.g. /media/profiles/photos/abc.jpg"
                ),
            },
        ),
        400: OpenApiResponse(
            description="No file provided, wrong content type, or file exceeds 5 MB"
        ),
        401: OpenApiResponse(description="Not authenticated"),
    },
    tags=["Profiles"],
)
class ProfilePhotoUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        uploaded = request.FILES.get("photo")
        err = _validate_upload(uploaded)
        if err:
            return err

        url = _save_uploaded_file(uploaded, "profiles/photos")
        user = request.user

        if user.role == "trainer":
            profile = _get_trainer_profile(user)
            if profile:
                profile.profile_photo_url = url
                profile.save(update_fields=["profile_photo_url"])
        elif user.role == "gym":
            profile = _get_gym_profile(user)
            if profile:
                profile.logo_url = url
                profile.save(update_fields=["logo_url"])
        elif user.role == "client":
            profile = _get_client_profile(user)
            if profile:
                profile.profile_photo_url = url
                profile.save(update_fields=["profile_photo_url"])

        return APIResponse.success(data={"url": url}, message="Photo uploaded.")


@extend_schema(
    summary="Upload cover photo",
    description="""
Upload a cover/banner photo for the authenticated user. JPG or PNG only, max 5 MB.

**Role-specific behaviour:**
- **Trainer** — saves to `cover_photo_url`
- **Gym** — saves to `cover_photo_url`
- **Client** — not applicable (ignored silently)

Returns the saved file URL. Send as `multipart/form-data` with key `cover`.
    """,
    request=CoverUploadSerializer,
    responses={
        200: inline_serializer(
            name="CoverUploadResponse",
            fields={
                "url": drf_serializers.CharField(
                    help_text="Relative URL of the saved cover, "
                    "e.g. /media/profiles/covers/abc.jpg"
                ),
            },
        ),
        400: OpenApiResponse(
            description="No file provided, wrong content type, or file exceeds 5 MB"
        ),
        401: OpenApiResponse(description="Not authenticated"),
    },
    tags=["Profiles"],
)
class CoverPhotoUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        uploaded = request.FILES.get("cover")
        err = _validate_upload(uploaded)
        if err:
            return err

        url = _save_uploaded_file(uploaded, "profiles/covers")
        user = request.user

        if user.role == "trainer":
            profile = _get_trainer_profile(user)
            if profile:
                profile.cover_photo_url = url
                profile.save(update_fields=["cover_photo_url"])
        elif user.role == "gym":
            profile = _get_gym_profile(user)
            if profile:
                profile.cover_photo_url = url
                profile.save(update_fields=["cover_photo_url"])

        return APIResponse.success(data={"url": url}, message="Cover uploaded.")


# ---------------------------------------------------------------------------
# Specialisations
# ---------------------------------------------------------------------------


@extend_schema(
    summary="List specialisations",
    description="""
Returns all available specialisations that can be assigned to trainer profiles.

Use the returned `id` values in `specialisation_ids` when calling
`PUT /api/v1/profiles/wizard/step2/`.

Use the returned `slug` values as the `specialisation` query parameter
when calling `GET /api/v1/profiles/search/`.

No authentication required.
    """,
    responses={
        200: OpenApiResponse(
            response=SpecialisationSerializer(many=True),
            description="List of all specialisations",
        )
    },
    tags=["Profiles"],
    auth=[],
)
class SpecialisationListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        specs = Specialisation.objects.all()
        return APIResponse.success(
            data=SpecialisationSerializer(specs, many=True).data,
            message="Specialisations retrieved.",
        )
