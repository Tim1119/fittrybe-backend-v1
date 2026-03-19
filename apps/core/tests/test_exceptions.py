"""
Tests for apps.core.exceptions.custom_exception_handler.
"""

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)

from apps.core.error_codes import ErrorCode
from apps.core.exceptions import _first_message, custom_exception_handler


def handler(exc):
    """Call the handler with a minimal fake context."""
    return custom_exception_handler(exc, context={})


class TestCustomExceptionHandler:
    def test_returns_none_for_unhandled_non_drf_exception(self):
        result = handler(RuntimeError("boom"))
        assert result is None

    def test_validation_error(self):
        exc = ValidationError({"email": ["Enter a valid email address."]})
        response = handler(exc)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == ErrorCode.VALIDATION_ERROR
        assert response.data["status"] == "error"
        assert "email" in response.data["errors"]

    def test_not_authenticated(self):
        response = handler(NotAuthenticated())
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["code"] == ErrorCode.AUTHENTICATION_REQUIRED

    def test_authentication_failed(self):
        response = handler(AuthenticationFailed("Bad token"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["code"] == ErrorCode.AUTHENTICATION_REQUIRED

    def test_permission_denied_drf(self):
        response = handler(PermissionDenied())
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["code"] == ErrorCode.PERMISSION_DENIED

    def test_django_permission_denied_converted(self):
        response = handler(DjangoPermissionDenied())
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["code"] == ErrorCode.PERMISSION_DENIED

    def test_not_found_drf(self):
        response = handler(NotFound())
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["code"] == ErrorCode.NOT_FOUND

    def test_django_http404_converted(self):
        response = handler(Http404())
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["code"] == ErrorCode.NOT_FOUND

    def test_method_not_allowed(self):
        response = handler(MethodNotAllowed("DELETE"))
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert response.data["code"] == "METHOD_NOT_ALLOWED"

    def test_throttled(self):
        response = handler(Throttled())
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert response.data["code"] == ErrorCode.RATE_LIMIT_EXCEEDED

    def test_response_shape_has_all_keys(self):
        response = handler(NotFound())
        assert "status" in response.data
        assert "message" in response.data
        assert "code" in response.data
        assert "errors" in response.data
        assert "meta" in response.data
        assert "timestamp" in response.data["meta"]


class TestFirstMessage:
    def test_dict_with_detail(self):
        assert _first_message({"detail": "Not found."}, "fallback") == "Not found."

    def test_dict_without_detail(self):
        assert _first_message({"other": "val"}, "fallback") == "fallback"

    def test_list(self):
        assert _first_message(["First error"], "fallback") == "First error"

    def test_empty_list(self):
        assert _first_message([], "fallback") == "fallback"

    def test_non_dict_non_list(self):
        assert _first_message("unexpected", "fallback") == "fallback"
