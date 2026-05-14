import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture(autouse=True)
def seed_system_badges(db):
    from apps.badges.models import Badge
    from apps.core.management.commands.seed_app_data import BADGES

    for data in BADGES:
        Badge.objects.get_or_create(name=data["name"], defaults=data)
