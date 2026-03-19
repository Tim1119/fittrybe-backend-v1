import pytest


@pytest.fixture(autouse=True)
def disable_ratelimit(settings):
    """Disable django-ratelimit for all accounts tests."""
    settings.RATELIMIT_ENABLE = False
