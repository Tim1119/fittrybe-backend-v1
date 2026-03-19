"""
Email utilities for the accounts app.
All emails send both a plain-text fallback and an HTML version
using EmailMultiAlternatives.
"""

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


class AccountTokenGenerator(PasswordResetTokenGenerator):
    """Token generator tied to email-verification status."""

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{timestamp}{user.is_email_verified}"


account_token_generator = AccountTokenGenerator()


def get_user_name(user):
    """Return the local part of the user's email as a display name."""
    return user.email.split("@")[0]


def _logo_url():
    return f"{settings.FRONTEND_URL}/static/accounts/images/logo.png"


def send_verification_email(user):
    token = account_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    verification_url = f"{settings.FRONTEND_URL}/verify-email/?uid={uid}&token={token}"
    context = {
        "user_name": get_user_name(user),
        "user_role": user.role,
        "verification_url": verification_url,
        "logo_url": _logo_url(),
    }
    html_content = render_to_string("accounts/emails/verify_email.html", context)
    text_content = (
        f"Hi {get_user_name(user)},\n\n"
        f"Verify your Fit Trybe account:\n{verification_url}\n\n"
        f"This link expires in 24 hours."
    )
    email = EmailMultiAlternatives(
        subject="Verify your Fit Trybe account",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)


def send_password_reset_email(user):
    token = PasswordResetTokenGenerator().make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    reset_url = f"{settings.FRONTEND_URL}/reset-password/?uid={uid}&token={token}"
    context = {
        "user_email": user.email,
        "reset_url": reset_url,
        "logo_url": _logo_url(),
    }
    html_content = render_to_string("accounts/emails/password_reset.html", context)
    text_content = (
        f"Reset your Fit Trybe password:\n{reset_url}\n\n"
        f"This link expires in 1 hour."
    )
    email = EmailMultiAlternatives(
        subject="Reset your Fit Trybe password",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)


def send_welcome_email(user):
    context = {
        "user_name": get_user_name(user),
        "user_role": user.role,
        "frontend_url": settings.FRONTEND_URL,
        "logo_url": _logo_url(),
    }
    html_content = render_to_string("accounts/emails/welcome.html", context)
    text_content = (
        f"Welcome to Fit Trybe, {get_user_name(user)}!\n\n"
        f"Your account is now active. Visit: {settings.FRONTEND_URL}"
    )
    email = EmailMultiAlternatives(
        subject="Welcome to Fit Trybe! 🎉",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)


def send_account_locked_email(user):
    token = PasswordResetTokenGenerator().make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    reset_url = f"{settings.FRONTEND_URL}/reset-password/?uid={uid}&token={token}"
    context = {
        "user_email": user.email,
        "reset_url": reset_url,
        "logo_url": _logo_url(),
    }
    html_content = render_to_string("accounts/emails/account_locked.html", context)
    text_content = (
        f"Your Fit Trybe account has been temporarily locked "
        f"after 3 failed login attempts.\n\n"
        f"It will unlock in 15 minutes.\n\n"
        f"Reset password: {reset_url}"
    )
    email = EmailMultiAlternatives(
        subject="Fit Trybe: Account Temporarily Locked",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)


def send_password_changed_email(user):
    token = PasswordResetTokenGenerator().make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    reset_url = f"{settings.FRONTEND_URL}/reset-password/?uid={uid}&token={token}"
    context = {
        "user_email": user.email,
        "reset_url": reset_url,
        "changed_at": timezone.now().strftime("%B %d, %Y at %H:%M UTC"),
        "logo_url": _logo_url(),
    }
    html_content = render_to_string("accounts/emails/password_changed.html", context)
    text_content = (
        f"Your Fit Trybe password was changed.\n\n"
        f"If this was not you, reset immediately: {reset_url}"
    )
    email = EmailMultiAlternatives(
        subject="Fit Trybe: Password Changed Successfully",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)
