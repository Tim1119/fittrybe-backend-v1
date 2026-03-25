import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture(autouse=True)
def disable_ratelimit(settings):
    """Disable django-ratelimit for all profile tests."""
    settings.RATELIMIT_ENABLE = False
