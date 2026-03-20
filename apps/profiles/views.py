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
    description=(
        "Update basic profile information. "
        "Trainers: full_name, bio, location, years_experience, phone_number. "
        "Gyms: gym_name, admin_full_name, about, location, city, "
        "contact_phone, business_email. "
        "Sets wizard_step to at least 1 and marks onboarding as in_progress."
    ),
    request=WizardStep1TrainerSerializer,
    responses={
        200: OpenApiResponse(description="Step 1 saved — profile and completion %"),
        400: OpenApiResponse(description="Validation error"),
        403: OpenApiResponse(description="Not a trainer or gym"),
        404: OpenApiResponse(description="Profile not found"),
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
    summary="Wizard step 2 — specialisations, certifications & services",
    description=(
        "Trainer: update specialisations (max 10), certifications, services, "
        "and pricing range. Replaces all existing data. "
        "Gym: update services only. "
        "Works for both trainers and gyms."
    ),
    request=WizardStep2Serializer,
    responses={
        200: OpenApiResponse(description="Step 2 saved"),
        400: OpenApiResponse(description="Validation error or >10 specialisations"),
        403: OpenApiResponse(description="Not a trainer or gym"),
        404: OpenApiResponse(description="Profile not found"),
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
    description=(
        "Replace all availability slots. "
        "Duplicate days within the same submission are rejected. "
        "Works for both trainers and gyms."
    ),
    request=WizardStep3TrainerSerializer,
    responses={
        200: OpenApiResponse(description="Step 3 saved"),
        400: OpenApiResponse(description="Validation error or duplicate days"),
        403: OpenApiResponse(description="Not a trainer or gym"),
        404: OpenApiResponse(description="Profile not found"),
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
        description=(
            "Publish the profile, mark wizard as completed, and complete onboarding. "
            "Requires an active or trial subscription (not locked/cancelled)."
        ),
        request=None,
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    "WizardStep4Response",
                    fields={
                        "public_url": drf_serializers.CharField(),
                        "profile_completion_percentage": drf_serializers.IntegerField(),
                    },
                ),
                description="Profile published",
            ),
            403: OpenApiResponse(
                description="Not a trainer or gym, or subscription locked"
            ),
            404: OpenApiResponse(description="Profile not found"),
        },
        tags=["Profile Wizard"],
    )
    def post(self, request):
        user = request.user
        is_trainer = user.role == "trainer"
        profile = _get_trainer_profile(user) if is_trainer else _get_gym_profile(user)
        if not profile:
            return _profile_not_found()

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
    summary="Wizard status",
    description="Return current wizard progress and profile completion percentage.",
    responses={
        200: OpenApiResponse(description="Wizard status"),
        403: OpenApiResponse(description="Not a trainer or gym"),
        404: OpenApiResponse(description="Profile not found"),
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
        summary="My profile — GET",
        description="Return the current user's profile (trainer, gym, or client).",
        responses={
            200: OpenApiResponse(
                response=TrainerProfileSerializer,
                description="Profile data (varies by role)",
            ),
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
        summary="My profile — PUT",
        description="Partially update the current user's profile.",
        request=TrainerProfileSerializer,
        responses={
            200: OpenApiResponse(
                response=TrainerProfileSerializer,
                description="Updated profile data (varies by role)",
            ),
            400: OpenApiResponse(description="Validation error"),
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
    description=(
        "View a published trainer profile by slug. Returns 404 if not published."
    ),
    responses={
        200: OpenApiResponse(
            response=TrainerProfilePublicSerializer,
            description="Trainer profile",
        ),
        404: OpenApiResponse(description="Not found or not published"),
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
    description="View a published gym profile by slug. Returns 404 if not published.",
    responses={
        200: OpenApiResponse(
            response=GymProfilePublicSerializer,
            description="Gym profile",
        ),
        404: OpenApiResponse(description="Not found or not published"),
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
    description=(
        "Search published trainer and gym profiles. "
        "Params: q (name search), type (trainer|gym, default trainer), "
        "location, specialisation (slug), session_type."
    ),
    parameters=[
        OpenApiParameter("q", str, description="Search term"),
        OpenApiParameter(
            "type",
            str,
            description="Profile type: trainer (default) or gym",
            required=False,
        ),
        OpenApiParameter("location", str, description="Filter by location"),
        OpenApiParameter(
            "specialisation", str, description="Trainer specialisation slug"
        ),
        OpenApiParameter("session_type", str, description="Availability session type"),
    ],
    responses={200: OpenApiResponse(description="Paginated profile results")},
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
    description="Upload a profile photo (JPG or PNG, max 5 MB). Returns the new URL.",
    request=PhotoUploadSerializer,
    responses={
        200: OpenApiResponse(description="Photo URL"),
        400: OpenApiResponse(description="File missing, wrong type, or too large"),
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
    description="Upload a cover photo (JPG or PNG, max 5 MB). Returns the new URL.",
    request=CoverUploadSerializer,
    responses={
        200: OpenApiResponse(description="Cover photo URL"),
        400: OpenApiResponse(description="File missing, wrong type, or too large"),
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
    description="Return all available specialisations for trainer profiles.",
    responses={
        200: OpenApiResponse(
            response=SpecialisationSerializer(many=True),
            description="Specialisation list",
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
