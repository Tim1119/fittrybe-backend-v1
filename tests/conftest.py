import pytest
from django.test import Client
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def django_client():
    return Client()
