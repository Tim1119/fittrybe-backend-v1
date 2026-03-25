"""
Fit Trybe Backend — Base Settings
Shared across all environments.
"""

from datetime import timedelta
from pathlib import Path

import environ

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "django_celery_beat",
    "django_celery_results",
    "channels",
    "anymail",
    "django_extensions",
    "axes",
]

LOCAL_APPS = [
    "apps.core",
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

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "apps.core.middleware.RequestIDMiddleware",
    "apps.subscriptions.middleware.SubscriptionGateMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "axes.middleware.AxesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "fittrybe_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "fittrybe_backend.wsgi.application"
ASGI_APPLICATION = "fittrybe_backend.asgi.application"

# ---------------------------------------------------------------------------
# Database — PostgreSQL
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="5432"),
        "OPTIONS": {"connect_timeout": 10},
    }
}

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & Media files
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
}

# ---------------------------------------------------------------------------
# Simple JWT
# ---------------------------------------------------------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=24),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "TOKEN_OBTAIN_SERIALIZER": (
        "apps.accounts.serializers.CustomTokenObtainPairSerializer"
    ),
}

# ---------------------------------------------------------------------------
# drf-spectacular (OpenAPI)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "Fit Trybe API",
    "DESCRIPTION": """
Fit Trybe — The Fitness Lifestyle Hub Backend API.

## Authentication
Use JWT Bearer tokens. Obtain tokens via /api/v1/auth/login/
Include in header: `Authorization: Bearer <access_token>`

## Response Format
All endpoints return a consistent envelope:
```json
{
  "status": "success | error",
  "message": "Human readable message",
  "data": {} or [] or null,
  "errors": {},
  "code": "ERROR_CODE",
  "meta": {
    "timestamp": "2025-03-19T10:00:00Z",
    "version": "v1",
    "pagination": {}
  }
}
```

## Error Codes
- `VALIDATION_ERROR` — invalid input
- `INVALID_CREDENTIALS` — wrong email/password
- `ACCOUNT_NOT_VERIFIED` — email not verified
- `ACCOUNT_LOCKED` — too many failed attempts
- `TOKEN_INVALID` — expired or invalid token
- `PERMISSION_DENIED` — insufficient permissions
- `NOT_FOUND` — resource not found
- `RATE_LIMIT_EXCEEDED` — too many requests
- `SUBSCRIPTION_EXPIRED` — subscription locked
    """,
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    "TAGS": [
        {
            "name": "Authentication",
            "description": (
                "Registration, login, email verification, password management"
            ),
        },
        {
            "name": "Subscriptions",
            "description": "Plans, billing, Paystack and Stripe checkout",
        },
        {
            "name": "Profiles",
            "description": "Trainer and gym profile management",
        },
        {
            "name": "Profile Wizard",
            "description": "Step-by-step profile setup for new trainers and gyms",
        },
        {
            "name": "Public Profiles",
            "description": "Public-facing profile discovery and search",
        },
        {
            "name": "Health",
            "description": "System health and status",
        },
    ],
}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# Django Channels
# ---------------------------------------------------------------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                (
                    env("REDIS_HOST", default="localhost"),
                    env.int("REDIS_PORT", default=6379),
                )
            ],
        },
    },
}

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "django-cache"
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# ---------------------------------------------------------------------------
# Email — Mailgun via django-anymail
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
ANYMAIL = {
    "MAILGUN_API_KEY": env("MAILGUN_API_KEY", default=""),
    "MAILGUN_SENDER_DOMAIN": env("MAILGUN_SENDER_DOMAIN", default=""),
}
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@fittrybe.com")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# ---------------------------------------------------------------------------
# Axes — account lockout
# ---------------------------------------------------------------------------
AXES_FAILURE_LIMIT = 3
AXES_COOLOFF_TIME = 0.25  # 15 minutes
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_CALLABLE = "apps.accounts.utils.axes_lockout_response"

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
RATELIMIT_USE_CACHE = "default"
RATELIMIT_ENABLE = True

# ---------------------------------------------------------------------------
# Frontend URL (for email links)
# ---------------------------------------------------------------------------
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")
MOBILE_URL = env("MOBILE_URL", default="fittrybe://")

# ---------------------------------------------------------------------------
# Payment gateways
# ---------------------------------------------------------------------------
PAYSTACK_SECRET_KEY = env("PAYSTACK_SECRET_KEY", default="")
PAYSTACK_PUBLIC_KEY = env("PAYSTACK_PUBLIC_KEY", default="")

STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_WEBHOOK_SECRET = ""

# ---------------------------------------------------------------------------
# Deep link / app store config
# ---------------------------------------------------------------------------
APPLE_TEAM_ID = env("APPLE_TEAM_ID", default="TEAMID")
ANDROID_PACKAGE_NAME = env("ANDROID_PACKAGE_NAME", default="com.fittrybe.app")
ANDROID_SHA256_FINGERPRINT = env("ANDROID_SHA256_FINGERPRINT", default="PLACEHOLDER")
APP_STORE_URL = env("APP_STORE_URL", default="#")
PLAY_STORE_URL = env("PLAY_STORE_URL", default="#")


# ---------------------------------------------------------------------------
# Celery Beat — scheduled tasks
# ---------------------------------------------------------------------------
from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    "check-trial-expirations": {
        "task": "apps.subscriptions.tasks.check_trial_expirations",
        "schedule": crontab(minute="0"),
    },
    "check-grace-period-expirations": {
        "task": "apps.subscriptions.tasks.check_grace_period_expirations",
        "schedule": crontab(minute="30"),
    },
    "check-active-subscription-expirations": {
        "task": "apps.subscriptions.tasks.check_active_subscription_expirations",
        "schedule": crontab(minute="15"),
    },
    "send-payment-reminders": {
        "task": "apps.clients.tasks.send_payment_reminders",
        "schedule": crontab(hour=9, minute=0),
    },
    "update-membership-statuses": {
        "task": "apps.clients.tasks.update_membership_statuses",
        "schedule": crontab(hour=0, minute=0),
    },
}

# ---------------------------------------------------------------------------
# Environment validation
# ---------------------------------------------------------------------------
from apps.core.startup import validate_environment  # noqa: E402

validate_environment()
