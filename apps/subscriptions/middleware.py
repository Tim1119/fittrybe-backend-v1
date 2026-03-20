"""
Subscription gate middleware — blocks locked/cancelled accounts.
"""

import logging

from django.http import JsonResponse
from django.utils.timezone import now

logger = logging.getLogger(__name__)

EXEMPT_PATHS = [
    "/api/v1/auth/",
    "/api/v1/subscriptions/webhook/",
    "/api/v1/subscriptions/plans/",
    "/api/v1/subscriptions/checkout/",
    "/api/v1/subscriptions/status/",
    "/api/v1/subscriptions/cancel/",
    "/api/v1/subscriptions/billing/",
    "/api/docs/",
    "/api/schema/",
    "/api/redoc/",
    "/admin/",
    "/api/v1/health/",
]


class SubscriptionGateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def _get_user(self, request):
        """Resolve the user from session auth or JWT Bearer token."""
        if hasattr(request, "user") and request.user.is_authenticated:
            return request.user

        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return None

        token_str = auth_header[7:]
        try:
            from rest_framework_simplejwt.authentication import JWTAuthentication

            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token_str)
            return jwt_auth.get_user(validated_token)
        except Exception:
            return None

    def __call__(self, request):
        for path in EXEMPT_PATHS:
            if request.path.startswith(path):
                return self.get_response(request)

        user = self._get_user(request)

        if user is None or not user.is_authenticated:
            return self.get_response(request)

        if user.role == "client":
            return self.get_response(request)

        try:
            sub = user.subscription
            if not sub.is_access_allowed():
                return JsonResponse(
                    {
                        "status": "error",
                        "message": (
                            "Your subscription has expired. "
                            "Please renew to continue."
                        ),
                        "errors": {},
                        "code": "SUBSCRIPTION_EXPIRED",
                        "meta": {
                            "timestamp": now().isoformat(),
                            "version": "v1",
                        },
                    },
                    status=403,
                )
        except Exception:
            pass

        return self.get_response(request)
