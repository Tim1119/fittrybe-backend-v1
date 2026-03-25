"""
Email utilities for the accounts app.
All emails send both a plain-text fallback and an HTML version
using EmailMultiAlternatives.

Every email that contains an action link exposes both a web URL
(FRONTEND_URL) and a mobile deep link (MOBILE_URL) so Flutter and
React clients can both be targeted in the same email.
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


def _mobile_url():
    return getattr(settings, "MOBILE_URL", "fittrybe://")


def send_verification_email(user):
    token = account_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    web_url = f"{settings.FRONTEND_URL}/verify-email/?uid={uid}&token={token}"
    mobile_url = f"{_mobile_url()}verify-email?uid={uid}&token={token}"
    context = {
        "user": user,
        "user_name": get_user_name(user),
        "user_role": user.role,
        "web_url": web_url,
        "mobile_url": mobile_url,
        "frontend_url": settings.FRONTEND_URL,
        "logo_url": _logo_url(),
        # legacy — kept so existing template refs still render
        "verification_url": web_url,
    }
    html_content = render_to_string("accounts/emails/verify_email.html", context)
    text_content = (
        f"Hi {get_user_name(user)},\n\n"
        f"Verify your Fit Trybe account:\n"
        f"  In browser: {web_url}\n"
        f"  In app:     {mobile_url}\n\n"
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
    web_url = f"{settings.FRONTEND_URL}/reset-password/?uid={uid}&token={token}"
    mobile_url = f"{_mobile_url()}reset-password?uid={uid}&token={token}"
    context = {
        "user": user,
        "user_email": user.email,
        "web_url": web_url,
        "mobile_url": mobile_url,
        "frontend_url": settings.FRONTEND_URL,
        "logo_url": _logo_url(),
        # legacy
        "reset_url": web_url,
    }
    html_content = render_to_string("accounts/emails/password_reset.html", context)
    text_content = (
        f"Reset your Fit Trybe password:\n"
        f"  In browser: {web_url}\n"
        f"  In app:     {mobile_url}\n\n"
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
    mobile_url = _mobile_url()
    context = {
        "user": user,
        "user_name": get_user_name(user),
        "user_role": user.role,
        "web_url": settings.FRONTEND_URL,
        "mobile_url": f"{mobile_url}dashboard",
        "frontend_url": settings.FRONTEND_URL,
        "logo_url": _logo_url(),
    }
    html_content = render_to_string("accounts/emails/welcome.html", context)
    text_content = (
        f"Welcome to Fit Trybe, {get_user_name(user)}!\n\n"
        f"Your account is now active.\n"
        f"  Web: {settings.FRONTEND_URL}\n"
        f"  App: {mobile_url}dashboard"
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
    web_url = f"{settings.FRONTEND_URL}/reset-password/?uid={uid}&token={token}"
    mobile_url = f"{_mobile_url()}reset-password?uid={uid}&token={token}"
    context = {
        "user": user,
        "user_email": user.email,
        "web_url": web_url,
        "mobile_url": mobile_url,
        "frontend_url": settings.FRONTEND_URL,
        "logo_url": _logo_url(),
        # legacy
        "reset_url": web_url,
    }
    html_content = render_to_string("accounts/emails/account_locked.html", context)
    text_content = (
        f"Your Fit Trybe account has been temporarily locked "
        f"after 3 failed login attempts.\n\n"
        f"It will unlock in 15 minutes.\n\n"
        f"Reset password:\n"
        f"  In browser: {web_url}\n"
        f"  In app:     {mobile_url}"
    )
    email = EmailMultiAlternatives(
        subject="Fit Trybe: Account Temporarily Locked",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)


def send_subscription_activated_email(user, subscription):
    mobile_url = _mobile_url()
    context = {
        "user": user,
        "user_name": get_user_name(user),
        "user_email": user.email,
        "plan_name": subscription.plan.display_name,
        "current_period_end": subscription.current_period_end,
        "web_url": f"{settings.FRONTEND_URL}/dashboard/",
        "mobile_url": f"{mobile_url}dashboard",
        "frontend_url": settings.FRONTEND_URL,
        "logo_url": _logo_url(),
    }
    html_content = render_to_string(
        "subscriptions/emails/subscription_activated.html", context
    )
    text_content = (
        f"Hi {get_user_name(user)},\n\n"
        f"Your Fit Trybe {subscription.plan.display_name} subscription is now active."
        f"\n\n"
        f"You have full access to all features.\n"
        f"  Web: {settings.FRONTEND_URL}/dashboard/\n"
        f"  App: {mobile_url}dashboard"
    )
    email = EmailMultiAlternatives(
        subject="Your Fit Trybe subscription is now active",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)


def send_subscription_locked_email(user):
    web_url = f"{settings.FRONTEND_URL}/subscription/upgrade/"
    mobile_url = f"{_mobile_url()}subscription/upgrade"
    context = {
        "user": user,
        "user_name": get_user_name(user),
        "user_email": user.email,
        "web_url": web_url,
        "mobile_url": mobile_url,
        "frontend_url": settings.FRONTEND_URL,
        "logo_url": _logo_url(),
    }
    html_content = render_to_string("accounts/emails/subscription_locked.html", context)
    text_content = (
        f"Hi {get_user_name(user)},\n\n"
        f"Your Fit Trybe subscription has expired "
        f"and your account has been locked.\n\n"
        f"Renew your subscription to restore access:\n"
        f"  In browser: {web_url}\n"
        f"  In app:     {mobile_url}"
    )
    email = EmailMultiAlternatives(
        subject="Your Fit Trybe subscription has expired",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)


def send_payment_retry_email(user, retry_count, next_retry_at):
    web_url = f"{settings.FRONTEND_URL}/subscription/upgrade/"
    mobile_url = f"{_mobile_url()}subscription/upgrade"
    context = {
        "user": user,
        "user_name": get_user_name(user),
        "user_email": user.email,
        "retry_count": retry_count,
        "next_retry_at": next_retry_at,
        "web_url": web_url,
        "mobile_url": mobile_url,
        "frontend_url": settings.FRONTEND_URL,
        "logo_url": _logo_url(),
    }
    html_content = render_to_string("accounts/emails/payment_retry.html", context)
    text_content = (
        f"Hi {get_user_name(user)},\n\n"
        f"Your recent Fit Trybe payment failed (attempt {retry_count}).\n\n"
        f"We will retry automatically on {next_retry_at}.\n\n"
        f"To avoid losing access, update your payment method:\n"
        f"  In browser: {web_url}\n"
        f"  In app:     {mobile_url}"
    )
    email = EmailMultiAlternatives(
        subject="Payment failed — we will retry",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)


def send_payment_failed_email(user, retry_count):
    web_url = f"{settings.FRONTEND_URL}/subscription/upgrade/"
    mobile_url = f"{_mobile_url()}subscription/upgrade"
    context = {
        "user": user,
        "user_name": get_user_name(user),
        "user_email": user.email,
        "retry_count": retry_count,
        "web_url": web_url,
        "mobile_url": mobile_url,
        "frontend_url": settings.FRONTEND_URL,
        "logo_url": _logo_url(),
    }
    html_content = render_to_string("accounts/emails/payment_failed.html", context)
    text_content = (
        f"Hi {get_user_name(user)},\n\n"
        f"We were unable to process your Fit Trybe subscription payment "
        f"(attempt {retry_count}).\n\n"
        f"Paystack will attempt to charge again on your next billing date. "
        f"To avoid losing access, please update your payment method:\n"
        f"  In browser: {web_url}\n"
        f"  In app:     {mobile_url}"
    )
    email = EmailMultiAlternatives(
        subject="Payment failed for your Fit Trybe subscription",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)


def send_card_expiring_email(user):
    web_url = f"{settings.FRONTEND_URL}/subscription/billing/"
    mobile_url = f"{_mobile_url()}subscription/billing"
    context = {
        "user": user,
        "user_name": get_user_name(user),
        "user_email": user.email,
        "web_url": web_url,
        "mobile_url": mobile_url,
        "frontend_url": settings.FRONTEND_URL,
        "logo_url": _logo_url(),
    }
    html_content = render_to_string("accounts/emails/card_expiring.html", context)
    text_content = (
        f"Hi {get_user_name(user)},\n\n"
        f"Your payment card on file is expiring soon.\n\n"
        f"Please update your payment method to avoid interruption "
        f"to your Fit Trybe subscription:\n"
        f"  In browser: {web_url}\n"
        f"  In app:     {mobile_url}"
    )
    email = EmailMultiAlternatives(
        subject="Your payment card is expiring soon",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)


def send_gym_trainer_invite_email(user, gym_profile):
    """Send a set-password invite to a newly added gym trainer."""
    from apps.profiles.tokens import gym_trainer_invite_token

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = gym_trainer_invite_token.make_token(user)
    web_url = f"{settings.FRONTEND_URL}/gym/trainer/setup?uid={uid}&token={token}"
    deep_link = f"{_mobile_url()}gym/trainer/setup?uid={uid}&token={token}"
    trainer_name = user.display_name or get_user_name(user)
    gym_name = gym_profile.gym_name
    context = {
        "trainer_name": trainer_name,
        "gym_name": gym_name,
        "set_password_url": web_url,
        "set_password_deep_link": deep_link,
        "web_url": settings.FRONTEND_URL,
        "frontend_url": settings.FRONTEND_URL,
        "logo_url": _logo_url(),
    }
    html_content = render_to_string("accounts/emails/gym_trainer_invite.html", context)
    text_content = render_to_string("accounts/emails/gym_trainer_invite.txt", context)
    email = EmailMultiAlternatives(
        subject=f"You've been added to {gym_name} — Fit Trybe",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)


def send_password_changed_email(user):
    token = PasswordResetTokenGenerator().make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    web_url = f"{settings.FRONTEND_URL}/reset-password/?uid={uid}&token={token}"
    mobile_url = f"{_mobile_url()}reset-password?uid={uid}&token={token}"
    context = {
        "user": user,
        "user_email": user.email,
        "web_url": web_url,
        "mobile_url": mobile_url,
        "frontend_url": settings.FRONTEND_URL,
        "changed_at": timezone.now().strftime("%B %d, %Y at %H:%M UTC"),
        "logo_url": _logo_url(),
        # legacy
        "reset_url": web_url,
    }
    html_content = render_to_string("accounts/emails/password_changed.html", context)
    text_content = (
        f"Your Fit Trybe password was changed.\n\n"
        f"If this was not you, reset immediately:\n"
        f"  In browser: {web_url}\n"
        f"  In app:     {mobile_url}"
    )
    email = EmailMultiAlternatives(
        subject="Fit Trybe: Password Changed Successfully",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)
