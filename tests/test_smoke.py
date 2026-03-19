"""
Smoke tests — verify basic project scaffolding is correct.
These tests run WITHOUT hitting external services (Postgres, Redis).
Database-required tests use pytest-django's @pytest.mark.django_db.
"""

import importlib

import pytest
from django.conf import settings
from django.test import Client


# ---------------------------------------------------------------------------
# 1. Settings load correctly
# ---------------------------------------------------------------------------
def test_settings_load():
    """Django settings are importable and have expected keys."""
    assert hasattr(settings, "INSTALLED_APPS")
    assert hasattr(settings, "DATABASES")
    assert hasattr(settings, "REST_FRAMEWORK")
    assert settings.AUTH_USER_MODEL == "accounts.User"


def test_secret_key_is_set():
    assert settings.SECRET_KEY
    assert settings.SECRET_KEY != ""


def test_installed_apps_contain_local_apps():
    local_apps = [
        "apps.accounts",
        "apps.profiles",
        "apps.clients",
        "apps.chat",
        "apps.marketplace",
        "apps.badges",
        "apps.subscriptions",
        "apps.trackers",
        "apps.analytics",
        "apps.notifications",
    ]
    for app in local_apps:
        assert app in settings.INSTALLED_APPS, f"{app} missing from INSTALLED_APPS"


# ---------------------------------------------------------------------------
# 2. All installed apps are importable
# ---------------------------------------------------------------------------
def test_all_apps_importable():
    """Every app in INSTALLED_APPS can be imported without errors."""
    for app in settings.INSTALLED_APPS:
        try:
            importlib.import_module(app)
        except ImportError as exc:
            pytest.fail(f"Could not import app '{app}': {exc}")


# ---------------------------------------------------------------------------
# 3. Database connection works
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_database_connection(db):
    """A basic ORM call succeeds, confirming DB connectivity."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    assert User.objects.count() >= 0  # just proves the query ran


# ---------------------------------------------------------------------------
# 4. API schema endpoint responds 200
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_schema_endpoint(client: Client):
    response = client.get("/api/schema/")
    assert (
        response.status_code == 200
    ), f"Schema endpoint returned {response.status_code}"


# ---------------------------------------------------------------------------
# 5. Admin login page responds 200
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_admin_login_page(client: Client):
    response = client.get("/admin/login/")
    assert response.status_code == 200, f"Admin login returned {response.status_code}"


# ---------------------------------------------------------------------------
# 6. Core exception handler is importable and callable
# ---------------------------------------------------------------------------
def test_custom_exception_handler_importable():
    from apps.core.exceptions import custom_exception_handler

    result = custom_exception_handler(Exception("test"), {})
    assert result is None  # no matching DRF exception → returns None


# ---------------------------------------------------------------------------
# 7. CustomTokenObtainPairSerializer is importable
# ---------------------------------------------------------------------------
def test_custom_token_serializer_importable():
    from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

    from apps.accounts.serializers import CustomTokenObtainPairSerializer

    assert issubclass(CustomTokenObtainPairSerializer, TokenObtainPairSerializer)


# ---------------------------------------------------------------------------
# 8. Chat middleware stub wraps inner app
# ---------------------------------------------------------------------------
def test_jwt_auth_middleware_stub():
    from apps.chat.middleware import JwtAuthMiddlewareStack

    sentinel = object()
    assert JwtAuthMiddlewareStack(sentinel) is sentinel


# ---------------------------------------------------------------------------
# 9. Chat routing urlpatterns is an empty list
# ---------------------------------------------------------------------------
def test_chat_routing_urlpatterns():
    from apps.chat.routing import websocket_urlpatterns

    assert isinstance(websocket_urlpatterns, list)
    assert len(websocket_urlpatterns) == 0


# ---------------------------------------------------------------------------
# 10. User model __str__ returns email
# ---------------------------------------------------------------------------
def test_user_model_str():
    from apps.accounts.models import User

    u = User(email="test@fittrybe.com", username="test")
    assert str(u) == "test@fittrybe.com"
