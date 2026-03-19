"""
Fit Trybe Backend — Development Settings
"""

from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# Override email to console in development
# EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", default="sandbox.smtp.mailtrap.io")
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=2525)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)

# Django Debug Toolbar
INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]  # noqa: F405
INTERNAL_IPS = ["127.0.0.1"]

# Run Celery tasks synchronously in development/tests (no broker required)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# LOGGING = {
#     "version": 1,
#     "disable_existing_loggers": False,
#     "formatters": {
#         "verbose": {
#             "format": (
#                 "[{levelname}] {asctime} {module} {process:d} {thread:d} {message}"
#             ),
#             "style": "{",
#         },
#         "simple": {
#             "format": "[{levelname}] {message}",
#             "style": "{",
#         },
#     },
#     "handlers": {
#         "console": {
#             "class": "logging.StreamHandler",
#             "formatter": "verbose",
#         },
#     },
#     "root": {
#         "handlers": ["console"],
#         "level": "DEBUG",
#     },
#     "loggers": {
#         "django": {
#             "handlers": ["console"],
#             "level": "DEBUG",
#             "propagate": False,
#         },
#         "apps": {
#             "handlers": ["console"],
#             "level": "DEBUG",
#             "propagate": False,
#         },
#     },
# }

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",  # Changed from DEBUG
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",  # Only show INFO and above for Django
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",  # Suppress SQL query logs
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "DEBUG",  # Keep DEBUG for your own apps only
            "propagate": False,
        },
    },
}
