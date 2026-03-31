"""
Sessions app views — training session logging.
"""

import datetime

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import IsTrainerOrGym
from apps.core.error_codes import ErrorCode
from apps.core.pagination import StandardPagination
from apps.core.responses import APIResponse
from apps.profiles.models import ClientProfile, GymProfile, TrainerProfile
from apps.sessions.models import Session
from apps.sessions.serializers import (
    SessionCreateSerializer,
    SessionSerializer,
    SessionUpdateSerializer,
)
from apps.sessions.tasks import check_session_badges

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _base_queryset(user):
    """Return role-scoped session queryset (soft-delete filtered)."""
    qs = Session.objects.select_related("trainer__user", "client__user")
    if user.role == "trainer":
        try:
            profile = user.trainer_profile
        except TrainerProfile.DoesNotExist:
            return qs.none()
        return qs.filter(trainer=profile)
    if user.role == "client":
        try:
            profile = user.client_profile
        except ClientProfile.DoesNotExist:
            return qs.none()
        return qs.filter(client=profile)
    if user.role == "gym":
        try:
            gym = user.gym_profile
        except GymProfile.DoesNotExist:
            return qs.none()
        return qs.filter(trainer__gym=gym)
    return qs.none()


# ─────────────────────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────────────────────


@extend_schema(tags=["Sessions"])
class SessionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List sessions",
        description=(
            "Returns paginated sessions scoped to the authenticated user's role. "
            "Trainers see their own sessions, clients see their own, "
            "gyms see all sessions from their trainers. "
            "Supports filtering by status, client_id, date_from, date_to."
        ),
        parameters=[
            OpenApiParameter("status", str, description="Filter by status enum"),
            OpenApiParameter(
                "client_id", str, description="Filter by client UUID (trainer/gym only)"
            ),
            OpenApiParameter("date_from", str, description="YYYY-MM-DD lower bound"),
            OpenApiParameter("date_to", str, description="YYYY-MM-DD upper bound"),
        ],
        responses={200: OpenApiResponse(description="Paginated session list")},
    )
    def get(self, request):
        qs = _base_queryset(request.user)

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        client_id = request.query_params.get("client_id")
        if client_id and request.user.role in ("trainer", "gym"):
            qs = qs.filter(client__id=client_id)

        date_from = request.query_params.get("date_from")
        if date_from:
            qs = qs.filter(session_date__gte=date_from)

        date_to = request.query_params.get("date_to")
        if date_to:
            qs = qs.filter(session_date__lte=date_to)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = SessionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        summary="Log a new session",
        description=(
            "Create a new session log. Trainer only. "
            "Client must have an active membership with the trainer. "
            "Triggers milestone badge check for completed sessions."
        ),
        responses={
            201: OpenApiResponse(description="Session created"),
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Not a trainer"),
        },
    )
    def post(self, request):
        if request.user.role != "trainer":
            return APIResponse.error(
                message="Only trainers can log sessions.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        try:
            trainer_profile = request.user.trainer_profile
        except TrainerProfile.DoesNotExist:
            return APIResponse.error(
                message="Trainer profile not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        serializer = SessionCreateSerializer(
            data=request.data,
            context={"trainer": trainer_profile},
        )
        if not serializer.is_valid():
            return APIResponse.error(
                message="Validation error.",
                errors=serializer.errors,
                code=ErrorCode.VALIDATION_ERROR,
            )

        data = serializer.validated_data
        client_profile = ClientProfile.objects.get(id=data["client_id"])

        with transaction.atomic():
            session = Session.objects.create(
                trainer=trainer_profile,
                client=client_profile,
                session_date=data["session_date"],
                session_time=data.get("session_time"),
                duration_minutes=data.get("duration_minutes", 60),
                session_type=data.get("session_type", Session.SessionType.PHYSICAL),
                virtual_platform=data.get("virtual_platform", ""),
                notes=data.get("notes", ""),
                status=data.get("status", Session.Status.COMPLETED),
            )

        if session.status == Session.Status.COMPLETED:
            check_session_badges.delay(str(client_profile.id), str(trainer_profile.id))

        return APIResponse.created(
            data=SessionSerializer(session).data,
            message="Session logged successfully.",
        )


@extend_schema(tags=["Sessions"])
class SessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_session(self, pk):
        try:
            return Session.objects.get(id=pk)
        except Session.DoesNotExist:
            return None

    def _is_owner(self, session, user):
        if user.role == "trainer":
            try:
                return session.trainer == user.trainer_profile
            except TrainerProfile.DoesNotExist:
                return False
        if user.role == "client":
            try:
                return session.client == user.client_profile
            except ClientProfile.DoesNotExist:
                return False
        if user.role == "gym":
            try:
                return session.trainer.gym == user.gym_profile
            except Exception:
                return False
        return False

    @extend_schema(
        summary="Retrieve a session",
        responses={
            200: OpenApiResponse(description="Session detail"),
            403: OpenApiResponse(description="Not your session"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    def get(self, request, pk):
        session = self._get_session(pk)
        if session is None:
            return APIResponse.error(
                message="Session not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        if not self._is_owner(session, request.user):
            return APIResponse.error(
                message="You do not have permission to view this session.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )
        return APIResponse.success(data=SessionSerializer(session).data)

    @extend_schema(
        summary="Update a session",
        description="Partial update. Trainer who owns the session only.",
        responses={
            200: OpenApiResponse(description="Updated"),
            403: OpenApiResponse(description="Not your session"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    def put(self, request, pk):
        session = self._get_session(pk)
        if session is None:
            return APIResponse.error(
                message="Session not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        if request.user.role != "trainer":
            return APIResponse.error(
                message="Only trainers can update sessions.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        try:
            trainer_profile = request.user.trainer_profile
        except TrainerProfile.DoesNotExist:
            return APIResponse.error(
                message="Trainer profile not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        if session.trainer != trainer_profile:
            return APIResponse.error(
                message="You do not have permission to update this session.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        serializer = SessionUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Validation error.",
                errors=serializer.errors,
                code=ErrorCode.VALIDATION_ERROR,
            )

        for field, value in serializer.validated_data.items():
            setattr(session, field, value)
        session.save()

        return APIResponse.success(
            data=SessionSerializer(session).data,
            message="Session updated.",
        )

    @extend_schema(
        summary="Delete (soft) a session",
        description="Soft-deletes the session. Trainer who owns it only.",
        responses={
            200: OpenApiResponse(description="Deleted"),
            403: OpenApiResponse(description="Not your session"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    def delete(self, request, pk):
        session = self._get_session(pk)
        if session is None:
            return APIResponse.error(
                message="Session not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        if request.user.role != "trainer":
            return APIResponse.error(
                message="Only trainers can delete sessions.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        try:
            trainer_profile = request.user.trainer_profile
        except TrainerProfile.DoesNotExist:
            return APIResponse.error(
                message="Trainer profile not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        if session.trainer != trainer_profile:
            return APIResponse.error(
                message="You do not have permission to delete this session.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        session.delete()
        return APIResponse.success(message="Session deleted.")


@extend_schema(tags=["Sessions"])
class UpcomingSessionsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List upcoming sessions",
        description=(
            "Returns up to 5 upcoming sessions (today or later), ordered ASC. "
            "Role-scoped like the main list endpoint."
        ),
        responses={200: OpenApiResponse(description="Upcoming sessions list")},
    )
    def get(self, request):
        today = datetime.date.today()
        qs = (
            _base_queryset(request.user)
            .filter(session_date__gte=today)
            .order_by("session_date", "created_at")[:5]
        )
        return APIResponse.success(data=SessionSerializer(qs, many=True).data)


@extend_schema(tags=["Sessions"])
class SessionStatsView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    @extend_schema(
        summary="Session statistics",
        description=(
            "Returns session counts: total, by status, this month, last month, "
            "and month-on-month growth percentage. Trainer/gym only."
        ),
        responses={
            200: OpenApiResponse(description="Stats object"),
            403: OpenApiResponse(description="Clients not allowed"),
        },
    )
    def get(self, request):
        qs = _base_queryset(request.user).filter(status=Session.Status.COMPLETED)

        now = timezone.now()
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 1:
            first_of_last_month = first_of_month.replace(year=now.year - 1, month=12)
        else:
            first_of_last_month = first_of_month.replace(month=now.month - 1)

        total = qs.count()
        this_month = qs.filter(session_date__gte=first_of_month.date()).count()
        last_month = qs.filter(
            session_date__gte=first_of_last_month.date(),
            session_date__lt=first_of_month.date(),
        ).count()

        if last_month == 0:
            growth_percent = 0
        else:
            growth_percent = round(((this_month - last_month) / last_month) * 100, 1)

        all_qs = _base_queryset(request.user)
        cancelled = all_qs.filter(status=Session.Status.CANCELLED).count()
        no_show = all_qs.filter(status=Session.Status.NO_SHOW).count()

        return APIResponse.success(
            data={
                "total": total,
                "completed": total,
                "cancelled": cancelled,
                "no_show": no_show,
                "this_month": this_month,
                "last_month": last_month,
                "growth_percent": growth_percent,
            }
        )
