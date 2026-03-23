"""Tests for HTML web profile pages."""

import pytest

from apps.profiles.tests.factories import (
    GymProfileFactory,
    PublishedGymProfileFactory,
    PublishedTrainerProfileFactory,
    TrainerProfileFactory,
)


@pytest.mark.django_db
class TestTrainerWebProfile:
    def test_published_profile_returns_200(self, client):
        profile = PublishedTrainerProfileFactory()
        response = client.get(f"/trainer/{profile.slug}/")
        assert response.status_code == 200

    def test_unpublished_profile_returns_404(self, client):
        profile = TrainerProfileFactory(is_published=False)
        response = client.get(f"/trainer/{profile.slug}/")
        assert response.status_code == 404

    def test_nonexistent_slug_returns_404(self, client):
        response = client.get("/trainer/does-not-exist/")
        assert response.status_code == 404

    def test_response_is_html(self, client):
        profile = PublishedTrainerProfileFactory()
        response = client.get(f"/trainer/{profile.slug}/")
        assert "text/html" in response["Content-Type"]

    def test_contains_profile_name(self, client):
        profile = PublishedTrainerProfileFactory(full_name="Jane Doe")
        response = client.get(f"/trainer/{profile.slug}/")
        assert b"Jane Doe" in response.content

    def test_contains_og_title_meta_tag(self, client):
        profile = PublishedTrainerProfileFactory(full_name="Jane Doe")
        response = client.get(f"/trainer/{profile.slug}/")
        assert b"og:title" in response.content

    def test_contains_og_description_meta_tag(self, client):
        profile = PublishedTrainerProfileFactory()
        response = client.get(f"/trainer/{profile.slug}/")
        assert b"og:description" in response.content

    def test_contains_og_image_meta_tag(self, client):
        profile = PublishedTrainerProfileFactory()
        response = client.get(f"/trainer/{profile.slug}/")
        assert b"og:image" in response.content

    def test_contains_deep_link(self, client):
        profile = PublishedTrainerProfileFactory()
        response = client.get(f"/trainer/{profile.slug}/")
        assert b"fittrybe://trainer/" in response.content


@pytest.mark.django_db
class TestGymWebProfile:
    def test_published_gym_returns_200(self, client):
        profile = PublishedGymProfileFactory()
        response = client.get(f"/gym/{profile.slug}/")
        assert response.status_code == 200

    def test_unpublished_gym_returns_404(self, client):
        profile = GymProfileFactory(is_published=False)
        response = client.get(f"/gym/{profile.slug}/")
        assert response.status_code == 404

    def test_nonexistent_slug_returns_404(self, client):
        response = client.get("/gym/does-not-exist/")
        assert response.status_code == 404

    def test_response_is_html(self, client):
        profile = PublishedGymProfileFactory()
        response = client.get(f"/gym/{profile.slug}/")
        assert "text/html" in response["Content-Type"]

    def test_contains_gym_name(self, client):
        profile = PublishedGymProfileFactory(gym_name="Iron Palace")
        response = client.get(f"/gym/{profile.slug}/")
        assert b"Iron Palace" in response.content

    def test_contains_og_title_meta_tag(self, client):
        profile = PublishedGymProfileFactory()
        response = client.get(f"/gym/{profile.slug}/")
        assert b"og:title" in response.content

    def test_contains_og_description_meta_tag(self, client):
        profile = PublishedGymProfileFactory()
        response = client.get(f"/gym/{profile.slug}/")
        assert b"og:description" in response.content

    def test_contains_deep_link(self, client):
        profile = PublishedGymProfileFactory()
        response = client.get(f"/gym/{profile.slug}/")
        assert b"fittrybe://gym/" in response.content
