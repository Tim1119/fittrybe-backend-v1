"""
Clients app views.
"""

import logging

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import IsTrainerOrGym
from apps.clients.emails import send_client_reminder_email
from apps.clients.models import ClientMembership, InviteLink
from apps.clients.serializers import (
    ClientMembershipSerializer,
    InviteLinkSerializer,
    InvitePreviewSerializer,
)
from apps.clients.utils import get_managed_clients, user_owns_membership
from apps.core.error_codes import ErrorCode
from apps.core.pagination import StandardPagination
from apps.core.responses import APIResponse

logger = logging.getLogger(__name__)


def _block_gym_trainer(user):
    """
    Returns a 403 error response if user is a gym trainer.
    Gym trainers cannot manage clients — that belongs to the gym admin.
    Returns None if the user is allowed to proceed.
    """
    if user.role == "trainer":
        try:
            if user.trainer_profile.trainer_type == "gym_trainer":
                return APIResponse.error(
                    message=(
                        "Gym trainers cannot manage clients directly. "
                        "Client management is handled by the gym admin."
                    ),
                    code=ErrorCode.PERMISSION_DENIED,
                    status_code=403,
                )
        except Exception:
            pass
    return None


def _get_membership_or_403(pk, user):
    """
    Fetch a non-deleted ClientMembership by pk and verify ownership.
    Returns (membership, None) on success, (None, response) on failure.
    """
    try:
        membership = ClientMembership.objects.select_related(
            "client__user", "trainer", "gym"
        ).get(pk=pk)
    except ClientMembership.DoesNotExist:
        return None, APIResponse.error(
            message="Membership not found.",
            code=ErrorCode.NOT_FOUND,
            status_code=404,
        )

    if not user_owns_membership(membership, user):
        return None, APIResponse.error(
            message="You do not have permission to access this membership.",
            code=ErrorCode.PERMISSION_DENIED,
            status_code=403,
        )
    return membership, None


@extend_schema(
    summary="List managed clients",
    description=(
        "Returns a paginated list of all clients managed by the authenticated "
        "trainer or gym.\n\n"
        "Trainer → clients linked to their trainer profile.\n"
        "Gym → direct gym clients PLUS clients of trainers who belong to "
        "the gym.\n\n"
        "Optional filters: `?status=active|lapsed|pending|suspended`, "
        "`?trainer_id=<id>` (gym only)."
    ),
    parameters=[
        OpenApiParameter(
            name="status",
            location=OpenApiParameter.QUERY,
            description="Filter by membership status",
            required=False,
            type=str,
        ),
        OpenApiParameter(
            name="trainer_id",
            location=OpenApiParameter.QUERY,
            description="Filter by trainer profile id (gym admins only)",
            required=False,
            type=int,
        ),
    ],
    responses={
        200: OpenApiResponse(description="Paginated list of client memberships"),
        401: OpenApiResponse(description="Not authenticated"),
        403: OpenApiResponse(description="Not a trainer or gym"),
    },
    tags=["Clients"],
)
class ClientListView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    def get(self, request):
        qs = get_managed_clients(request.user)

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        trainer_id = request.query_params.get("trainer_id")
        if trainer_id and request.user.role == "gym":
            qs = qs.filter(trainer_id=trainer_id)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = ClientMembershipSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema(
    summary="Get, update, or remove a client membership",
    description=(
        "GET — retrieve the membership details.\n"
        "PUT — partially update status, renewal_date, payment_amount, "
        "payment_currency, payment_notes, or notes.\n"
        "DELETE — soft-delete the membership (sets deleted_at).\n\n"
        "Ownership enforced: trainers can only access their own clients; "
        "gym admins can access direct gym clients and clients of "
        "gym-affiliated trainers."
    ),
    request=ClientMembershipSerializer,
    responses={
        200: OpenApiResponse(description="Membership data"),
        204: OpenApiResponse(description="Deleted"),
        403: OpenApiResponse(description="Not your client"),
        404: OpenApiResponse(description="Membership not found"),
    },
    tags=["Clients"],
)
class ClientDetailView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    def get(self, request, pk):
        membership, err = _get_membership_or_403(pk, request.user)
        if err:
            return err
        serializer = ClientMembershipSerializer(membership)
        return APIResponse.success(data=serializer.data)

    def put(self, request, pk):
        err = _block_gym_trainer(request.user)
        if err:
            return err
        membership, err = _get_membership_or_403(pk, request.user)
        if err:
            return err
        serializer = ClientMembershipSerializer(
            membership, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return APIResponse.error(
                message="Invalid data.",
                errors=serializer.errors,
                code=ErrorCode.VALIDATION_ERROR,
                status_code=400,
            )
        serializer.save()
        return APIResponse.success(data=serializer.data, message="Membership updated.")

    def delete(self, request, pk):
        err = _block_gym_trainer(request.user)
        if err:
            return err
        membership, err = _get_membership_or_403(pk, request.user)
        if err:
            return err
        membership.delete()
        return APIResponse.no_content(message="Membership removed.")


@extend_schema(
    summary="Send a payment reminder to a client",
    description=(
        "Sends a reminder email to the client and records last_reminder_at. "
        "Ownership is enforced — trainers can only remind their own clients."
    ),
    request=None,
    responses={
        200: OpenApiResponse(description="Reminder sent"),
        403: OpenApiResponse(description="Not your client"),
        404: OpenApiResponse(description="Membership not found"),
    },
    tags=["Clients"],
)
class ClientReminderView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    def post(self, request, pk):
        err = _block_gym_trainer(request.user)
        if err:
            return err
        membership, err = _get_membership_or_403(pk, request.user)
        if err:
            return err

        owner_name = (
            membership.trainer.full_name
            if membership.trainer_id
            else membership.gym.gym_name
        )
        try:
            send_client_reminder_email(membership, owner_name)
        except Exception:
            logger.exception("Failed to send reminder email for membership %s", pk)

        membership.last_reminder_at = timezone.now()
        membership.save(update_fields=["last_reminder_at"])

        return APIResponse.success(message="Reminder sent successfully.")


@extend_schema(
    summary="Create an invite link or list existing ones",
    description=(
        "POST — create a new invite link for the authenticated trainer or gym. "
        "Accepts optional `expires_at` (ISO datetime) and `max_uses` (integer). "
        "Returns the invite with `web_url` and `deep_link`.\n\n"
        "GET — list all invite links owned by the authenticated user."
    ),
    request=inline_serializer(
        name="InviteCreateRequest",
        fields={
            "expires_at": drf_serializers.DateTimeField(
                required=False, allow_null=True
            ),
            "max_uses": drf_serializers.IntegerField(
                required=False, allow_null=True, min_value=1
            ),
        },
    ),
    responses={
        200: OpenApiResponse(description="List of invite links"),
        201: OpenApiResponse(description="Invite link created"),
        401: OpenApiResponse(description="Not authenticated"),
        403: OpenApiResponse(description="Not a trainer or gym"),
    },
    tags=["Clients"],
)
class InviteCreateListView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    def post(self, request):
        err = _block_gym_trainer(request.user)
        if err:
            return err

        expires_at = request.data.get("expires_at")
        max_uses = request.data.get("max_uses")

        kwargs = {}
        if expires_at:
            kwargs["expires_at"] = expires_at
        if max_uses is not None:
            kwargs["max_uses"] = max_uses

        if request.user.role == "trainer":
            try:
                profile = request.user.trainer_profile
            except Exception:
                return APIResponse.error(
                    message="Trainer profile not found.",
                    code=ErrorCode.NOT_FOUND,
                    status_code=404,
                )
            invite = InviteLink.objects.create(trainer=profile, **kwargs)
        else:
            try:
                profile = request.user.gym_profile
            except Exception:
                return APIResponse.error(
                    message="Gym profile not found.",
                    code=ErrorCode.NOT_FOUND,
                    status_code=404,
                )
            invite = InviteLink.objects.create(gym=profile, **kwargs)

        serializer = InviteLinkSerializer(invite)
        return APIResponse.created(
            data=serializer.data,
            message="Invite link created.",
        )

    def get(self, request):
        if request.user.role == "trainer":
            try:
                qs = InviteLink.objects.filter(
                    trainer=request.user.trainer_profile
                ).order_by("-created_at")
            except Exception:
                qs = InviteLink.objects.none()
        else:
            try:
                qs = InviteLink.objects.filter(gym=request.user.gym_profile).order_by(
                    "-created_at"
                )
            except Exception:
                qs = InviteLink.objects.none()

        serializer = InviteLinkSerializer(qs, many=True)
        return APIResponse.success(data=serializer.data)


@extend_schema(
    summary="Deactivate an invite link",
    description=(
        "Sets is_active=False on the invite link identified by token. "
        "Ownership is enforced — trainers can only deactivate their own links."
    ),
    request=None,
    responses={
        200: OpenApiResponse(description="Invite deactivated"),
        403: OpenApiResponse(description="Not your invite"),
        404: OpenApiResponse(description="Token not found"),
    },
    tags=["Clients"],
)
class InviteDeactivateView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    def delete(self, request, token):
        err = _block_gym_trainer(request.user)
        if err:
            return err

        try:
            invite = InviteLink.objects.get(token=token)
        except InviteLink.DoesNotExist:
            return APIResponse.error(
                message="Invite link not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        owns = False
        if request.user.role == "trainer":
            try:
                owns = invite.trainer_id == request.user.trainer_profile.id
            except Exception:
                pass
        elif request.user.role == "gym":
            try:
                owns = invite.gym_id == request.user.gym_profile.id
            except Exception:
                pass

        if not owns:
            return APIResponse.error(
                message=("You do not have permission to deactivate this invite."),
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        invite.is_active = False
        invite.save(update_fields=["is_active"])
        return APIResponse.success(message="Invite link deactivated.")


@extend_schema(
    summary="Preview an invite link (public)",
    description=(
        "Returns information about the trainer or gym behind this invite link "
        "so the client can decide before joining. No authentication required. "
        "`is_valid` indicates whether the link can still be accepted "
        "(not deactivated, not expired, not over max_uses)."
    ),
    request=None,
    responses={
        200: OpenApiResponse(description="Invite preview data"),
        404: OpenApiResponse(description="Token not found"),
    },
    tags=["Clients"],
    auth=[],
)
class InvitePreviewView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        try:
            invite = InviteLink.objects.select_related("trainer", "gym").get(
                token=token
            )
        except InviteLink.DoesNotExist:
            return APIResponse.error(
                message="Invite link not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        serializer = InvitePreviewSerializer(invite)
        return APIResponse.success(data=serializer.data)


@extend_schema(
    summary="Accept an invite link and join a community",
    description=(
        "Client-only endpoint. Validates the invite token, checks for "
        "duplicate memberships, creates a ClientMembership, and increments "
        "the invite's uses_count. Atomic.\n\n"
        "Returns 403 if the authenticated user is not a client.\n"
        "Returns 400 if the invite is invalid/expired/deactivated or "
        "the user is already a member."
    ),
    request=None,
    responses={
        201: OpenApiResponse(description="Joined — membership created"),
        400: OpenApiResponse(description="Invite invalid or already a member"),
        403: OpenApiResponse(description="Only clients can accept invites"),
        404: OpenApiResponse(description="Token not found"),
    },
    tags=["Clients"],
)
class InviteAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        if request.user.role != "client":
            return APIResponse.error(
                message="Only clients can accept invites.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        try:
            invite = InviteLink.objects.select_related("trainer", "gym").get(
                token=token
            )
        except InviteLink.DoesNotExist:
            return APIResponse.error(
                message="Invite link not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        valid, reason = invite.is_valid()
        if not valid:
            return APIResponse.error(
                message=reason,
                code=ErrorCode.VALIDATION_ERROR,
                status_code=400,
            )

        try:
            client_profile = request.user.client_profile
        except Exception:
            return APIResponse.error(
                message="Client profile not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        # Duplicate check
        if invite.trainer_id:
            duplicate = ClientMembership.all_objects.filter(
                client=client_profile,
                trainer=invite.trainer,
                deleted_at__isnull=True,
            ).exists()
        else:
            duplicate = ClientMembership.all_objects.filter(
                client=client_profile,
                gym=invite.gym,
                deleted_at__isnull=True,
            ).exists()

        if duplicate:
            return APIResponse.error(
                message="You are already a member of this community.",
                code=ErrorCode.ALREADY_EXISTS,
                status_code=400,
            )

        with transaction.atomic():
            membership = ClientMembership.objects.create(
                client=client_profile,
                trainer=invite.trainer,
                gym=invite.gym,
                status=ClientMembership.Status.PENDING,
            )
            invite.uses_count += 1
            invite.save(update_fields=["uses_count"])

        owner_name = (
            invite.trainer.full_name if invite.trainer_id else invite.gym.gym_name
        )
        serializer = ClientMembershipSerializer(membership)
        return APIResponse.created(
            data=serializer.data,
            message=f"You have joined {owner_name}'s community.",
        )
