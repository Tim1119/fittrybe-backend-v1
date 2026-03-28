"""
Notifications REST views.
"""

from django.utils.timezone import now
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.error_codes import ErrorCode
from apps.core.pagination import StandardPagination
from apps.core.responses import APIResponse

from .models import FCMDevice, Notification
from .serializers import FCMDeviceSerializer, NotificationSerializer

# ─────────────────────────────────────────────────────────────────────────────
# FCM Device
# ─────────────────────────────────────────────────────────────────────────────


@extend_schema(
    summary="Register FCM device token",
    description=(
        "Register a device token for push notifications. "
        "Re-registering an existing token reactivates it. "
        "Call this on app launch and after token refresh. "
        "Supported platforms: android, ios, web."
    ),
    request=FCMDeviceSerializer,
    responses={
        200: OpenApiResponse(description="Device registered."),
        400: OpenApiResponse(
            description="Validation error — missing token or invalid platform."
        ),
        401: OpenApiResponse(description="Authentication required."),
    },
    tags=["Notifications"],
)
class FCMDeviceRegisterView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FCMDeviceSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Invalid device data.",
                errors=serializer.errors,
                code=ErrorCode.VALIDATION_ERROR,
            )

        token = serializer.validated_data["token"]
        platform = serializer.validated_data["platform"]

        FCMDevice.objects.update_or_create(
            user=request.user,
            token=token,
            defaults={
                "platform": platform,
                "is_active": True,
                "last_used_at": now(),
                "deleted_at": None,
            },
        )

        return APIResponse.success(message="Device registered.")


@extend_schema(
    summary="Unregister FCM device token",
    description=(
        "Soft-deactivate a device token so it no longer receives push notifications. "
        "Call this on logout. The token is matched to the authenticated user only."
    ),
    responses={
        200: OpenApiResponse(description="Device unregistered."),
        401: OpenApiResponse(description="Authentication required."),
        404: OpenApiResponse(description="Token not found for this user."),
    },
    tags=["Notifications"],
)
class FCMDeviceUnregisterView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, token):
        updated = FCMDevice.objects.filter(user=request.user, token=token).update(
            is_active=False
        )
        if not updated:
            return APIResponse.error(
                message="Device token not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        return APIResponse.success(message="Device unregistered.")


# ─────────────────────────────────────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────────────────────────────────────


@extend_schema(
    summary="List in-app notifications",
    description=(
        "Returns paginated notifications for the authenticated user, "
        "ordered by most recent first. "
        "Includes unread_count in response meta."
    ),
    responses={
        200: OpenApiResponse(description="Paginated notification list."),
        401: OpenApiResponse(description="Authentication required."),
    },
    tags=["Notifications"],
)
class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(
            recipient=request.user, deleted_at__isnull=True
        ).select_related("sender")

        unread_count = qs.filter(is_read=False).count()

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = NotificationSerializer(page, many=True)
        response = paginator.get_paginated_response(serializer.data)
        # Inject unread_count into meta
        response.data.setdefault("meta", {})["unread_count"] = unread_count
        return response


@extend_schema(
    summary="Mark a notification as read",
    description=(
        "Marks a single notification as read and records the read timestamp. "
        "Returns 404 if the notification does not belong to the authenticated user."
    ),
    responses={
        200: OpenApiResponse(description="Notification marked as read."),
        401: OpenApiResponse(description="Authentication required."),
        404: OpenApiResponse(description="Notification not found."),
    },
    tags=["Notifications"],
)
class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            notif = Notification.objects.get(
                pk=pk, recipient=request.user, deleted_at__isnull=True
            )
        except Notification.DoesNotExist:
            return APIResponse.error(
                message="Notification not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        if not notif.is_read:
            notif.is_read = True
            notif.read_at = now()
            notif.save(update_fields=["is_read", "read_at"])

        return APIResponse.success(message="Notification marked as read.")


@extend_schema(
    summary="Mark all notifications as read",
    description=(
        "Bulk-marks all unread notifications for the authenticated user as read. "
        "Returns the count of notifications that were updated."
    ),
    responses={
        200: OpenApiResponse(description="All notifications marked as read."),
        401: OpenApiResponse(description="Authentication required."),
    },
    tags=["Notifications"],
)
class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        marked_count = Notification.objects.filter(
            recipient=request.user, is_read=False, deleted_at__isnull=True
        ).update(is_read=True, read_at=now())

        return APIResponse.success(
            data={"marked_count": marked_count},
            message=f"{marked_count} notification(s) marked as read.",
        )


@extend_schema(
    summary="Get unread notification count",
    description=(
        "Returns the number of unread notifications for the authenticated user. "
        "Lightweight endpoint suitable for badge polling."
    ),
    responses={
        200: OpenApiResponse(description="Unread count returned."),
        401: OpenApiResponse(description="Authentication required."),
    },
    tags=["Notifications"],
)
class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            recipient=request.user, is_read=False, deleted_at__isnull=True
        ).count()
        return APIResponse.success(data={"unread_count": count})
