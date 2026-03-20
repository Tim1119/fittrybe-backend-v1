"""Accounts utility functions."""

from django.http import JsonResponse
from django.utils.timezone import now


def axes_lockout_response(request, credentials, *args, **kwargs):
    """Custom lockout response for django-axes (AXES_LOCKOUT_CALLABLE)."""
    return JsonResponse(
        {
            "status": "error",
            "message": (
                "Too many failed login attempts. " "Account locked for 15 minutes."
            ),
            "errors": {},
            "code": "ACCOUNT_LOCKED",
            "meta": {
                "timestamp": now().isoformat(),
                "version": "v1",
            },
        },
        status=429,
    )
