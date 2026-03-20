"""
Core views — system health check.
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.core.responses import APIResponse


@extend_schema(
    summary="Health check",
    description=(
        "Returns HTTP 200 when the API is reachable and healthy. "
        "Used by load balancers, uptime monitors, and CI pipelines. "
        "No authentication required."
    ),
    responses={
        200: OpenApiResponse(description="Service is healthy"),
    },
    tags=["Health"],
    auth=[],
)
class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return APIResponse.success(
            data={"status": "healthy"},
            message="Service is healthy.",
        )
