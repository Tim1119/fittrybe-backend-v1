"""
Core middleware.
"""

import logging
import uuid

logger = logging.getLogger(__name__)


class RequestIDMiddleware:
    """Attach a unique request ID to every request and response.

    Uses the incoming X-Request-ID header if present (e.g. from a load
    balancer or API gateway), otherwise generates a UUID4.  The ID is
    available as ``request.request_id`` throughout the request lifecycle
    and echoed back in the X-Request-ID response header.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.request_id = request_id
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response
