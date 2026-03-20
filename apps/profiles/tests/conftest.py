import pytest


@pytest.fixture(autouse=True)
def disable_ratelimit(settings):
    """Disable django-ratelimit for all profile tests."""
    settings.RATELIMIT_ENABLE = False
