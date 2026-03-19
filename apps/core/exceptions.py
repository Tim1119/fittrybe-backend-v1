"""
Custom DRF exception handler — standardised error response shape.
"""

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
)
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.exceptions import Throttled, ValidationError
from rest_framework.views import exception_handler

from apps.core.error_codes import ErrorCode
from apps.core.responses import APIResponse


def custom_exception_handler(exc, context):
    """
    Wraps DRF's default handler and converts all error responses into the
    standard APIResponse.error shape.
    """
    # Convert Django-level exceptions to DRF equivalents first
    if isinstance(exc, Http404):
        exc = NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = DRFPermissionDenied()

    response = exception_handler(exc, context)

    if response is None:
        return None

    if isinstance(exc, ValidationError):
        return APIResponse.error(
            message="Validation error.",
            errors=response.data,
            code=ErrorCode.VALIDATION_ERROR,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, NotAuthenticated) or isinstance(exc, AuthenticationFailed):
        return APIResponse.error(
            message=_first_message(response.data, "Authentication required."),
            code=ErrorCode.AUTHENTICATION_REQUIRED,
            status_code=response.status_code,
        )

    if isinstance(exc, (DRFPermissionDenied,)):
        return APIResponse.error(
            message=_first_message(
                response.data, "You do not have permission to perform this action."
            ),
            code=ErrorCode.PERMISSION_DENIED,
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if isinstance(exc, NotFound):
        return APIResponse.error(
            message=_first_message(response.data, "Not found."),
            code=ErrorCode.NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, MethodNotAllowed):
        return APIResponse.error(
            message=_first_message(response.data, "Method not allowed."),
            code="METHOD_NOT_ALLOWED",
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    if isinstance(exc, Throttled):
        return APIResponse.error(
            message="Too many requests. Please try again later.",
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # Fallback for any other DRF exception
    return APIResponse.error(
        message=_first_message(response.data, "An error occurred."),
        code=ErrorCode.SERVER_ERROR,
        status_code=response.status_code,
    )


def _first_message(data, fallback: str) -> str:
    """Extract a human-readable message from a DRF error response dict/list."""
    if isinstance(data, dict):
        detail = data.get("detail", fallback)
        return str(detail) if detail else fallback
    if isinstance(data, list) and data:
        return str(data[0])
    return fallback
