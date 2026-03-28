"""
Tests for product listing endpoints.
"""

import pytest

from apps.marketplace.models import Product
from apps.marketplace.tests.conftest import make_product

LIST_URL = "/api/v1/marketplace/products/"
MY_URL = "/api/v1/marketplace/products/my/"


def detail_url(pk):
    return f"/api/v1/marketplace/products/{pk}/"


# ─────────────────────────────────────────────────────────────────────────────
# Public list — GET /products/
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_public_list_returns_only_active(trainer_setup, anon_client):
    _, profile, _ = trainer_setup
    make_product(trainer=profile, status=Product.Status.ACTIVE, name="Active Product")
    make_product(trainer=profile, status=Product.Status.DRAFT, name="Draft Product")
    make_product(
        trainer=profile, status=Product.Status.ARCHIVED, name="Archived Product"
    )

    res = anon_client.get(LIST_URL)
    assert res.status_code == 200
    names = [p["name"] for p in res.data["data"]]
    assert "Active Product" in names
    assert "Draft Product" not in names
    assert "Archived Product" not in names


@pytest.mark.django_db
def test_public_list_q_filter(trainer_setup, anon_client):
    _, profile, _ = trainer_setup
    make_product(trainer=profile, name="Yoga Program", description="Yoga class")
    make_product(trainer=profile, name="Nutrition Guide", description="Diet plan")

    res = anon_client.get(LIST_URL, {"q": "yoga"})
    assert res.status_code == 200
    names = [p["name"] for p in res.data["data"]]
    assert "Yoga Program" in names
    assert "Nutrition Guide" not in names


@pytest.mark.django_db
def test_public_list_category_filter(trainer_setup, anon_client):
    _, profile, _ = trainer_setup
    make_product(
        trainer=profile, name="Equipment Item", category=Product.Category.EQUIPMENT
    )
    make_product(
        trainer=profile, name="Nutrition Plan", category=Product.Category.NUTRITION
    )

    res = anon_client.get(LIST_URL, {"category": "equipment"})
    assert res.status_code == 200
    names = [p["name"] for p in res.data["data"]]
    assert "Equipment Item" in names
    assert "Nutrition Plan" not in names


@pytest.mark.django_db
def test_public_list_min_max_price_filter(trainer_setup, trainer2_setup, anon_client):
    _, p1, _ = trainer_setup
    _, p2, _ = trainer2_setup
    make_product(trainer=p1, name="Cheap", price="500.00")
    make_product(trainer=p2, name="Expensive", price="50000.00")

    res = anon_client.get(LIST_URL, {"min_price": "1000", "max_price": "10000"})
    assert res.status_code == 200
    names = [p["name"] for p in res.data["data"]]
    assert "Cheap" not in names
    assert "Expensive" not in names


@pytest.mark.django_db
def test_public_list_is_featured_filter(trainer_setup, anon_client):
    _, profile, _ = trainer_setup
    make_product(trainer=profile, name="Featured", is_featured=True)
    make_product(trainer=profile, name="Normal", is_featured=False)

    res = anon_client.get(LIST_URL, {"is_featured": "true"})
    assert res.status_code == 200
    names = [p["name"] for p in res.data["data"]]
    assert "Featured" in names
    assert "Normal" not in names


@pytest.mark.django_db
def test_public_list_type_trainer_filter(trainer_setup, gym_setup, anon_client):
    _, t_profile, _ = trainer_setup
    _, g_profile, _ = gym_setup
    make_product(trainer=t_profile, name="Trainer Product")
    make_product(gym=g_profile, name="Gym Product")

    res = anon_client.get(LIST_URL, {"type": "trainer"})
    assert res.status_code == 200
    names = [p["name"] for p in res.data["data"]]
    assert "Trainer Product" in names
    assert "Gym Product" not in names


# ─────────────────────────────────────────────────────────────────────────────
# Detail — GET /products/{id}/
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_get_detail_increments_view_count(trainer_setup, anon_client):
    _, profile, _ = trainer_setup
    product = make_product(trainer=profile)
    assert product.view_count == 0

    anon_client.get(detail_url(product.pk))
    product.refresh_from_db()
    assert product.view_count == 1


# ─────────────────────────────────────────────────────────────────────────────
# Create — POST /products/
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_trainer_can_create_product(trainer_setup):
    _, profile, api_client = trainer_setup
    payload = {
        "name": "New Program",
        "description": "A great program",
        "category": "program",
        "price": "3000.00",
    }
    res = api_client.post(LIST_URL, payload, format="json")
    assert res.status_code == 201
    assert res.data["data"]["name"] == "New Program"
    assert res.data["data"]["status"] == "draft"


@pytest.mark.django_db
def test_gym_can_create_product(gym_setup):
    _, profile, api_client = gym_setup
    payload = {
        "name": "Gym Class",
        "description": "Weekly class",
        "category": "class",
        "price": "1500.00",
    }
    res = api_client.post(LIST_URL, payload, format="json")
    assert res.status_code == 201
    data = res.data["data"]
    assert data["seller"]["seller_type"] == "gym"


@pytest.mark.django_db
def test_client_cannot_create_product(client_setup):
    _, _, api_client = client_setup
    payload = {
        "name": "Client Product",
        "description": "Should fail",
        "category": "other",
        "price": "100.00",
    }
    res = api_client.post(LIST_URL, payload, format="json")
    assert res.status_code == 403


@pytest.mark.django_db
def test_anon_cannot_create_product(anon_client):
    payload = {
        "name": "Anon Product",
        "description": "Should fail",
        "category": "other",
        "price": "100.00",
    }
    res = anon_client.post(LIST_URL, payload, format="json")
    assert res.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# Update — PUT /products/{id}/
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_trainer_can_update_own_product(trainer_setup):
    _, profile, api_client = trainer_setup
    product = make_product(trainer=profile, name="Old Name")

    res = api_client.put(detail_url(product.pk), {"name": "New Name"}, format="json")
    assert res.status_code == 200
    assert res.data["data"]["name"] == "New Name"


@pytest.mark.django_db
def test_trainer_cannot_update_another_trainers_product(trainer_setup, trainer2_setup):
    _, p1, _ = trainer_setup
    _, p2, api_client2 = trainer2_setup
    product = make_product(trainer=p1, name="Trainer1 Product")

    res = api_client2.put(detail_url(product.pk), {"name": "Hijacked"}, format="json")
    assert res.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Delete (archive) — DELETE /products/{id}/
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_delete_archives_product_not_hard_delete(trainer_setup):
    _, profile, api_client = trainer_setup
    product = make_product(trainer=profile)

    res = api_client.delete(detail_url(product.pk))
    assert res.status_code == 200

    product.refresh_from_db()
    assert product.status == Product.Status.ARCHIVED
    assert Product.objects.filter(pk=product.pk).exists()


# ─────────────────────────────────────────────────────────────────────────────
# My products — GET /products/my/
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_my_products_returns_all_statuses(trainer_setup):
    _, profile, api_client = trainer_setup
    make_product(trainer=profile, name="Active", status=Product.Status.ACTIVE)
    make_product(trainer=profile, name="Draft", status=Product.Status.DRAFT)
    make_product(trainer=profile, name="Archived", status=Product.Status.ARCHIVED)

    res = api_client.get(MY_URL)
    assert res.status_code == 200
    names = [p["name"] for p in res.data["data"]]
    assert "Active" in names
    assert "Draft" in names
    assert "Archived" in names


@pytest.mark.django_db
def test_my_products_does_not_return_other_trainers_products(
    trainer_setup, trainer2_setup
):
    _, p1, api_client1 = trainer_setup
    _, p2, _ = trainer2_setup
    make_product(trainer=p1, name="Mine")
    make_product(trainer=p2, name="Theirs")

    res = api_client1.get(MY_URL)
    assert res.status_code == 200
    names = [p["name"] for p in res.data["data"]]
    assert "Mine" in names
    assert "Theirs" not in names
