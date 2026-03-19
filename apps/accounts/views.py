"""
Accounts views — authentication endpoints.
"""

import logging

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django_ratelimit.decorators import ratelimit
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
    send_password_reset_email,
    send_verification_email,
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

logger = logging.getLogger(__name__)


def _decode_uid(uid):
    """Decode a base64-encoded UID string. Returns the decoded string or None."""
    try:
        return force_str(urlsafe_base64_decode(uid))
    except Exception:
        return None


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

        try:
            send_verification_email(user)
        except Exception:
            logger.exception("Failed to send verification email to %s", user.email)

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

        try:
            send_welcome_email(user)
        except Exception:
            logger.exception("Failed to send welcome email to %s", user.email)

        return Response(
            {"message": "Email verified successfully. Welcome to Fit Trybe!"},
            status=status.HTTP_200_OK,
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

        return super().post(request, *args, **kwargs)


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
                send_password_reset_email(user)
            except User.DoesNotExist:
                pass
            except Exception:
                logger.exception("Failed to send password reset email to %s", email)

        return Response(
            {
                "message": (
                    "If this email exists, you will receive a password reset "
                    "link shortly."
                )
            },
            status=status.HTTP_200_OK,
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


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
