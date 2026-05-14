"""
Role-specific onboarding views.
"""

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.error_codes import ErrorCode
from apps.core.permissions import IsClient, IsGym, IsTrainer
from apps.core.responses import APIResponse
from apps.profiles.models import Goal, Service, Specialisation
from apps.profiles.serializers import (
    GoalSerializer,
    ServiceSerializer,
    SpecialisationSerializer,
)


def _trainer_profile(user):
    try:
        return user.trainer_profile
    except Exception:
        return None


def _gym_profile(user):
    try:
        return user.gym_profile
    except Exception:
        return None


def _client_profile(user):
    try:
        return user.client_profile
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Trainer expertise (step 1)
# ---------------------------------------------------------------------------


@extend_schema(
    summary="Get expertise options for onboarding picker (trainer step 1)",
    description=(
        "GET — returns all available expertise options for the picker screen. "
        "Use ?is_predefined=true for predefined options only.\n"
        "POST — attaches selected expertise to the trainer profile and advances "
        "onboarding to step 1.\n"
        "Body: {expertise_ids: [1,2,3], custom_names: ['Optional custom expertise']}"
    ),
    request=inline_serializer(
        name="TrainerExpertiseRequest",
        fields={
            "expertise_ids": drf_serializers.ListField(
                child=drf_serializers.IntegerField(),
                required=False,
                default=list,
            ),
            "custom_names": drf_serializers.ListField(
                child=drf_serializers.CharField(),
                required=False,
                default=list,
            ),
        },
    ),
    responses={
        200: OpenApiResponse(description="Expertise attached"),
        400: OpenApiResponse(description="Exceeds 10-specialisation limit"),
        401: OpenApiResponse(description="Not authenticated"),
        403: OpenApiResponse(description="Not a trainer"),
    },
    tags=["Onboarding"],
)
class TrainerExpertiseView(APIView):
    permission_classes = [IsAuthenticated, IsTrainer]

    def get(self, request):
        qs = Specialisation.objects.all().order_by("name")
        is_predefined = request.query_params.get("is_predefined")
        if is_predefined == "true":
            qs = qs.filter(is_predefined=True)
        elif is_predefined == "false":
            qs = qs.filter(is_predefined=False)
        return APIResponse.success(
            data={"expertise": SpecialisationSerializer(qs, many=True).data},
            message="Expertise options retrieved.",
        )

    def post(self, request):
        user = request.user
        profile = _trainer_profile(user)
        if not profile:
            return APIResponse.error(
                message="Profile not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        expertise_ids = request.data.get("expertise_ids", []) or []
        custom_names = request.data.get("custom_names", []) or []

        existing_count = profile.specialisations.count()
        if existing_count + len(expertise_ids) + len(custom_names) > 10:
            return APIResponse.error(
                message="You can have at most 10 specialisations.",
                code=ErrorCode.VALIDATION_ERROR,
                status_code=400,
            )

        with transaction.atomic():
            if expertise_ids:
                specs = Specialisation.objects.filter(id__in=expertise_ids)
                profile.specialisations.add(*specs)

            for raw_name in custom_names:
                name = raw_name.strip()
                if name:
                    spec, _ = Specialisation.objects.get_or_create(
                        name=name,
                        defaults={"is_predefined": False},
                    )
                    profile.specialisations.add(spec)

            user.onboarding_step = max(user.onboarding_step, 1)
            user.save(update_fields=["onboarding_step"])

            if user.onboarding_status != user.OnboardingStatus.COMPLETED:
                user.onboarding_status = user.OnboardingStatus.IN_PROGRESS
                user.save(update_fields=["onboarding_status"])

        return APIResponse.success(
            data={
                "expertise": SpecialisationSerializer(
                    profile.specialisations.all(), many=True
                ).data,
                "onboarding_step": user.onboarding_step,
            },
            message="Expertise updated.",
        )


# ---------------------------------------------------------------------------
# Trainer products (step 2)
# ---------------------------------------------------------------------------


@extend_schema(
    summary="Get or set trainer products flag (onboarding step 2)",
    description=(
        "GET — returns current offers_products value for the trainer.\n\n"
        "POST — sets offers_products, publishes the profile, "
        "and completes onboarding (step 2)."
    ),
    request=inline_serializer(
        name="TrainerProductsRequest",
        fields={
            "offers_products": drf_serializers.BooleanField(),
        },
    ),
    responses={
        200: OpenApiResponse(description="Products flag set, profile published"),
        401: OpenApiResponse(description="Not authenticated"),
        403: OpenApiResponse(description="Not a trainer"),
    },
    tags=["Onboarding"],
)
class TrainerProductsView(APIView):
    permission_classes = [IsAuthenticated, IsTrainer]

    def get(self, request):
        profile = _trainer_profile(request.user)
        if not profile:
            return APIResponse.error(
                message="Profile not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        return APIResponse.success(
            data={"offers_products": profile.offers_products},
            message="Products status retrieved.",
        )

    def post(self, request):
        user = request.user
        profile = _trainer_profile(user)
        if not profile:
            return APIResponse.error(
                message="Profile not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        offers_products = bool(request.data.get("offers_products", False))

        with transaction.atomic():
            profile.offers_products = offers_products
            profile.is_published = True
            profile.save(update_fields=["offers_products", "is_published"])

            user.onboarding_step = 2
            user.save(update_fields=["onboarding_step"])
            user.complete_onboarding()

        return APIResponse.success(
            data={
                "offers_products": profile.offers_products,
                "is_published": True,
                "onboarding_step": user.onboarding_step,
                "current_step": user.onboarding_step,
                "total_steps": 2,
                "role": "trainer",
                "full_name": profile.full_name,
                "location": user.country,
                "expertise": SpecialisationSerializer(
                    profile.specialisations.all(), many=True
                ).data,
            },
            message="Onboarding complete.",
        )


# ---------------------------------------------------------------------------
# Gym services (step 1)
# ---------------------------------------------------------------------------


@extend_schema(
    summary="Get service options and current services (gym onboarding step 1)",
    description=(
        "GET — returns session_type picker options and the gym's current services.\n\n"
        "POST — replaces all services and advances onboarding_step to 1."
    ),
    request=inline_serializer(
        name="GymServicesRequest",
        fields={
            "services": drf_serializers.ListField(
                child=inline_serializer(
                    name="ServiceItem",
                    fields={
                        "name": drf_serializers.CharField(),
                        "description": drf_serializers.CharField(
                            required=False, default=""
                        ),
                        "session_type": drf_serializers.ChoiceField(
                            choices=["physical", "virtual", "both"],
                            required=False,
                            default="both",
                        ),
                        "display_order": drf_serializers.IntegerField(
                            required=False, default=0
                        ),
                    },
                )
            ),
        },
    ),
    responses={
        200: OpenApiResponse(description="Services saved"),
        401: OpenApiResponse(description="Not authenticated"),
        403: OpenApiResponse(description="Not a gym"),
    },
    tags=["Onboarding"],
)
class GymServicesView(APIView):
    permission_classes = [IsAuthenticated, IsGym]

    SESSION_TYPE_OPTIONS = [
        {"value": "physical", "label": "Physical"},
        {"value": "virtual", "label": "Virtual"},
        {"value": "both", "label": "Both"},
    ]

    def get(self, request):
        profile = _gym_profile(request.user)
        if not profile:
            return APIResponse.error(
                message="Profile not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        return APIResponse.success(
            data={
                "session_type_options": self.SESSION_TYPE_OPTIONS,
                "current_services": ServiceSerializer(
                    profile.services.all(), many=True
                ).data,
            },
            message="Services retrieved.",
        )

    def post(self, request):
        user = request.user
        profile = _gym_profile(user)
        if not profile:
            return APIResponse.error(
                message="Profile not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        services_data = request.data.get("services", []) or []

        with transaction.atomic():
            profile.services.all().delete()
            for svc in services_data:
                Service.objects.create(
                    gym=profile,
                    name=svc.get("name", ""),
                    description=svc.get("description", ""),
                    session_type=svc.get("session_type", Service.SessionType.BOTH),
                    display_order=svc.get("display_order", 0),
                )

            user.onboarding_step = max(user.onboarding_step, 1)
            user.save(update_fields=["onboarding_step"])

            if user.onboarding_status != user.OnboardingStatus.COMPLETED:
                user.onboarding_status = user.OnboardingStatus.IN_PROGRESS
                user.save(update_fields=["onboarding_status"])

        return APIResponse.success(
            data={
                "services": ServiceSerializer(profile.services.all(), many=True).data,
                "onboarding_step": user.onboarding_step,
            },
            message="Services saved.",
        )


# ---------------------------------------------------------------------------
# Gym products (step 2)
# ---------------------------------------------------------------------------


@extend_schema(
    summary="Get or set gym products flag (onboarding step 2)",
    description=(
        "GET — returns current offers_products value for the gym.\n\n"
        "POST — sets offers_products, publishes the gym profile, "
        "and completes onboarding."
    ),
    request=inline_serializer(
        name="GymProductsRequest",
        fields={
            "offers_products": drf_serializers.BooleanField(),
        },
    ),
    responses={
        200: OpenApiResponse(description="Products flag set, profile published"),
        401: OpenApiResponse(description="Not authenticated"),
        403: OpenApiResponse(description="Not a gym"),
    },
    tags=["Onboarding"],
)
class GymProductsView(APIView):
    permission_classes = [IsAuthenticated, IsGym]

    def get(self, request):
        profile = _gym_profile(request.user)
        if not profile:
            return APIResponse.error(
                message="Profile not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        return APIResponse.success(
            data={"offers_products": profile.offers_products},
            message="Products status retrieved.",
        )

    def post(self, request):
        user = request.user
        profile = _gym_profile(user)
        if not profile:
            return APIResponse.error(
                message="Profile not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        offers_products = bool(request.data.get("offers_products", False))

        with transaction.atomic():
            profile.offers_products = offers_products
            profile.is_published = True
            profile.save(update_fields=["offers_products", "is_published"])

            user.onboarding_step = 2
            user.save(update_fields=["onboarding_step"])
            user.complete_onboarding()

        return APIResponse.success(
            data={
                "offers_products": profile.offers_products,
                "is_published": True,
                "onboarding_step": user.onboarding_step,
                "current_step": user.onboarding_step,
                "total_steps": 2,
                "role": "gym",
                "full_name": profile.full_name,
                "location": user.country,
                "services": ServiceSerializer(profile.services.all(), many=True).data,
            },
            message="Onboarding complete.",
        )


# ---------------------------------------------------------------------------
# Client goal (step 1)
# ---------------------------------------------------------------------------


@extend_schema(
    summary="Get goal options for onboarding picker (client step 1)",
    description=(
        "GET — returns all available goal options for the picker screen.\n"
        "POST — attaches selected goals to the client profile and advances "
        "onboarding to step 1.\n"
        "Body: {goal_ids: [1,2], custom_names: ['Optional custom goal']}"
    ),
    request=inline_serializer(
        name="ClientGoalRequest",
        fields={
            "goal_ids": drf_serializers.ListField(
                child=drf_serializers.IntegerField(), required=False, default=list
            ),
            "custom_names": drf_serializers.ListField(
                child=drf_serializers.CharField(), required=False, default=list
            ),
        },
    ),
    responses={
        200: OpenApiResponse(description="Goals attached"),
        400: OpenApiResponse(description="Exceeds 6-goal limit"),
        401: OpenApiResponse(description="Not authenticated"),
        403: OpenApiResponse(description="Not a client"),
    },
    tags=["Onboarding"],
)
class ClientGoalView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def get(self, request):
        qs = Goal.objects.all().order_by("name")
        is_predefined = request.query_params.get("is_predefined")
        if is_predefined == "true":
            qs = qs.filter(is_predefined=True)
        elif is_predefined == "false":
            qs = qs.filter(is_predefined=False)
        return APIResponse.success(
            data={"goals": GoalSerializer(qs, many=True).data},
            message="Goal options retrieved.",
        )

    def post(self, request):
        user = request.user
        profile = _client_profile(user)
        if not profile:
            return APIResponse.error(
                message="Profile not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        goal_ids = request.data.get("goal_ids", []) or []
        custom_names = request.data.get("custom_names", []) or []

        existing_count = profile.primary_goals.count()
        if existing_count + len(goal_ids) + len(custom_names) > 6:
            return APIResponse.error(
                message="You can have at most 6 goals.",
                code=ErrorCode.VALIDATION_ERROR,
                status_code=400,
            )

        with transaction.atomic():
            if goal_ids:
                goals = Goal.objects.filter(id__in=goal_ids)
                profile.primary_goals.add(*goals)

            for raw_name in custom_names:
                name = raw_name.strip()
                if name:
                    goal, _ = Goal.objects.get_or_create(
                        name=name,
                        defaults={"is_predefined": False},
                    )
                    profile.primary_goals.add(goal)

            user.onboarding_step = max(user.onboarding_step, 1)
            user.save(update_fields=["onboarding_step"])

            if user.onboarding_status != user.OnboardingStatus.COMPLETED:
                user.onboarding_status = user.OnboardingStatus.IN_PROGRESS
                user.save(update_fields=["onboarding_status"])

        return APIResponse.success(
            data={
                "goals": GoalSerializer(profile.primary_goals.all(), many=True).data,
                "onboarding_step": user.onboarding_step,
            },
            message="Goals updated.",
        )


@extend_schema(
    summary="Remove a goal from client profile",
    description="Removes a goal from the client's primary_goals.",
    responses={
        204: OpenApiResponse(description="Removed"),
        404: OpenApiResponse(description="Goal not attached to this profile"),
    },
    tags=["Onboarding"],
)
class ClientGoalDetailView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def delete(self, request, goal_id):
        profile = _client_profile(request.user)
        if not profile:
            return APIResponse.error(
                message="Profile not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        try:
            goal = profile.primary_goals.get(id=goal_id)
        except Goal.DoesNotExist:
            return APIResponse.error(
                message="Goal not found on your profile.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        profile.primary_goals.remove(goal)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Client focus (step 2)
# ---------------------------------------------------------------------------


@extend_schema(
    summary="Get focus area options for onboarding picker (client step 2)",
    description=(
        "GET — returns all available focus area options for the picker screen.\n"
        "POST — attaches selected focus areas to the client profile and completes "
        "onboarding.\n"
        "Body: {specialisation_ids: [1,2,3], custom_names: ['Optional custom focus']}"
    ),
    request=inline_serializer(
        name="ClientFocusRequest",
        fields={
            "specialisation_ids": drf_serializers.ListField(
                child=drf_serializers.IntegerField(), required=False, default=list
            ),
            "custom_names": drf_serializers.ListField(
                child=drf_serializers.CharField(), required=False, default=list
            ),
        },
    ),
    responses={
        200: OpenApiResponse(description="Focus areas attached, onboarding complete"),
        400: OpenApiResponse(description="Exceeds 10-specialisation limit"),
        401: OpenApiResponse(description="Not authenticated"),
        403: OpenApiResponse(description="Not a client"),
    },
    tags=["Onboarding"],
)
class ClientFocusView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def get(self, request):
        qs = Specialisation.objects.all().order_by("name")
        is_predefined = request.query_params.get("is_predefined")
        if is_predefined == "true":
            qs = qs.filter(is_predefined=True)
        elif is_predefined == "false":
            qs = qs.filter(is_predefined=False)
        return APIResponse.success(
            data={"focus_areas": SpecialisationSerializer(qs, many=True).data},
            message="Focus area options retrieved.",
        )

    def post(self, request):
        user = request.user
        profile = _client_profile(user)
        if not profile:
            return APIResponse.error(
                message="Profile not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        specialisation_ids = request.data.get("specialisation_ids", []) or []
        custom_names = request.data.get("custom_names", []) or []

        existing_count = profile.specialisations.count()
        if existing_count + len(specialisation_ids) + len(custom_names) > 10:
            return APIResponse.error(
                message="You can have at most 10 specialisations.",
                code=ErrorCode.VALIDATION_ERROR,
                status_code=400,
            )

        with transaction.atomic():
            if specialisation_ids:
                specs = Specialisation.objects.filter(id__in=specialisation_ids)
                profile.specialisations.add(*specs)

            for raw_name in custom_names:
                name = raw_name.strip()
                if name:
                    spec, _ = Specialisation.objects.get_or_create(
                        name=name,
                        defaults={"is_predefined": False},
                    )
                    profile.specialisations.add(spec)

            user.onboarding_step = 2
            user.save(update_fields=["onboarding_step"])
            user.complete_onboarding()

        return APIResponse.success(
            data={
                "onboarding_step": user.onboarding_step,
                "current_step": user.onboarding_step,
                "total_steps": 2,
                "role": "client",
                "full_name": profile.full_name,
                "location": user.country,
                "goals": GoalSerializer(profile.primary_goals.all(), many=True).data,
                "focus": SpecialisationSerializer(
                    profile.specialisations.all(), many=True
                ).data,
            },
            message="Focus areas updated. Onboarding complete.",
        )


@extend_schema(
    summary="Remove a focus area (specialisation) from client profile",
    description="Removes a specialisation from the client's focus areas.",
    responses={
        204: OpenApiResponse(description="Removed"),
        404: OpenApiResponse(description="Specialisation not attached to this profile"),
    },
    tags=["Onboarding"],
)
class ClientFocusDetailView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def delete(self, request, specialisation_id):
        profile = _client_profile(request.user)
        if not profile:
            return APIResponse.error(
                message="Profile not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        try:
            spec = profile.specialisations.get(id=specialisation_id)
        except Specialisation.DoesNotExist:
            return APIResponse.error(
                message="Specialisation not found on your profile.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        profile.specialisations.remove(spec)
        return Response(status=status.HTTP_204_NO_CONTENT)
