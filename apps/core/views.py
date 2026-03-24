"""
Core views — system health check and well-known deep link files.
"""

from django.conf import settings
from django.http import JsonResponse
from django.views import View
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


class AppleAppSiteAssociationView(View):
    def get(self, request):
        data = {
            "applinks": {
                "apps": [],
                "details": [
                    {
                        "appID": (
                            f"{settings.APPLE_TEAM_ID}"
                            f".{settings.ANDROID_PACKAGE_NAME}"
                        ),
                        "paths": [
                            "/trainer/*",
                            "/gym/*",
                            "/invite/*",
                            "/verify-email/*",
                            "/reset-password/*",
                        ],
                    }
                ],
            }
        }
        return JsonResponse(data, content_type="application/json")


class AssetLinksView(View):
    def get(self, request):
        data = [
            {
                "relation": ["delegate_permission/common.handle_all_urls"],
                "target": {
                    "namespace": "android_app",
                    "package_name": settings.ANDROID_PACKAGE_NAME,
                    "sha256_cert_fingerprints": [settings.ANDROID_SHA256_FINGERPRINT],
                },
            }
        ]
        return JsonResponse(data, safe=False, content_type="application/json")
