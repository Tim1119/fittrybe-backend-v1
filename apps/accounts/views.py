"""
Accounts views — authentication endpoints.
"""

import logging

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django_ratelimit.decorators import ratelimit
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.emails import (
    account_token_generator,
    send_password_changed_email,
    send_welcome_email,
)
from apps.accounts.models import User
from apps.accounts.serializers import (
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    ForgotPasswordSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserProfileSerializer,
)
from apps.accounts.tasks import (
    send_password_reset_email_task,
    send_verification_email_task,
)
from apps.core.error_codes import ErrorCode
from apps.core.responses import APIResponse

logger = logging.getLogger(__name__)


def _decode_uid(uid):
    """Decode a base64-encoded UID string. Returns the decoded string or None."""
    try:
        return force_str(urlsafe_base64_decode(uid))
    except Exception:
        return None


def _get_subscription_data(user):
    if user.role == "client":
        return None
    try:
        sub = user.subscription
        return {
            "status": sub.status,
            "plan": sub.plan.plan,
            "is_trial": sub.is_trial_active(),
            "days_remaining": sub.days_remaining_in_trial(),
            "trial_ends_at": (
                sub.trial_end.isoformat() if sub.status == "trial" else None
            ),
            "current_period_end": (
                sub.current_period_end.isoformat() if sub.current_period_end else None
            ),
            "is_access_allowed": sub.is_access_allowed(),
        }
    except Exception:
        return None


@extend_schema(
    summary="Register a new user",
    description=(
        "Create a new trainer, gym, or client account. "
        "A verification email will be sent."
    ),
    request=RegisterSerializer,
    responses={
        201: OpenApiResponse(description="Registration successful"),
        400: OpenApiResponse(description="Validation error"),
    },
    tags=["Authentication"],
    auth=[],
)
@method_decorator(
    ratelimit(key="ip", rate="5/h", method="POST", block=True), name="post"
)
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()

        send_verification_email_task.delay(str(user.id))

        return Response(
            {
                "message": (
                    "Registration successful. Please check your email to verify "
                    "your account."
                ),
                "email": user.email,
                "role": user.role,
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    summary="Verify email address",
    description=(
        "Verify a user's email using the uid and token from the verification email."
    ),
    responses={
        200: OpenApiResponse(description="Email verified successfully"),
        400: OpenApiResponse(description="Invalid or expired token"),
    },
    tags=["Authentication"],
    auth=[],
)
class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        uid_param = request.query_params.get("uid", "")
        token = request.query_params.get("token", "")

        uid = _decode_uid(uid_param)
        if uid is None:
            return Response(
                {"error": "Invalid verification link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, Exception):
            return Response(
                {"error": "Invalid verification link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not account_token_generator.check_token(user, token):
            return Response(
                {"error": "Verification link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_active = True
        user.is_email_verified = True
        user.save(update_fields=["is_active", "is_email_verified"])

        if user.role in ("trainer", "gym"):
            try:
                from apps.subscriptions.utils import create_trial_subscription

                create_trial_subscription(user)
            except Exception:
                logger.exception(
                    "Failed to create trial subscription for %s", user.email
                )

        try:
            send_welcome_email(user)
        except Exception:
            logger.exception("Failed to send welcome email to %s", user.email)

        return Response(
            {"message": "Email verified successfully. Welcome to Fit Trybe!"},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    summary="Login",
    description=(
        "Authenticate with email and password. Returns JWT access and refresh tokens."
    ),
    request=CustomTokenObtainPairSerializer,
    responses={
        200: OpenApiResponse(description="Login successful with tokens"),
        400: OpenApiResponse(description="Invalid credentials"),
        403: OpenApiResponse(description="Account not verified"),
    },
    tags=["Authentication"],
    auth=[],
)
@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="post"
)
class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        # Pre-check: if the user exists but hasn't verified email, return 403
        # before JWT auth so the unverified message is always shown.
        email = request.data.get("email", "").strip().lower()
        try:
            user = User.objects.get(email=email)
            if not user.is_email_verified:
                return Response(
                    {
                        "error": (
                            "Please verify your email before logging in. "
                            "Check your inbox for the verification link."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        except User.DoesNotExist:
            pass

        response = super().post(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return response

            return APIResponse.success(
                data={
                    "access": response.data.get("access"),
                    "refresh": response.data.get("refresh"),
                    "email": user.email,
                    "role": user.role,
                    "subscription": _get_subscription_data(user),
                },
                message="Login successful.",
            )

        return response


@extend_schema(
    summary="Logout",
    description="Blacklist the refresh token to log out.",
    request=inline_serializer(
        name="LogoutRequest", fields={"refresh": drf_serializers.CharField()}
    ),
    responses={
        200: OpenApiResponse(description="Logged out successfully"),
        400: OpenApiResponse(description="Invalid token"),
    },
    tags=["Authentication"],
)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {"error": "Token is invalid or expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {"message": "Logged out successfully."}, status=status.HTTP_200_OK
        )


@extend_schema(
    summary="Forgot password",
    description=(
        "Send a password reset email. Always returns 200 to prevent email enumeration."
    ),
    request=ForgotPasswordSerializer,
    responses={
        200: OpenApiResponse(description="Reset email sent if account exists"),
    },
    tags=["Authentication"],
    auth=[],
)
@method_decorator(
    ratelimit(key="ip", rate="3/h", method="POST", block=True), name="post"
)
class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            try:
                user = User.objects.get(email=email)
                send_password_reset_email_task.delay(str(user.id))
            except User.DoesNotExist:
                pass

        return Response(
            {
                "message": (
                    "If this email exists, you will receive a password reset "
                    "link shortly."
                )
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    summary="Reset password",
    description="Reset password using uid and token from the reset email.",
    request=ResetPasswordSerializer,
    responses={
        200: OpenApiResponse(description="Password reset successful"),
        400: OpenApiResponse(description="Invalid or expired token"),
    },
    tags=["Authentication"],
    auth=[],
)
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        uid = _decode_uid(serializer.validated_data["uid"])
        token = serializer.validated_data["token"]

        if uid is None:
            return Response(
                {"error": "Invalid reset link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, Exception):
            return Response(
                {"error": "Invalid reset link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not PasswordResetTokenGenerator().check_token(user, token):
            return Response(
                {"error": "Reset link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        try:
            send_password_changed_email(user)
        except Exception:
            logger.exception("Failed to send password-changed email to %s", user.email)

        return Response(
            {
                "message": (
                    "Password reset successfully. You can now log in with your "
                    "new password."
                )
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    summary="Change password",
    description="Change password for authenticated user.",
    request=ChangePasswordSerializer,
    responses={
        200: OpenApiResponse(description="Password changed successfully"),
        400: OpenApiResponse(description="Invalid old password"),
    },
    tags=["Authentication"],
)
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        serializer = ChangePasswordSerializer(data=request.data)

        if not user.check_password(request.data.get("old_password", "")):
            return Response(
                {"error": "Old password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        try:
            send_password_changed_email(user)
        except Exception:
            logger.exception("Failed to send password-changed email to %s", user.email)

        return Response(
            {"message": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    summary="Get current user",
    description="Returns the authenticated user's profile.",
    responses={
        200: UserProfileSerializer,
    },
    tags=["Authentication"],
)
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return APIResponse.success(
            data={
                **serializer.data,
                "subscription": _get_subscription_data(request.user),
            },
            message="Profile retrieved successfully.",
        )
