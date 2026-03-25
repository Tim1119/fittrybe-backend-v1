"""
TDD tests for ratings and reviews endpoints.

GET/POST  /api/v1/profiles/trainer/<slug>/reviews/
POST      /api/v1/profiles/trainer/<slug>/reviews/<review_id>/respond/
GET/POST  /api/v1/profiles/gym/<slug>/reviews/
POST      /api/v1/profiles/gym/<slug>/reviews/<review_id>/respond/
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import ClientFactory, GymFactory, TrainerFactory
from apps.clients.models import ClientMembership
from apps.clients.tests.factories import (
    ClientMembershipGymFactory,
    ClientMembershipTrainerFactory,
)
from apps.profiles.models import Review
from apps.profiles.tests.factories import (
    ClientProfileFactory,
    PublishedGymProfileFactory,
    PublishedTrainerProfileFactory,
    TrainerProfileFactory,
)


@pytest.fixture
def api_client():
    return APIClient()


def trainer_reviews_url(slug):
    return f"/api/v1/profiles/trainer/{slug}/reviews/"


def trainer_respond_url(slug, review_id):
    return f"/api/v1/profiles/trainer/{slug}/reviews/{review_id}/respond/"


def gym_reviews_url(slug):
    return f"/api/v1/profiles/gym/{slug}/reviews/"


def gym_respond_url(slug, review_id):
    return f"/api/v1/profiles/gym/{slug}/reviews/{review_id}/respond/"


# ---------------------------------------------------------------------------
# Submit review — happy path
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSubmitTrainerReview:

    def test_client_with_membership_can_review_trainer(self, api_client):
        profile = PublishedTrainerProfileFactory()
        client_user = ClientFactory()
        client_profile = ClientProfileFactory(user=client_user)
        ClientMembershipTrainerFactory(
            trainer=profile,
            client=client_profile,
            status=ClientMembership.Status.ACTIVE,
        )
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(
            trainer_reviews_url(profile.slug),
            {"rating": 5, "content": "Excellent trainer!"},
            format="json",
        )

        assert resp.status_code == 201
        assert Review.objects.filter(trainer=profile, client=client_profile).exists()

    def test_submitting_review_updates_trainer_avg_rating(self, api_client):
        profile = PublishedTrainerProfileFactory()
        client_user = ClientFactory()
        client_profile = ClientProfileFactory(user=client_user)
        ClientMembershipTrainerFactory(
            trainer=profile,
            client=client_profile,
            status=ClientMembership.Status.ACTIVE,
        )
        api_client.force_authenticate(user=client_user)

        api_client.post(
            trainer_reviews_url(profile.slug),
            {"rating": 4, "content": "Great!"},
            format="json",
        )

        profile.refresh_from_db()
        assert float(profile.avg_rating) == 4.0

    def test_submitting_review_updates_trainer_rating_count(self, api_client):
        profile = PublishedTrainerProfileFactory()
        client_user = ClientFactory()
        client_profile = ClientProfileFactory(user=client_user)
        ClientMembershipTrainerFactory(
            trainer=profile,
            client=client_profile,
            status=ClientMembership.Status.ACTIVE,
        )
        api_client.force_authenticate(user=client_user)

        api_client.post(
            trainer_reviews_url(profile.slug),
            {"rating": 5, "content": "Amazing!"},
            format="json",
        )

        profile.refresh_from_db()
        assert profile.rating_count == 1


@pytest.mark.django_db
class TestSubmitGymReview:

    def test_client_with_membership_can_review_gym(self, api_client):
        gym_profile = PublishedGymProfileFactory()
        client_user = ClientFactory()
        client_profile = ClientProfileFactory(user=client_user)
        ClientMembershipGymFactory(
            gym=gym_profile,
            client=client_profile,
            status=ClientMembership.Status.ACTIVE,
        )
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(
            gym_reviews_url(gym_profile.slug),
            {"rating": 4, "content": "Great gym!"},
            format="json",
        )

        assert resp.status_code == 201
        assert Review.objects.filter(gym=gym_profile, client=client_profile).exists()


# ---------------------------------------------------------------------------
# Submit review — membership gate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMembershipGate:

    def test_client_without_membership_cannot_review_trainer(self, api_client):
        profile = PublishedTrainerProfileFactory()
        client_user = ClientFactory()
        ClientProfileFactory(user=client_user)
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(
            trainer_reviews_url(profile.slug),
            {"rating": 5, "content": "Good"},
            format="json",
        )

        assert resp.status_code == 403

    def test_client_without_membership_cannot_review_gym(self, api_client):
        gym_profile = PublishedGymProfileFactory()
        client_user = ClientFactory()
        ClientProfileFactory(user=client_user)
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(
            gym_reviews_url(gym_profile.slug),
            {"rating": 4, "content": "Ok"},
            format="json",
        )

        assert resp.status_code == 403

    def test_soft_deleted_membership_blocks_trainer_review(self, api_client):
        profile = PublishedTrainerProfileFactory()
        client_user = ClientFactory()
        client_profile = ClientProfileFactory(user=client_user)
        membership = ClientMembershipTrainerFactory(
            trainer=profile,
            client=client_profile,
            status=ClientMembership.Status.ACTIVE,
        )
        membership.delete()  # soft-delete
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(
            trainer_reviews_url(profile.slug),
            {"rating": 5, "content": "Great"},
            format="json",
        )

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Submit review — role checks
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestReviewRoleChecks:

    def test_trainer_role_cannot_submit_review(self, api_client):
        profile = PublishedTrainerProfileFactory()
        other_trainer = TrainerFactory()
        api_client.force_authenticate(user=other_trainer)

        resp = api_client.post(
            trainer_reviews_url(profile.slug),
            {"rating": 3, "content": "Meh"},
            format="json",
        )

        assert resp.status_code == 403

    def test_gym_role_cannot_submit_review(self, api_client):
        profile = PublishedTrainerProfileFactory()
        gym_user = GymFactory()
        api_client.force_authenticate(user=gym_user)

        resp = api_client.post(
            trainer_reviews_url(profile.slug),
            {"rating": 3, "content": "Meh"},
            format="json",
        )

        assert resp.status_code == 403

    def test_unauthenticated_cannot_submit_review(self, api_client):
        profile = PublishedTrainerProfileFactory()

        resp = api_client.post(
            trainer_reviews_url(profile.slug),
            {"rating": 5, "content": "Good"},
            format="json",
        )

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Submit review — validation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestReviewValidation:

    def _client_with_membership(self, profile, is_gym=False):
        client_user = ClientFactory()
        client_profile = ClientProfileFactory(user=client_user)
        if is_gym:
            ClientMembershipGymFactory(
                gym=profile,
                client=client_profile,
                status=ClientMembership.Status.ACTIVE,
            )
        else:
            ClientMembershipTrainerFactory(
                trainer=profile,
                client=client_profile,
                status=ClientMembership.Status.ACTIVE,
            )
        return client_user

    def test_rating_zero_returns_400(self, api_client):
        profile = PublishedTrainerProfileFactory()
        client_user = self._client_with_membership(profile)
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(
            trainer_reviews_url(profile.slug),
            {"rating": 0, "content": "Ok"},
            format="json",
        )

        assert resp.status_code == 400

    def test_rating_six_returns_400(self, api_client):
        profile = PublishedTrainerProfileFactory()
        client_user = self._client_with_membership(profile)
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(
            trainer_reviews_url(profile.slug),
            {"rating": 6, "content": "Ok"},
            format="json",
        )

        assert resp.status_code == 400

    def test_empty_content_returns_400(self, api_client):
        profile = PublishedTrainerProfileFactory()
        client_user = self._client_with_membership(profile)
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(
            trainer_reviews_url(profile.slug),
            {"rating": 4, "content": ""},
            format="json",
        )

        assert resp.status_code == 400

    def test_duplicate_trainer_review_returns_400(self, api_client):
        profile = PublishedTrainerProfileFactory()
        client_user = self._client_with_membership(profile)
        client_profile = client_user.client_profile
        # Pre-existing review
        Review.objects.create(
            client=client_profile,
            trainer=profile,
            rating=5,
            content="First review",
        )
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(
            trainer_reviews_url(profile.slug),
            {"rating": 4, "content": "Second review"},
            format="json",
        )

        assert resp.status_code == 400

    def test_duplicate_gym_review_returns_400(self, api_client):
        gym_profile = PublishedGymProfileFactory()
        client_user = self._client_with_membership(gym_profile, is_gym=True)
        client_profile = client_user.client_profile
        Review.objects.create(
            client=client_profile,
            gym=gym_profile,
            rating=3,
            content="First review",
        )
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(
            gym_reviews_url(gym_profile.slug),
            {"rating": 4, "content": "Second review"},
            format="json",
        )

        assert resp.status_code == 400

    def test_unpublished_trainer_returns_404(self, api_client):
        profile = TrainerProfileFactory()  # not published
        client_user = ClientFactory()
        ClientProfileFactory(user=client_user)
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(
            trainer_reviews_url(profile.slug),
            {"rating": 5, "content": "Test"},
            format="json",
        )

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# List reviews — public
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestListReviews:

    def test_anyone_can_list_trainer_reviews_no_auth(self, api_client):
        profile = PublishedTrainerProfileFactory()

        resp = api_client.get(trainer_reviews_url(profile.slug))

        assert resp.status_code == 200

    def test_list_returns_paginated_results(self, api_client):
        profile = PublishedTrainerProfileFactory()
        client1 = ClientProfileFactory()
        client2 = ClientProfileFactory()
        Review.objects.create(
            client=client1, trainer=profile, rating=5, content="Great"
        )
        Review.objects.create(client=client2, trainer=profile, rating=4, content="Good")

        resp = api_client.get(trainer_reviews_url(profile.slug))

        assert resp.status_code == 200
        assert resp.data["meta"]["pagination"]["total_count"] == 2

    def test_list_includes_avg_rating_in_summary(self, api_client):
        profile = PublishedTrainerProfileFactory()

        resp = api_client.get(trainer_reviews_url(profile.slug))

        assert "summary" in resp.data
        assert "avg_rating" in resp.data["summary"]

    def test_list_includes_total_reviews_in_summary(self, api_client):
        profile = PublishedTrainerProfileFactory()

        resp = api_client.get(trainer_reviews_url(profile.slug))

        assert "summary" in resp.data
        assert "total_reviews" in resp.data["summary"]

    def test_list_includes_rating_distribution_with_all_5_stars(self, api_client):
        profile = PublishedTrainerProfileFactory()

        resp = api_client.get(trainer_reviews_url(profile.slug))

        dist = resp.data["summary"]["rating_distribution"]
        assert set(dist.keys()) == {1, 2, 3, 4, 5}

    def test_stars_with_no_reviews_show_zero_not_missing(self, api_client):
        profile = PublishedTrainerProfileFactory()
        client_profile = ClientProfileFactory()
        Review.objects.create(
            client=client_profile, trainer=profile, rating=5, content="5 star"
        )

        resp = api_client.get(trainer_reviews_url(profile.slug))

        dist = resp.data["summary"]["rating_distribution"]
        assert dist[1] == 0
        assert dist[5] == 1

    def test_soft_deleted_reviews_not_shown(self, api_client):
        profile = PublishedTrainerProfileFactory()
        client_profile = ClientProfileFactory()
        review = Review.objects.create(
            client=client_profile, trainer=profile, rating=5, content="Great"
        )
        review.delete()  # soft-delete

        resp = api_client.get(trainer_reviews_url(profile.slug))

        assert resp.data["meta"]["pagination"]["total_count"] == 0


# ---------------------------------------------------------------------------
# Respond to review
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRespondToReview:

    def test_trainer_can_respond_to_own_review(self, api_client):
        profile = PublishedTrainerProfileFactory()
        client_profile = ClientProfileFactory()
        review = Review.objects.create(
            client=client_profile, trainer=profile, rating=4, content="Good"
        )
        api_client.force_authenticate(user=profile.user)

        resp = api_client.post(
            trainer_respond_url(profile.slug, review.id),
            {"trainer_response": "Thank you!"},
            format="json",
        )

        assert resp.status_code == 200
        review.refresh_from_db()
        assert review.trainer_response == "Thank you!"

    def test_trainer_can_update_existing_response(self, api_client):
        profile = PublishedTrainerProfileFactory()
        client_profile = ClientProfileFactory()
        review = Review.objects.create(
            client=client_profile,
            trainer=profile,
            rating=4,
            content="Good",
            trainer_response="Old response",
        )
        api_client.force_authenticate(user=profile.user)

        resp = api_client.post(
            trainer_respond_url(profile.slug, review.id),
            {"trainer_response": "Updated response"},
            format="json",
        )

        assert resp.status_code == 200
        review.refresh_from_db()
        assert review.trainer_response == "Updated response"

    def test_trainer_cannot_respond_to_another_trainers_review(self, api_client):
        other_profile = PublishedTrainerProfileFactory()
        client_profile = ClientProfileFactory()
        review = Review.objects.create(
            client=client_profile,
            trainer=other_profile,
            rating=3,
            content="Ok",
        )
        my_profile = PublishedTrainerProfileFactory()
        api_client.force_authenticate(user=my_profile.user)

        resp = api_client.post(
            trainer_respond_url(my_profile.slug, review.id),
            {"trainer_response": "Hacking"},
            format="json",
        )

        assert resp.status_code == 404

    def test_gym_can_respond_to_own_gym_review(self, api_client):
        gym_profile = PublishedGymProfileFactory()
        client_profile = ClientProfileFactory()
        review = Review.objects.create(
            client=client_profile, gym=gym_profile, rating=5, content="Wow"
        )
        api_client.force_authenticate(user=gym_profile.user)

        resp = api_client.post(
            gym_respond_url(gym_profile.slug, review.id),
            {"trainer_response": "Thanks!"},
            format="json",
        )

        assert resp.status_code == 200
        review.refresh_from_db()
        assert review.trainer_response == "Thanks!"

    def test_client_cannot_respond_to_review(self, api_client):
        profile = PublishedTrainerProfileFactory()
        client_user = ClientFactory()
        client_profile = ClientProfileFactory(user=client_user)
        review = Review.objects.create(
            client=client_profile, trainer=profile, rating=4, content="Good"
        )
        api_client.force_authenticate(user=client_user)

        resp = api_client.post(
            trainer_respond_url(profile.slug, review.id),
            {"trainer_response": "Response"},
            format="json",
        )

        assert resp.status_code == 403

    def test_empty_trainer_response_returns_400(self, api_client):
        profile = PublishedTrainerProfileFactory()
        client_profile = ClientProfileFactory()
        review = Review.objects.create(
            client=client_profile, trainer=profile, rating=4, content="Good"
        )
        api_client.force_authenticate(user=profile.user)

        resp = api_client.post(
            trainer_respond_url(profile.slug, review.id),
            {"trainer_response": ""},
            format="json",
        )

        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Rating recalculation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRatingRecalculation:

    def _post_review(self, api_client, profile, client_user, rating):
        api_client.force_authenticate(user=client_user)
        api_client.post(
            trainer_reviews_url(profile.slug),
            {"rating": rating, "content": f"{rating} star review"},
            format="json",
        )

    def test_avg_rating_correct_after_one_review(self, api_client):
        profile = PublishedTrainerProfileFactory()
        c = ClientFactory()
        cp = ClientProfileFactory(user=c)
        ClientMembershipTrainerFactory(
            trainer=profile, client=cp, status=ClientMembership.Status.ACTIVE
        )
        self._post_review(api_client, profile, c, 4)

        profile.refresh_from_db()
        assert float(profile.avg_rating) == 4.0

    def test_avg_rating_correct_after_multiple_reviews(self, api_client):
        profile = PublishedTrainerProfileFactory()
        # Two clients, each with a membership
        c1 = ClientFactory()
        cp1 = ClientProfileFactory(user=c1)
        ClientMembershipTrainerFactory(
            trainer=profile, client=cp1, status=ClientMembership.Status.ACTIVE
        )
        c2 = ClientFactory()
        cp2 = ClientProfileFactory(user=c2)
        ClientMembershipTrainerFactory(
            trainer=profile, client=cp2, status=ClientMembership.Status.ACTIVE
        )

        self._post_review(api_client, profile, c1, 5)
        self._post_review(api_client, profile, c2, 3)

        profile.refresh_from_db()
        assert float(profile.avg_rating) == 4.0

    def test_avg_rating_is_zero_when_no_reviews(self, api_client):
        profile = PublishedTrainerProfileFactory()

        profile.refresh_from_db()
        # Default is 0.00, never None
        assert profile.avg_rating is not None
        assert float(profile.avg_rating) == 0.0

    def test_rating_count_correct(self, api_client):
        profile = PublishedTrainerProfileFactory()
        c1 = ClientFactory()
        cp1 = ClientProfileFactory(user=c1)
        ClientMembershipTrainerFactory(
            trainer=profile, client=cp1, status=ClientMembership.Status.ACTIVE
        )
        c2 = ClientFactory()
        cp2 = ClientProfileFactory(user=c2)
        ClientMembershipTrainerFactory(
            trainer=profile, client=cp2, status=ClientMembership.Status.ACTIVE
        )

        self._post_review(api_client, profile, c1, 5)
        self._post_review(api_client, profile, c2, 3)

        profile.refresh_from_db()
        assert profile.rating_count == 2
