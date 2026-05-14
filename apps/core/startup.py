"""
Environment validation — called at the end of base settings.
Raises ImproperlyConfigured early with a clear list of missing variables
rather than failing deep inside a view or worker.

Uses os.environ directly (not django.conf.settings) to avoid circular
imports during the settings module load.
"""

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
        # Table may not exist yet during initial migrate — skip check
        pass


def validate_environment():
    """Verify that all required environment variables are present and non-empty."""
    missing = [var for var in _REQUIRED_VARS if not os.environ.get(var)]
    if missing:
        raise ImproperlyConfigured(
            f"Missing required environment variables: {', '.join(missing)}"
        )
    check_reference_data()
