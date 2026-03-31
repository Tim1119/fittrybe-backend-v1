"""
Badges app views — badge management, assignment, leaderboard,
and weekly recognition post.
"""

import datetime

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import IsTrainerOrGym
from apps.badges.models import Badge, BadgeAssignment
from apps.badges.serializers import (
    BadgeAssignmentSerializer,
    BadgeSerializer,
    RecognitionSlotSerializer,
)
from apps.badges.tasks import post_badge_to_chatroom
from apps.chat.models import Chatroom, Message
from apps.clients.models import ClientMembership
from apps.core.error_codes import ErrorCode
from apps.core.pagination import StandardPagination
from apps.core.responses import APIResponse
from apps.notifications.tasks import send_push_notification
from apps.profiles.models import ClientProfile, GymProfile, TrainerProfile
from apps.sessions.models import Session

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _get_trainer_gym(user):
    """Return (trainer_profile, gym_profile) for the user."""
    if user.role == "trainer":
        return getattr(user, "trainer_profile", None), None
    if user.role == "gym":
        return None, getattr(user, "gym_profile", None)
    return None, None


def _client_in_community(client, trainer=None, gym=None):
    """Return True if client has active membership with trainer or gym."""
    qs = ClientMembership.objects.filter(
        client=client,
        status=ClientMembership.Status.ACTIVE,
        deleted_at__isnull=True,
    )
    if trainer:
        return qs.filter(trainer=trainer).exists()
    if gym:
        return qs.filter(gym=gym).exists()
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Badge CRUD
# ─────────────────────────────────────────────────────────────────────────────


@extend_schema(tags=["Badges"])
class BadgeListCreateView(APIView):
    permission_classes = []

    @extend_schema(
        summary="List all badges",
        description="Returns all badges. Public endpoint. Optional filter: badge_type.",
        parameters=[
            OpenApiParameter(
                "badge_type",
                str,
                description="milestone | streak | weekly_top | manual",
            )
        ],
        responses={200: OpenApiResponse(description="Paginated badge list")},
        auth=[],
    )
    def get(self, request):
        qs = Badge.objects.all()
        badge_type = request.query_params.get("badge_type")
        if badge_type:
            qs = qs.filter(badge_type=badge_type)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = BadgeSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        summary="Create a custom badge",
        description=(
            "Create a non-system badge. Trainer or gym only. "
            "is_system is always forced to False. "
            "milestone_threshold is only allowed when badge_type=milestone."
        ),
        responses={
            201: OpenApiResponse(description="Badge created"),
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Not trainer/gym"),
        },
    )
    def post(self, request):
        if not request.user.is_authenticated:
            return APIResponse.error(
                message="Authentication required.",
                code=ErrorCode.AUTHENTICATION_REQUIRED,
                status_code=401,
            )
        if request.user.role not in ("trainer", "gym"):
            return APIResponse.error(
                message="Only trainers and gyms can create badges.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        data = (
            request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        )
        data["is_system"] = False

        threshold = data.get("milestone_threshold")
        if threshold is not None and data.get("badge_type") != "milestone":
            return APIResponse.error(
                message="milestone_threshold is only allowed for badge_type=milestone.",
                code=ErrorCode.VALIDATION_ERROR,
            )

        serializer = BadgeSerializer(data=data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Validation error.",
                errors=serializer.errors,
                code=ErrorCode.VALIDATION_ERROR,
            )

        badge = serializer.save(is_system=False)
        return APIResponse.created(
            data=BadgeSerializer(badge).data,
            message="Badge created.",
        )


@extend_schema(tags=["Badges"])
class BadgeDetailView(APIView):
    permission_classes = []

    @extend_schema(
        summary="Retrieve a badge",
        responses={
            200: OpenApiResponse(description="Badge detail"),
            404: OpenApiResponse(description="Not found"),
        },
        auth=[],
    )
    def get(self, request, pk):
        try:
            badge = Badge.objects.get(id=pk)
        except Badge.DoesNotExist:
            return APIResponse.error(
                message="Badge not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        return APIResponse.success(data=BadgeSerializer(badge).data)


# ─────────────────────────────────────────────────────────────────────────────
# Assignment
# ─────────────────────────────────────────────────────────────────────────────


@extend_schema(tags=["Badges"])
class BadgeAssignView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    @extend_schema(
        summary="Assign a badge to a client",
        description=(
            "Manually assign a badge to a client. "
            "Client must have an active membership with the trainer/gym. "
            "Optionally posts to chatroom and sends push notification."
        ),
        responses={
            201: OpenApiResponse(description="Assignment created"),
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Client not in community"),
            404: OpenApiResponse(description="Badge or client not found"),
        },
    )
    def post(self, request, client_id):
        try:
            client = ClientProfile.objects.get(id=client_id)
        except ClientProfile.DoesNotExist:
            return APIResponse.error(
                message="Client not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        trainer, gym = _get_trainer_gym(request.user)

        if not _client_in_community(client, trainer=trainer, gym=gym):
            return APIResponse.error(
                message="This client is not in your community.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        badge_id = request.data.get("badge_id")
        try:
            badge = Badge.objects.get(id=badge_id)
        except Badge.DoesNotExist:
            return APIResponse.error(
                message="Badge not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        note = request.data.get("note", "")
        post_to_chatroom_flag = request.data.get("post_to_chatroom", True)

        assignment = BadgeAssignment.objects.create(
            badge=badge,
            client=client,
            trainer=trainer,
            gym=gym,
            assigned_by=request.user,
            note=note,
            post_to_chatroom=post_to_chatroom_flag,
        )

        if assignment.post_to_chatroom:
            post_badge_to_chatroom.delay(str(assignment.id))

        send_push_notification.delay(
            user_id=str(client.user_id),
            title="You earned a badge! 🏅",
            body=f"You just earned the {badge.name} badge!",
            data={
                "type": "badge_earned",
                "badge_id": str(badge.id),
                "assignment_id": str(assignment.id),
            },
        )

        return APIResponse.created(
            data=BadgeAssignmentSerializer(assignment).data,
            message="Badge assigned successfully.",
        )


@extend_schema(tags=["Badges"])
class ClientBadgeListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List a client's badges",
        description=(
            "Returns paginated badge assignments for a client. "
            "Client can view their own. "
            "Trainer/gym can view clients in their community."
        ),
        responses={
            200: OpenApiResponse(description="Paginated assignment list"),
            403: OpenApiResponse(description="Not permitted"),
            404: OpenApiResponse(description="Client not found"),
        },
    )
    def get(self, request, client_id):
        try:
            client = ClientProfile.objects.get(id=client_id)
        except ClientProfile.DoesNotExist:
            return APIResponse.error(
                message="Client not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        user = request.user
        if user.role == "client":
            try:
                own_profile = user.client_profile
            except ClientProfile.DoesNotExist:
                return APIResponse.error(
                    message="Client profile not found.",
                    code=ErrorCode.NOT_FOUND,
                    status_code=404,
                )
            if own_profile.id != client.id:
                return APIResponse.error(
                    message="You can only view your own badges.",
                    code=ErrorCode.PERMISSION_DENIED,
                    status_code=403,
                )
        elif user.role in ("trainer", "gym"):
            trainer, gym = _get_trainer_gym(user)
            if not _client_in_community(client, trainer=trainer, gym=gym):
                return APIResponse.error(
                    message="This client is not in your community.",
                    code=ErrorCode.PERMISSION_DENIED,
                    status_code=403,
                )
        else:
            return APIResponse.error(
                message="Permission denied.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        qs = BadgeAssignment.objects.filter(client=client).select_related(
            "badge", "client__user", "trainer", "assigned_by"
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = BadgeAssignmentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema(tags=["Badges"])
class BadgeAssignmentListView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    @extend_schema(
        summary="List badge assignments made by this trainer/gym",
        description="Returns paginated assignments ordered by -created_at.",
        responses={200: OpenApiResponse(description="Paginated assignment list")},
    )
    def get(self, request):
        trainer, gym = _get_trainer_gym(request.user)
        if trainer:
            qs = BadgeAssignment.objects.filter(trainer=trainer)
        else:
            qs = BadgeAssignment.objects.filter(gym=gym)

        qs = qs.select_related("badge", "client__user", "trainer", "assigned_by")

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = BadgeAssignmentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# Leaderboard
# ─────────────────────────────────────────────────────────────────────────────


@extend_schema(tags=["Badges"])
class BadgeLeaderboardView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    @extend_schema(
        summary="Leaderboard — most active clients this week",
        description=(
            "Top 10 clients ranked by completed sessions in the last 7 days. "
            "Trainer sees own community; gym sees across all gym trainers. "
            "Returns rank, client name, photo_url, sessions_this_week, "
            "total_badges_count."
        ),
        responses={200: OpenApiResponse(description="Leaderboard list (max 10)")},
    )
    def get(self, request):
        week_ago = timezone.now().date() - datetime.timedelta(days=7)
        trainer, gym = _get_trainer_gym(request.user)

        if trainer:
            session_qs = Session.objects.filter(trainer=trainer)
        else:
            session_qs = Session.objects.filter(trainer__gym=gym)

        top = (
            session_qs.filter(
                status=Session.Status.COMPLETED,
                session_date__gte=week_ago,
                deleted_at__isnull=True,
            )
            .values("client")
            .annotate(sessions_this_week=Count("id"))
            .order_by("-sessions_this_week")[:10]
        )

        results = []
        for rank, row in enumerate(top, start=1):
            try:
                client = ClientProfile.objects.get(id=row["client"])
            except ClientProfile.DoesNotExist:
                continue
            total_badges = BadgeAssignment.objects.filter(client=client).count()
            results.append(
                {
                    "rank": rank,
                    "client_id": str(client.id),
                    "client_name": client.display_name or client.username,
                    "photo_url": client.profile_photo_url,
                    "sessions_this_week": row["sessions_this_week"],
                    "total_badges_count": total_badges,
                }
            )

        return APIResponse.success(data=results)


# ─────────────────────────────────────────────────────────────────────────────
# Weekly recognition post
# ─────────────────────────────────────────────────────────────────────────────


@extend_schema(tags=["Badges"])
class WeeklyRecognitionPostView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    @extend_schema(
        summary="Post weekly recognition to chatroom",
        description=(
            "Assign 1–3 badges and post a single formatted recognition card "
            "to the trainer's/gym's chatroom. "
            "Each slot: client_id, badge_id, optional note."
        ),
        responses={
            201: OpenApiResponse(description="Assignments created + message posted"),
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Not trainer/gym"),
        },
    )
    def post(self, request):
        slots_data = request.data.get("slots", [])

        if not isinstance(slots_data, list) or len(slots_data) == 0:
            return APIResponse.error(
                message="Provide 1 to 3 slots.",
                code=ErrorCode.VALIDATION_ERROR,
            )
        if len(slots_data) > 3:
            return APIResponse.error(
                message="Maximum 3 slots allowed.",
                code=ErrorCode.VALIDATION_ERROR,
            )

        slot_serializers = [RecognitionSlotSerializer(data=s) for s in slots_data]
        for s in slot_serializers:
            if not s.is_valid():
                return APIResponse.error(
                    message="Validation error in slots.",
                    errors=s.errors,
                    code=ErrorCode.VALIDATION_ERROR,
                )

        validated_slots = [s.validated_data for s in slot_serializers]

        trainer, gym = _get_trainer_gym(request.user)

        # Validate clients and badges before creating anything
        resolved = []
        for slot in validated_slots:
            try:
                client = ClientProfile.objects.get(id=slot["client_id"])
            except ClientProfile.DoesNotExist:
                return APIResponse.error(
                    message=f"Client {slot['client_id']} not found.",
                    code=ErrorCode.NOT_FOUND,
                    status_code=404,
                )

            if not _client_in_community(client, trainer=trainer, gym=gym):
                return APIResponse.error(
                    message=f"Client {client.username} is not in your community.",
                    code=ErrorCode.VALIDATION_ERROR,
                )

            try:
                badge = Badge.objects.get(id=slot["badge_id"])
            except Badge.DoesNotExist:
                return APIResponse.error(
                    message=f"Badge {slot['badge_id']} not found.",
                    code=ErrorCode.NOT_FOUND,
                    status_code=404,
                )

            resolved.append(
                {"client": client, "badge": badge, "note": slot.get("note", "")}
            )

        # Get chatroom
        try:
            if trainer:
                chatroom = trainer.chatroom
            else:
                chatroom = gym.chatroom
        except Exception:
            chatroom = None

        assignments = []
        medals = ["🥇", "🥈", "🥉"]

        with transaction.atomic():
            for item in resolved:
                assignment = BadgeAssignment.objects.create(
                    badge=item["badge"],
                    client=item["client"],
                    trainer=trainer,
                    gym=gym,
                    assigned_by=request.user,
                    note=item["note"],
                    post_to_chatroom=False,
                )
                assignments.append(assignment)

            if chatroom:
                lines = ["🏆 TOP PERFORMERS THIS WEEK", "─────────────────────────"]
                for i, item in enumerate(resolved):
                    lines.append(
                        f"{medals[i]} @{item['client'].username} — {item['badge'].name}"
                    )
                    if item["note"]:
                        lines.append(f'   "{item["note"]}"')
                recogniser = request.user.display_name or request.user.username
                lines.append(f"Recognised by {recogniser}")
                content = "\n".join(lines)

                Message.objects.create(
                    chatroom=chatroom,
                    sender=request.user,
                    content=content,
                    message_type="announcement",
                    audience="full_group",
                )

        return APIResponse.created(
            data=BadgeAssignmentSerializer(assignments, many=True).data,
            message="Recognition posted successfully.",
        )
