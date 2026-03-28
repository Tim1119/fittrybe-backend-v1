"""
Tests for product enquiry endpoints.
"""

from unittest.mock import patch

import pytest

from apps.marketplace.models import Product, ProductEnquiry
from apps.marketplace.tests.conftest import make_product


def enquire_url(pk):
    return f"/api/v1/marketplace/products/{pk}/enquire/"


def enquiries_url(pk):
    return f"/api/v1/marketplace/products/{pk}/enquiries/"


def respond_url(pk, enq_pk):
    return f"/api/v1/marketplace/products/{pk}/enquiries/{enq_pk}/respond/"


# ─────────────────────────────────────────────────────────────────────────────
# Enquire — POST /products/{id}/enquire/
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_client_can_enquire_on_active_product(trainer_setup, client_setup):
    _, profile, _ = trainer_setup
    product = make_product(trainer=profile, status=Product.Status.ACTIVE)
    _, _, api_client = client_setup

    with patch("apps.notifications.tasks.send_push_notification.delay"):
        res = api_client.post(
            enquire_url(product.pk), {"message": "Is this available?"}, format="json"
        )

    assert res.status_code == 201
    assert res.data["data"]["message"] == "Is this available?"


@pytest.mark.django_db
def test_enquiry_increments_enquiry_count(trainer_setup, client_setup):
    _, profile, _ = trainer_setup
    product = make_product(trainer=profile, status=Product.Status.ACTIVE)
    _, _, api_client = client_setup

    with patch("apps.notifications.tasks.send_push_notification.delay"):
        api_client.post(enquire_url(product.pk), {"message": "Hi"}, format="json")

    product.refresh_from_db()
    assert product.enquiry_count == 1


@pytest.mark.django_db
def test_client_cannot_enquire_twice(trainer_setup, client_setup):
    _, profile, _ = trainer_setup
    product = make_product(trainer=profile, status=Product.Status.ACTIVE)
    _, client_profile, api_client = client_setup

    ProductEnquiry.objects.create(
        product=product, client=client_profile, message="First"
    )

    with patch("apps.notifications.tasks.send_push_notification.delay"):
        res = api_client.post(
            enquire_url(product.pk), {"message": "Second"}, format="json"
        )

    assert res.status_code == 400


@pytest.mark.django_db
def test_trainer_cannot_enquire(trainer_setup):
    _, profile, api_client = trainer_setup
    product = make_product(trainer=profile, status=Product.Status.ACTIVE)

    res = api_client.post(enquire_url(product.pk), {"message": "Hi"}, format="json")
    assert res.status_code == 403


@pytest.mark.django_db
def test_cannot_enquire_on_draft_product(trainer_setup, client_setup):
    _, profile, _ = trainer_setup
    product = make_product(trainer=profile, status=Product.Status.DRAFT)
    _, _, api_client = client_setup

    res = api_client.post(enquire_url(product.pk), {"message": "Hi"}, format="json")
    assert res.status_code == 404


@pytest.mark.django_db
def test_cannot_enquire_on_archived_product(trainer_setup, client_setup):
    _, profile, _ = trainer_setup
    product = make_product(trainer=profile, status=Product.Status.ARCHIVED)
    _, _, api_client = client_setup

    res = api_client.post(enquire_url(product.pk), {"message": "Hi"}, format="json")
    assert res.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# List enquiries — GET /products/{id}/enquiries/
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_owner_sees_all_enquiries(trainer_setup, client_setup):
    _, profile, api_client = trainer_setup
    product = make_product(trainer=profile, status=Product.Status.ACTIVE)
    _, client_profile, _ = client_setup
    ProductEnquiry.objects.create(
        product=product, client=client_profile, message="Hello"
    )

    res = api_client.get(enquiries_url(product.pk))
    assert res.status_code == 200
    assert len(res.data["data"]) == 1


@pytest.mark.django_db
def test_non_owner_cannot_see_enquiries(trainer_setup, trainer2_setup, client_setup):
    _, p1, _ = trainer_setup
    _, _, api_client2 = trainer2_setup
    product = make_product(trainer=p1, status=Product.Status.ACTIVE)
    _, client_profile, _ = client_setup
    ProductEnquiry.objects.create(
        product=product, client=client_profile, message="Hello"
    )

    res = api_client2.get(enquiries_url(product.pk))
    assert res.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Respond — POST /products/{id}/enquiries/{enq_id}/respond/
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_owner_can_respond_to_enquiry(trainer_setup, client_setup):
    _, profile, api_client = trainer_setup
    product = make_product(trainer=profile, status=Product.Status.ACTIVE)
    _, client_profile, _ = client_setup
    enquiry = ProductEnquiry.objects.create(
        product=product, client=client_profile, message="Hi"
    )

    with patch("apps.notifications.tasks.send_push_notification.delay"):
        res = api_client.post(
            respond_url(product.pk, enquiry.pk),
            {"response": "Yes, available!", "status": "responded"},
            format="json",
        )

    assert res.status_code == 200
    assert res.data["data"]["trainer_response"] == "Yes, available!"


@pytest.mark.django_db
def test_respond_sets_responded_at_and_status(trainer_setup, client_setup):
    _, profile, api_client = trainer_setup
    product = make_product(trainer=profile, status=Product.Status.ACTIVE)
    _, client_profile, _ = client_setup
    enquiry = ProductEnquiry.objects.create(
        product=product, client=client_profile, message="Hi"
    )

    with patch("apps.notifications.tasks.send_push_notification.delay"):
        api_client.post(
            respond_url(product.pk, enquiry.pk),
            {"response": "Sure!", "status": "responded"},
            format="json",
        )

    enquiry.refresh_from_db()
    assert enquiry.status == ProductEnquiry.Status.RESPONDED
    assert enquiry.responded_at is not None


@pytest.mark.django_db
def test_client_gets_push_notification_on_response(trainer_setup, client_setup):
    _, profile, api_client = trainer_setup
    product = make_product(trainer=profile, status=Product.Status.ACTIVE)
    client_user, client_profile, _ = client_setup
    enquiry = ProductEnquiry.objects.create(
        product=product, client=client_profile, message="Hi"
    )

    with patch("apps.notifications.tasks.send_push_notification.delay") as mock_push:
        api_client.post(
            respond_url(product.pk, enquiry.pk),
            {"response": "Yes!", "status": "responded"},
            format="json",
        )

    mock_push.assert_called_once()
    call_kwargs = mock_push.call_args
    assert (
        str(client_user.id) in call_kwargs[0]
        or str(client_user.id) == call_kwargs[1].get("user_id")
        or call_kwargs[0][0] == str(client_user.id)
    )


@pytest.mark.django_db
def test_owner_gets_push_notification_on_new_enquiry(trainer_setup, client_setup):
    trainer_user, profile, _ = trainer_setup
    product = make_product(trainer=profile, status=Product.Status.ACTIVE)
    _, _, api_client = client_setup

    with patch("apps.notifications.tasks.send_push_notification.delay") as mock_push:
        api_client.post(
            enquire_url(product.pk), {"message": "Interested"}, format="json"
        )

    mock_push.assert_called_once()
    call_kwargs = mock_push.call_args
    assert str(trainer_user.id) == call_kwargs[0][0]
