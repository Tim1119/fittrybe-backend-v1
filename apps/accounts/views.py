"""
Accounts views — authentication endpoints.
"""

import logging

from axes.handlers.proxy import AxesProxyHandler
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django_ratelimit.decorators import ratelimit
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView as _TokenRefreshView

from apps.accounts.emails import (
    account_token_generator,
    send_password_changed_email,
    send_welcome_email,
)
from apps.accounts.models import User
from apps.accounts.serializers import (
    ChangePasswordSerializer,
    ClientRegisterSerializer,
    CustomTokenObtainPairSerializer,
    ForgotPasswordSerializer,
    GymRegisterSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    TrainerRegisterSerializer,
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


def _get_onboarding_data(user, is_first_login):
    wizard_step = 0
    profile_completion = 0

    try:
        if user.role == "trainer":
            profile = user.trainer_profile
            wizard_step = profile.wizard_step
            profile_completion = profile.profile_completion_percentage
        elif user.role == "gym":
            profile = user.gym_profile
            wizard_step = profile.wizard_step
            profile_completion = profile.profile_completion_percentage
    except Exception:
        pass

    return {
        "status": user.onboarding_status,
        "is_completed": user.onboarding_status == user.OnboardingStatus.COMPLETED,
        "is_first_login": is_first_login,
        "wizard_step": wizard_step,
        "profile_completion_percentage": profile_completion,
    }


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


_ROLE_SERIALIZER_MAP = {
    "trainer": TrainerRegisterSerializer,
    "gym": GymRegisterSerializer,
    "client": ClientRegisterSerializer,
}


@extend_schema(
    summary="Register a new user",
    description=(
        "Create a new trainer, gym, or client account. "
        "Sends a verification email upon success. "
        "Rate limited to 5 registrations per hour per IP.\n\n"
        "**Role: `trainer`** — required fields: "
        "`email`, `password`, `confirm_password`, `display_name`, "
        "`full_name`, `terms_accepted`; "
        "optional: `phone_number`.\n\n"
        "**Role: `gym`** — required fields: "
        "`email`, `password`, `confirm_password`, `gym_name`, "
        "`admin_full_name`, `terms_accepted`; "
        "optional: `phone_number`, `city`.\n\n"
        "**Role: `client`** — required fields: "
        "`email`, `password`, `confirm_password`, `display_name`, "
        "`terms_accepted`."
    ),
    request=inline_serializer(
        name="RegisterRequest",
        fields={
            "email": drf_serializers.EmailField(),
            "password": drf_serializers.CharField(),
            "confirm_password": drf_serializers.CharField(),
            "role": drf_serializers.ChoiceField(choices=User.Role.choices),
            "display_name": drf_serializers.CharField(
                required=False,
                help_text="Trainer and client: public display name",
            ),
            "full_name": drf_serializers.CharField(
                required=False,
                help_text="Trainer only: full legal name used on profile",
            ),
            "gym_name": drf_serializers.CharField(
                required=False, help_text="Gym only: official gym name"
            ),
            "admin_full_name": drf_serializers.CharField(
                required=False, help_text="Gym only: full name of the admin"
            ),
            "phone_number": drf_serializers.CharField(
                required=False, help_text="Trainer / gym: contact phone"
            ),
            "city": drf_serializers.CharField(
                required=False, help_text="Gym only: city of operation"
            ),
            "terms_accepted": drf_serializers.BooleanField(
                help_text="Must be true — user accepts the terms of service"
            ),
        },
    ),
    responses={
        201: OpenApiResponse(
            description="Registration successful — verification email sent"
        ),
        400: OpenApiResponse(
            description="Validation error — invalid data, duplicate email, "
            "weak password, missing role-specific field, or terms not accepted"
        ),
        429: OpenApiResponse(description="Rate limit exceeded"),
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
        role = request.data.get("role", "")
        serializer_class = _ROLE_SERIALIZER_MAP.get(role, RegisterSerializer)
        serializer = serializer_class(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Registration failed.",
                errors=serializer.errors,
                code=ErrorCode.VALIDATION_ERROR,
                status_code=400,
            )

        user = serializer.save()

        send_verification_email_task.delay(str(user.id))

        return APIResponse.created(
            data={"email": user.email, "role": user.role},
            message=(
                "Registration successful. Please check your email to verify "
                "your account."
            ),
        )


@extend_schema(
    summary="Verify email address",
    description=(
        "Confirm ownership of an email address using the uid and token "
        "included in the verification link sent after registration. "
        "Activates the account and starts the subscription trial for trainers and gyms."
    ),
    parameters=[
        OpenApiParameter(
            name="uid",
            location=OpenApiParameter.QUERY,
            description="Base64-encoded user ID from the verification email",
            required=True,
            type=str,
        ),
        OpenApiParameter(
            name="token",
            location=OpenApiParameter.QUERY,
            description="Verification token from the email link",
            required=True,
            type=str,
        ),
    ],
    responses={
        200: OpenApiResponse(description="Email verified — account activated"),
        400: OpenApiResponse(description="Invalid uid, unknown user, or expired token"),
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
            return APIResponse.error(
                message="Invalid verification link.",
                code=ErrorCode.TOKEN_INVALID,
                status_code=400,
            )

        try:
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, Exception):
            return APIResponse.error(
                message="Invalid verification link.",
                code=ErrorCode.TOKEN_INVALID,
                status_code=400,
            )

        if not account_token_generator.check_token(user, token):
            return APIResponse.error(
                message="Verification link is invalid or has expired.",
                code=ErrorCode.TOKEN_INVALID,
                status_code=400,
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

        return APIResponse.success(
            message="Email verified successfully. Welcome to Fit Trybe!"
        )


@extend_schema(
    summary="Login",
    description=(
        "Authenticate with email and password. Returns JWT access and refresh tokens "
        "alongside the user's role, subscription status, and onboarding state. "
        "Sets is_first_login=False after the first successful login. "
        "Rate limited to 10 requests per minute per IP."
    ),
    request=CustomTokenObtainPairSerializer,
    responses={
        200: OpenApiResponse(
            description="Login successful — access/refresh tokens and user context"
        ),
        401: OpenApiResponse(description="Invalid email or password"),
        403: OpenApiResponse(
            description="Email not verified — check inbox for verification link"
        ),
        429: OpenApiResponse(description="Rate limit exceeded"),
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
        email = request.data.get("email", "").strip().lower()

        # Pre-check lockout before attempting authentication so that axes
        # cannot be bypassed by SimpleJWT raising AuthenticationFailed first.
        if AxesProxyHandler.is_locked(request, credentials={"username": email}):
            return APIResponse.error(
                message=("Too many failed login attempts. " "Try again in 15 minutes."),
                code=ErrorCode.ACCOUNT_LOCKED,
                status_code=429,
            )

        # Pre-check: if the user exists but hasn't verified email, return 403
        # before JWT auth so the unverified message is always shown.
        try:
            user = User.objects.get(email=email)
            if not user.is_email_verified:
                return APIResponse.error(
                    message=(
                        "Please verify your email before logging in. "
                        "Check your inbox for the verification link."
                    ),
                    code=ErrorCode.ACCOUNT_NOT_VERIFIED,
                    status_code=403,
                )
        except User.DoesNotExist:
            pass

        response = super().post(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return APIResponse.error(
                    message="Invalid email or password.",
                    code=ErrorCode.INVALID_CREDENTIALS,
                    status_code=401,
                )

            is_first = user.is_first_login
            if is_first:
                user.is_first_login = False
                user.save(update_fields=["is_first_login"])

            return APIResponse.success(
                data={
                    "access": response.data.get("access"),
                    "refresh": response.data.get("refresh"),
                    "email": user.email,
                    "role": user.role,
                    "subscription": _get_subscription_data(user),
                    "onboarding": _get_onboarding_data(user, is_first),
                },
                message="Login successful.",
            )

        return APIResponse.error(
            message="Invalid email or password.",
            code=ErrorCode.INVALID_CREDENTIALS,
            status_code=response.status_code,
        )


@extend_schema(
    summary="Logout",
    description=(
        "Blacklist the provided refresh token, invalidating the session. "
        "The client should also discard the access token locally. "
        "Requires a valid Bearer access token in the Authorization header."
    ),
    request=inline_serializer(
        name="LogoutRequest", fields={"refresh": drf_serializers.CharField()}
    ),
    responses={
        200: OpenApiResponse(description="Logged out successfully"),
        400: OpenApiResponse(
            description="Refresh token missing or already invalidated"
        ),
        401: OpenApiResponse(description="Access token missing or expired"),
    },
    tags=["Authentication"],
)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return APIResponse.error(
                message="Refresh token is required.",
                code=ErrorCode.VALIDATION_ERROR,
                status_code=400,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return APIResponse.error(
                message="Token is invalid or expired.",
                code=ErrorCode.TOKEN_INVALID,
                status_code=400,
            )
        return APIResponse.success(message="Logged out successfully.")


@extend_schema(
    summary="Forgot password",
    description=(
        "Request a password reset link by email. "
        "Always returns 200 regardless of whether the email exists, "
        "to prevent account enumeration attacks. "
        "Rate limited to 3 requests per hour per IP."
    ),
    request=ForgotPasswordSerializer,
    responses={
        200: OpenApiResponse(
            description="Request accepted — reset email sent if the account exists"
        ),
        429: OpenApiResponse(description="Rate limit exceeded"),
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

        return APIResponse.success(
            message=(
                "If this email exists, you will receive a password reset "
                "link shortly."
            )
        )


@extend_schema(
    summary="Reset password",
    description=(
        "Set a new password using the uid and token from the password reset email. "
        "The token is single-use and expires after a short window. "
        "Sends a confirmation email on success."
    ),
    request=ResetPasswordSerializer,
    responses={
        200: OpenApiResponse(
            description="Password reset — user may now log in with new password"
        ),
        400: OpenApiResponse(
            description="Invalid uid, unknown user, expired token, or weak password"
        ),
    },
    tags=["Authentication"],
    auth=[],
)
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Password reset failed.",
                errors=serializer.errors,
                code=ErrorCode.VALIDATION_ERROR,
                status_code=400,
            )

        uid = _decode_uid(serializer.validated_data["uid"])
        token = serializer.validated_data["token"]

        if uid is None:
            return APIResponse.error(
                message="Invalid reset link.",
                code=ErrorCode.TOKEN_INVALID,
                status_code=400,
            )

        try:
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, Exception):
            return APIResponse.error(
                message="Invalid reset link.",
                code=ErrorCode.TOKEN_INVALID,
                status_code=400,
            )

        if not PasswordResetTokenGenerator().check_token(user, token):
            return APIResponse.error(
                message="Reset link is invalid or has expired.",
                code=ErrorCode.TOKEN_INVALID,
                status_code=400,
            )

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        try:
            send_password_changed_email(user)
        except Exception:
            logger.exception("Failed to send password-changed email to %s", user.email)

        return APIResponse.success(
            message=(
                "Password reset successfully. You can now log in with your "
                "new password."
            )
        )


@extend_schema(
    summary="Change password",
    description=(
        "Change the password for the currently authenticated user. "
        "Requires the correct current password. "
        "Sends a security notification email after a successful change."
    ),
    request=ChangePasswordSerializer,
    responses={
        200: OpenApiResponse(description="Password changed successfully"),
        400: OpenApiResponse(
            description="Current password incorrect or new password too weak"
        ),
        401: OpenApiResponse(description="Not authenticated"),
    },
    tags=["Authentication"],
)
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        serializer = ChangePasswordSerializer(data=request.data)

        if not user.check_password(request.data.get("old_password", "")):
            return APIResponse.error(
                message="Old password is incorrect.",
                code=ErrorCode.VALIDATION_ERROR,
                status_code=400,
            )

        if not serializer.is_valid():
            return APIResponse.error(
                message="Password change failed.",
                errors=serializer.errors,
                code=ErrorCode.VALIDATION_ERROR,
                status_code=400,
            )

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        try:
            send_password_changed_email(user)
        except Exception:
            logger.exception("Failed to send password-changed email to %s", user.email)

        return APIResponse.success(message="Password changed successfully.")


@extend_schema(
    summary="Get current user profile",
    description=(
        "Returns the full profile of the currently authenticated user, "
        "including role, email verification status, subscription state, "
        "and onboarding progress."
    ),
    responses={
        200: OpenApiResponse(
            description="User profile with subscription and onboarding data"
        ),
        401: OpenApiResponse(description="Not authenticated"),
    },
    tags=["Authentication"],
)
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = UserProfileSerializer(user)
        return APIResponse.success(
            data={
                **serializer.data,
                "subscription": _get_subscription_data(user),
                "onboarding": _get_onboarding_data(user, user.is_first_login),
            },
            message="Profile retrieved successfully.",
        )


@extend_schema(
    summary="Complete onboarding",
    description=(
        "Mark the current user's onboarding as completed. "
        "Idempotent — safe to call if already completed."
    ),
    request=None,
    responses={
        200: OpenApiResponse(description="Onboarding marked as completed"),
        401: OpenApiResponse(description="Not authenticated"),
    },
    tags=["Authentication"],
)
class CompleteOnboardingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.complete_onboarding()
        return APIResponse.success(message="Onboarding completed.")


@extend_schema(
    summary="Refresh access token",
    description=(
        "Exchange a valid refresh token for a new access token. "
        "If ROTATE_REFRESH_TOKENS is enabled a new refresh token is also returned "
        "and the old one is blacklisted."
    ),
    tags=["Authentication"],
    auth=[],
)
class TokenRefreshView(_TokenRefreshView):
    pass
