"""Views for the trackers app — exercise and nutrition logging."""

from django.db.models import Max
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import IsClient
from apps.core.error_codes import ErrorCode
from apps.core.pagination import StandardPagination
from apps.core.responses import APIResponse

from .models import DailyNutritionLog, ExerciseEntry, MealEntry, WorkoutLog
from .permissions import HasTrackerAddon
from .serializers import (
    DailyNutritionLogDetailSerializer,
    DailyNutritionLogListSerializer,
    MealEntrySerializer,
    NutritionGoalUpdateSerializer,
    WorkoutLogSerializer,
)

# ─────────────────────────────────────────────────────────────────────────────
# Addon management
# ─────────────────────────────────────────────────────────────────────────────


@extend_schema(tags=["Trackers"])
class AddonStatusView(APIView):
    """GET — return the tracker addon status for the authenticated client."""

    permission_classes = [IsAuthenticated, IsClient]

    @extend_schema(
        summary="Get tracker addon status",
        description=(
            "Returns whether the tracker add-on is active for the authenticated client."
        ),
        responses={
            200: OpenApiResponse(description="Addon status returned"),
            403: OpenApiResponse(description="Not a client account"),
        },
    )
    def get(self, request):
        profile = request.user.client_profile
        return APIResponse.success(
            data={"addon_active": profile.tracker_addon_active},
            message="Addon status retrieved.",
        )


@extend_schema(tags=["Trackers"])
class AddonActivateView(APIView):
    """POST — activate the tracker addon for the authenticated client."""

    permission_classes = [IsAuthenticated, IsClient]

    @extend_schema(
        summary="Activate tracker addon",
        description=(
            "Activates the tracker add-on for the authenticated client. "
            "Idempotent — calling again when already active is a no-op."
        ),
        responses={
            200: OpenApiResponse(description="Addon activated"),
            403: OpenApiResponse(description="Not a client account"),
        },
    )
    def post(self, request):
        profile = request.user.client_profile
        profile.tracker_addon_active = True
        profile.save(update_fields=["tracker_addon_active"])
        return APIResponse.success(
            data={"addon_active": True},
            message="Tracker add-on activated.",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Exercise / workout logs
# ─────────────────────────────────────────────────────────────────────────────


@extend_schema(tags=["Trackers"])
class WorkoutLogListCreateView(APIView):
    """GET + POST workout logs for the authenticated client."""

    permission_classes = [IsAuthenticated, HasTrackerAddon]

    @extend_schema(
        summary="List workout logs",
        description=(
            "Returns paginated workout logs for the authenticated client. "
            "Supports optional ?date=YYYY-MM-DD filter."
        ),
        responses={
            200: OpenApiResponse(description="Paginated workout logs"),
            403: OpenApiResponse(description="Tracker add-on required"),
        },
    )
    def get(self, request):
        profile = request.user.client_profile
        qs = WorkoutLog.objects.filter(client=profile).prefetch_related("exercises")

        date_param = request.query_params.get("date")
        if date_param:
            qs = qs.filter(date=date_param)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = WorkoutLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        summary="Create a workout log",
        description=(
            "Creates a new workout log with exercises for the authenticated client. "
            "At least one exercise is required."
        ),
        request=WorkoutLogSerializer,
        responses={
            201: OpenApiResponse(description="Workout log created"),
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Tracker add-on required"),
        },
    )
    def post(self, request):
        profile = request.user.client_profile
        serializer = WorkoutLogSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Validation error.",
                errors=serializer.errors,
                code=ErrorCode.VALIDATION_ERROR,
            )
        log = serializer.save(client=profile)
        return APIResponse.created(
            data=WorkoutLogSerializer(log).data,
            message="Workout log created.",
        )


@extend_schema(tags=["Trackers"])
class PersonalRecordsView(APIView):
    """GET — personal best (max weight) per exercise for the authenticated client."""

    permission_classes = [IsAuthenticated, HasTrackerAddon]

    @extend_schema(
        summary="Get personal records",
        description=(
            "Returns the personal best (max weight lifted) per exercise. "
            "Exercises without weight are excluded. "
            "Results are ordered alphabetically by exercise name."
        ),
        responses={
            200: OpenApiResponse(description="Personal records"),
            403: OpenApiResponse(description="Tracker add-on required"),
        },
    )
    def get(self, request):
        profile = request.user.client_profile
        aggregated = (
            ExerciseEntry.objects.filter(
                workout_log__client=profile,
                workout_log__deleted_at__isnull=True,
                weight_kg__isnull=False,
            )
            .values("name")
            .annotate(max_weight=Max("weight_kg"))
            .order_by("name")
        )

        records = []
        for rec in aggregated:
            entry = (
                ExerciseEntry.objects.filter(
                    workout_log__client=profile,
                    workout_log__deleted_at__isnull=True,
                    name=rec["name"],
                    weight_kg=rec["max_weight"],
                )
                .select_related("workout_log")
                .order_by("-workout_log__date")
                .first()
            )
            records.append(
                {
                    "exercise_name": rec["name"],
                    "max_weight_kg": str(rec["max_weight"]),
                    "logged_on": str(entry.workout_log.date) if entry else None,
                }
            )

        return APIResponse.success(
            data={"records": records},
            message="Personal records retrieved.",
        )


@extend_schema(tags=["Trackers"])
class WorkoutLogDetailView(APIView):
    """GET + PUT + DELETE a single workout log."""

    permission_classes = [IsAuthenticated, HasTrackerAddon]

    def _get_log(self, request, pk):
        try:
            return WorkoutLog.objects.prefetch_related("exercises").get(
                pk=pk, client=request.user.client_profile
            )
        except WorkoutLog.DoesNotExist:
            return None

    @extend_schema(
        summary="Retrieve a workout log",
        description="Returns a single workout log with its exercises.",
        responses={
            200: OpenApiResponse(description="Workout log detail"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    def get(self, request, pk):
        log = self._get_log(request, pk)
        if log is None:
            return APIResponse.error(
                message="Workout log not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        return APIResponse.success(
            data=WorkoutLogSerializer(log).data,
            message="Workout log retrieved.",
        )

    @extend_schema(
        summary="Update a workout log",
        description=(
            "Full update. Replaces all exercises — send the complete list. "
            "At least one exercise is required."
        ),
        request=WorkoutLogSerializer,
        responses={
            200: OpenApiResponse(description="Workout log updated"),
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    def put(self, request, pk):
        log = self._get_log(request, pk)
        if log is None:
            return APIResponse.error(
                message="Workout log not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        serializer = WorkoutLogSerializer(log, data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Validation error.",
                errors=serializer.errors,
                code=ErrorCode.VALIDATION_ERROR,
            )
        updated = serializer.save()
        return APIResponse.success(
            data=WorkoutLogSerializer(updated).data,
            message="Workout log updated.",
        )

    @extend_schema(
        summary="Delete a workout log",
        description="Soft-deletes the workout log. The record remains in the database.",
        responses={
            204: OpenApiResponse(description="Deleted"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    def delete(self, request, pk):
        log = self._get_log(request, pk)
        if log is None:
            return APIResponse.error(
                message="Workout log not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        log.delete()
        return APIResponse.no_content()


# ─────────────────────────────────────────────────────────────────────────────
# Nutrition logs
# ─────────────────────────────────────────────────────────────────────────────


@extend_schema(tags=["Trackers"])
class NutritionLogListCreateView(APIView):
    """GET + POST daily nutrition logs for the authenticated client."""

    permission_classes = [IsAuthenticated, HasTrackerAddon]

    @extend_schema(
        summary="List nutrition logs",
        description=(
            "Returns paginated daily nutrition logs for the authenticated client. "
            "Supports optional ?date=YYYY-MM-DD filter."
        ),
        responses={
            200: OpenApiResponse(description="Paginated nutrition logs"),
            403: OpenApiResponse(description="Tracker add-on required"),
        },
    )
    def get(self, request):
        profile = request.user.client_profile
        qs = DailyNutritionLog.objects.filter(client=profile)

        date_param = request.query_params.get("date")
        if date_param:
            qs = qs.filter(date=date_param)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = DailyNutritionLogListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        summary="Create or update a nutrition log",
        description=(
            "Creates a daily nutrition log for the given date. "
            "If a log already exists for that date, updates its goal fields instead. "
            "Returns 201 on creation, 200 on update."
        ),
        request=DailyNutritionLogListSerializer,
        responses={
            201: OpenApiResponse(description="Nutrition log created"),
            200: OpenApiResponse(description="Existing log updated"),
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Tracker add-on required"),
        },
    )
    def post(self, request):
        profile = request.user.client_profile
        date_val = request.data.get("date")
        if not date_val:
            return APIResponse.error(
                message="date is required.",
                errors={"date": ["This field is required."]},
                code=ErrorCode.VALIDATION_ERROR,
            )

        log, created = DailyNutritionLog.objects.get_or_create(
            client=profile,
            date=date_val,
        )

        goal_fields = {
            k: v
            for k, v in request.data.items()
            if k in ("calorie_goal", "protein_goal_g", "carbs_goal_g", "fat_goal_g")
        }
        if goal_fields:
            for field, value in goal_fields.items():
                setattr(log, field, value)
            log.save(update_fields=list(goal_fields.keys()))

        serializer = DailyNutritionLogListSerializer(log)
        if created:
            return APIResponse.created(
                data=serializer.data,
                message="Nutrition log created.",
            )
        return APIResponse.success(
            data=serializer.data,
            message="Nutrition log updated.",
        )


@extend_schema(tags=["Trackers"])
class NutritionLogDetailView(APIView):
    """GET + PUT a single daily nutrition log."""

    permission_classes = [IsAuthenticated, HasTrackerAddon]

    def _get_log(self, request, pk):
        try:
            return DailyNutritionLog.objects.prefetch_related("meals").get(
                pk=pk, client=request.user.client_profile
            )
        except DailyNutritionLog.DoesNotExist:
            return None

    @extend_schema(
        summary="Retrieve a nutrition log",
        description=(
            "Returns a daily nutrition log with all meal entries, macro totals, "
            "and calorie goal progress."
        ),
        responses={
            200: OpenApiResponse(description="Nutrition log detail"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    def get(self, request, pk):
        log = self._get_log(request, pk)
        if log is None:
            return APIResponse.error(
                message="Nutrition log not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        return APIResponse.success(
            data=DailyNutritionLogDetailSerializer(log).data,
            message="Nutrition log retrieved.",
        )

    @extend_schema(
        summary="Update nutrition goals",
        description="Update the calorie and macro goals for an existing nutrition log.",
        request=NutritionGoalUpdateSerializer,
        responses={
            200: OpenApiResponse(description="Goals updated"),
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    def put(self, request, pk):
        log = self._get_log(request, pk)
        if log is None:
            return APIResponse.error(
                message="Nutrition log not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        serializer = NutritionGoalUpdateSerializer(log, data=request.data, partial=True)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Validation error.",
                errors=serializer.errors,
                code=ErrorCode.VALIDATION_ERROR,
            )
        serializer.save()
        return APIResponse.success(
            data=DailyNutritionLogDetailSerializer(log).data,
            message="Nutrition goals updated.",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Meal entries
# ─────────────────────────────────────────────────────────────────────────────


@extend_schema(tags=["Trackers"])
class MealEntryCreateView(APIView):
    """POST — add a meal entry to a daily nutrition log."""

    permission_classes = [IsAuthenticated, HasTrackerAddon]

    def _get_log(self, request, log_pk):
        try:
            return DailyNutritionLog.objects.get(
                pk=log_pk, client=request.user.client_profile
            )
        except DailyNutritionLog.DoesNotExist:
            return None

    @extend_schema(
        summary="Add a meal entry",
        description="Adds a meal entry to the specified daily nutrition log.",
        request=MealEntrySerializer,
        responses={
            201: OpenApiResponse(description="Meal entry created"),
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Nutrition log not found"),
        },
    )
    def post(self, request, log_pk):
        log = self._get_log(request, log_pk)
        if log is None:
            return APIResponse.error(
                message="Nutrition log not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        serializer = MealEntrySerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Validation error.",
                errors=serializer.errors,
                code=ErrorCode.VALIDATION_ERROR,
            )
        meal = serializer.save(nutrition_log=log)
        return APIResponse.created(
            data=MealEntrySerializer(meal).data,
            message="Meal entry added.",
        )


@extend_schema(tags=["Trackers"])
class MealEntryDeleteView(APIView):
    """DELETE — remove a meal entry from a daily nutrition log."""

    permission_classes = [IsAuthenticated, HasTrackerAddon]

    def _get_objects(self, request, log_pk, meal_pk):
        try:
            log = DailyNutritionLog.objects.get(
                pk=log_pk, client=request.user.client_profile
            )
        except DailyNutritionLog.DoesNotExist:
            return None, None
        try:
            meal = MealEntry.objects.get(pk=meal_pk, nutrition_log=log)
        except MealEntry.DoesNotExist:
            return log, None
        return log, meal

    @extend_schema(
        summary="Delete a meal entry",
        description="Soft-deletes a meal entry from the specified daily nutrition log.",
        responses={
            204: OpenApiResponse(description="Meal entry deleted"),
            404: OpenApiResponse(description="Log or meal entry not found"),
        },
    )
    def delete(self, request, log_pk, meal_pk):
        log, meal = self._get_objects(request, log_pk, meal_pk)
        if log is None or meal is None:
            return APIResponse.error(
                message="Not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        meal.delete()
        return APIResponse.no_content()
