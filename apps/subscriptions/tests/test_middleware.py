"""
Tests for SubscriptionGateMiddleware.
"""

from datetime import timedelta

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.tests.factories import ClientFactory, TrainerFactory
from apps.subscriptions.middleware import SubscriptionGateMiddleware
from apps.subscriptions.tests.factories import BasicPlanFactory, SubscriptionFactory


def _get_response(_request):
    return HttpResponse("OK")


def _jwt_header(user):
    refresh = RefreshToken.for_user(user)
    return f"Bearer {str(refresh.access_token)}"


@pytest.mark.django_db
class TestSubscriptionGateMiddleware:
    def setup_method(self):
        self.factory = RequestFactory()
        self.middleware = SubscriptionGateMiddleware(_get_response)

    def test_exempt_auth_path_passes_through(self):
        request = self.factory.get("/api/v1/auth/login/")
        resp = self.middleware(request)
        assert resp.status_code == 200

    def test_unauthenticated_request_passes_through(self):
        request = self.factory.get("/api/v1/profiles/me/")
        resp = self.middleware(request)
        assert resp.status_code == 200

    def test_active_subscription_passes_through(self):
        user = TrainerFactory()
        BasicPlanFactory()
        SubscriptionFactory(
            user=user,
            status="trial",
            trial_end=timezone.now() + timedelta(days=7),
        )
        request = self.factory.get(
            "/api/v1/profiles/me/",
            HTTP_AUTHORIZATION=_jwt_header(user),
        )
        resp = self.middleware(request)
        assert resp.status_code == 200

    def test_locked_subscription_returns_403(self):
        user = TrainerFactory()
        BasicPlanFactory()
        SubscriptionFactory(
            user=user,
            status="locked",
            trial_end=timezone.now() - timedelta(days=1),
        )
        request = self.factory.get(
            "/api/v1/profiles/me/",
            HTTP_AUTHORIZATION=_jwt_header(user),
        )
        resp = self.middleware(request)
        assert resp.status_code == 403

    def test_client_always_passes_through(self):
        user = ClientFactory()
        request = self.factory.get(
            "/api/v1/profiles/me/",
            HTTP_AUTHORIZATION=_jwt_header(user),
        )
        resp = self.middleware(request)
        assert resp.status_code == 200

    def test_exempt_plans_path_passes_through(self):
        user = TrainerFactory()
        BasicPlanFactory()
        SubscriptionFactory(
            user=user,
            status="locked",
            trial_end=timezone.now() - timedelta(days=1),
        )
        request = self.factory.get(
            "/api/v1/subscriptions/plans/",
            HTTP_AUTHORIZATION=_jwt_header(user),
        )
        resp = self.middleware(request)
        assert resp.status_code == 200

    def test_cancelled_subscription_returns_403(self):
        user = TrainerFactory()
        BasicPlanFactory()
        SubscriptionFactory(
            user=user,
            status="cancelled",
            trial_end=timezone.now() - timedelta(days=1),
        )
        request = self.factory.get(
            "/api/v1/profiles/me/",
            HTTP_AUTHORIZATION=_jwt_header(user),
        )
        resp = self.middleware(request)
        assert resp.status_code == 403
