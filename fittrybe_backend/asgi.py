"""
ASGI config for fittrybe_backend project.

Supports HTTP (Django) and WebSocket (Django Channels) protocols.
"""

import os

import django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fittrybe_backend.settings.development")
django.setup()

from apps.chat.middleware import JwtAuthMiddlewareStack  # noqa: E402
from apps.chat.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AllowedHostsOriginValidator(
            JwtAuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
