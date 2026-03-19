"""
Tests for apps/core/middleware.py — RequestIDMiddleware.
"""

from django.http import HttpResponse
from django.test import RequestFactory

from apps.core.middleware import RequestIDMiddleware


def _get_response(request):
    return HttpResponse()


class TestRequestIDMiddleware:
    def setup_method(self):
        self.factory = RequestFactory()
        self.middleware = RequestIDMiddleware(_get_response)

    def test_request_id_added_to_response_headers(self):
        request = self.factory.get("/")
        response = self.middleware(request)
        assert "X-Request-ID" in response

    def test_custom_request_id_is_respected(self):
        request = self.factory.get("/", HTTP_X_REQUEST_ID="my-trace-id")
        response = self.middleware(request)
        assert response["X-Request-ID"] == "my-trace-id"

    def test_different_requests_get_different_ids(self):
        r1 = self.factory.get("/")
        r2 = self.factory.get("/")
        resp1 = self.middleware(r1)
        resp2 = self.middleware(r2)
        assert resp1["X-Request-ID"] != resp2["X-Request-ID"]

    def test_request_id_stored_on_request_object(self):
        request = self.factory.get("/")
        self.middleware(request)
        assert hasattr(request, "request_id")
        assert request.request_id

    def test_custom_id_stored_on_request_object(self):
        request = self.factory.get("/", HTTP_X_REQUEST_ID="abc-123")
        self.middleware(request)
        assert request.request_id == "abc-123"
