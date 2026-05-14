import os

from django.core.exceptions import ImproperlyConfigured

_REQUIRED_VARS = [
    "SECRET_KEY",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "REDIS_URL",
    "DEFAULT_FROM_EMAIL",
    "FRONTEND_URL",
]


def validate_environment():
    """Verify that all required environment variables are present and non-empty."""
    missing = [var for var in _REQUIRED_VARS if not os.environ.get(var)]
    if missing:
        raise ImproperlyConfigured(
            f"Missing required environment variables: {', '.join(missing)}"
        )


def check_reference_data():
    try:
        from apps.profiles.models import Specialisation

        if not Specialisation.objects.filter(is_predefined=True).exists():
            raise ImproperlyConfigured(
                "\n\n"
                "  ❌ Reference data missing.\n"
                "  The app cannot start without seeded reference data.\n"
                "  Run this command then restart the server:\n\n"
                "      python manage.py seed_app_data\n"
            )
    except Exception as e:
        if isinstance(e, ImproperlyConfigured):
            raise
        pass
