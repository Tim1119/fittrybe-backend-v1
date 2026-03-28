"""
Tests for product image upload/delete endpoints.
"""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.marketplace.tests.conftest import make_product

LIST_URL = "/api/v1/marketplace/products/"


def detail_url(pk):
    return f"/api/v1/marketplace/products/{pk}/"


def images_url(pk):
    return f"/api/v1/marketplace/products/{pk}/images/"


def images_delete_url(pk):
    return f"/api/v1/marketplace/products/{pk}/images/delete/"


def make_image_file(fmt="JPEG", size=(100, 100), name="test.jpg"):
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=(255, 0, 0))
    img.save(buf, format=fmt)
    buf.seek(0)
    content_type = "image/jpeg" if fmt == "JPEG" else "image/png"
    return SimpleUploadedFile(name, buf.read(), content_type=content_type)


def make_large_image_file(name="big.jpg"):
    """Creates a file-like object that reports > 5MB."""
    content = b"x" * (5 * 1024 * 1024 + 1)
    return SimpleUploadedFile(name, content, content_type="image/jpeg")


# ─────────────────────────────────────────────────────────────────────────────
# Upload
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_upload_valid_jpeg(trainer_setup, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    _, profile, api_client = trainer_setup
    product = make_product(trainer=profile)

    img = make_image_file(fmt="JPEG", name="photo.jpg")
    res = api_client.post(images_url(product.pk), {"image": img}, format="multipart")

    assert res.status_code == 200
    assert "url" in res.data["data"]
    product.refresh_from_db()
    assert len(product.images) == 1


@pytest.mark.django_db
def test_upload_valid_png(trainer_setup, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    _, profile, api_client = trainer_setup
    product = make_product(trainer=profile)

    img = make_image_file(fmt="PNG", name="photo.png")
    res = api_client.post(images_url(product.pk), {"image": img}, format="multipart")

    assert res.status_code == 200
    product.refresh_from_db()
    assert len(product.images) == 1


@pytest.mark.django_db
def test_upload_non_image_rejected(trainer_setup):
    _, profile, api_client = trainer_setup
    product = make_product(trainer=profile)

    bad_file = SimpleUploadedFile(
        "doc.pdf", b"PDF content", content_type="application/pdf"
    )
    res = api_client.post(
        images_url(product.pk), {"image": bad_file}, format="multipart"
    )

    assert res.status_code == 400


@pytest.mark.django_db
def test_upload_over_5mb_rejected(trainer_setup):
    _, profile, api_client = trainer_setup
    product = make_product(trainer=profile)

    big = make_large_image_file()
    res = api_client.post(images_url(product.pk), {"image": big}, format="multipart")

    assert res.status_code == 400


@pytest.mark.django_db
def test_upload_sixth_image_rejected(trainer_setup, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    _, profile, api_client = trainer_setup
    product = make_product(
        trainer=profile,
        images=["url1", "url2", "url3", "url4", "url5"],
    )

    img = make_image_file(fmt="JPEG", name="extra.jpg")
    res = api_client.post(images_url(product.pk), {"image": img}, format="multipart")

    assert res.status_code == 400


@pytest.mark.django_db
def test_non_owner_cannot_upload(trainer_setup, trainer2_setup, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    _, p1, _ = trainer_setup
    _, _, api_client2 = trainer2_setup
    product = make_product(trainer=p1)

    img = make_image_file(fmt="JPEG", name="photo.jpg")
    res = api_client2.post(images_url(product.pk), {"image": img}, format="multipart")

    assert res.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Delete image URL
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_delete_image_url_removes_from_list(trainer_setup):
    _, profile, api_client = trainer_setup
    product = make_product(
        trainer=profile, images=["http://example.com/a.jpg", "http://example.com/b.jpg"]
    )

    res = api_client.delete(
        images_delete_url(product.pk),
        {"url": "http://example.com/a.jpg"},
        format="json",
    )

    assert res.status_code == 200
    product.refresh_from_db()
    assert "http://example.com/a.jpg" not in product.images
    assert "http://example.com/b.jpg" in product.images


@pytest.mark.django_db
def test_delete_nonexistent_url_returns_400(trainer_setup):
    _, profile, api_client = trainer_setup
    product = make_product(trainer=profile, images=["http://example.com/a.jpg"])

    res = api_client.delete(
        images_delete_url(product.pk),
        {"url": "http://example.com/nothere.jpg"},
        format="json",
    )

    assert res.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Combined create + images (POST /products/ multipart)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_create_product_with_images_multipart(trainer_setup, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    _, profile, api_client = trainer_setup

    img1 = make_image_file(fmt="JPEG", name="a.jpg")
    img2 = make_image_file(fmt="PNG", name="b.png")
    payload = {
        "name": "Program With Photos",
        "description": "Comes with photos",
        "category": "program",
        "price": "3000.00",
        "images": [img1, img2],
    }
    res = api_client.post(LIST_URL, payload, format="multipart")

    assert res.status_code == 201
    assert len(res.data["data"]["images"]) == 2


@pytest.mark.django_db
def test_create_product_too_many_images_rejected(trainer_setup, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    _, profile, api_client = trainer_setup

    files = [make_image_file(fmt="JPEG", name=f"img{i}.jpg") for i in range(6)]
    payload = {
        "name": "Too Many Photos",
        "description": "desc",
        "category": "program",
        "price": "1000.00",
        "images": files,
    }
    res = api_client.post(LIST_URL, payload, format="multipart")

    assert res.status_code == 400


@pytest.mark.django_db
def test_create_product_invalid_image_type_rejected(trainer_setup):
    _, profile, api_client = trainer_setup

    bad = SimpleUploadedFile("doc.pdf", b"PDF content", content_type="application/pdf")
    payload = {
        "name": "Bad Image",
        "description": "desc",
        "category": "program",
        "price": "1000.00",
        "images": bad,
    }
    res = api_client.post(LIST_URL, payload, format="multipart")

    assert res.status_code == 400


@pytest.mark.django_db
def test_create_product_oversized_image_rejected(trainer_setup):
    _, profile, api_client = trainer_setup

    big = make_large_image_file()
    payload = {
        "name": "Big Image",
        "description": "desc",
        "category": "program",
        "price": "1000.00",
        "images": big,
    }
    res = api_client.post(LIST_URL, payload, format="multipart")

    assert res.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Combined update + images (PUT /products/{id}/ multipart)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_update_product_adds_new_images(trainer_setup, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    _, profile, api_client = trainer_setup
    product = make_product(trainer=profile, images=["http://example.com/existing.jpg"])

    img = make_image_file(fmt="JPEG", name="new.jpg")
    payload = {
        "existing_images": "http://example.com/existing.jpg",
        "images": img,
    }
    res = api_client.put(detail_url(product.pk), payload, format="multipart")

    assert res.status_code == 200
    assert len(res.data["data"]["images"]) == 2
    assert "http://example.com/existing.jpg" in res.data["data"]["images"]


@pytest.mark.django_db
def test_update_product_drops_existing_image_when_not_passed(
    trainer_setup, settings, tmp_path
):
    settings.MEDIA_ROOT = str(tmp_path)
    _, profile, api_client = trainer_setup
    product = make_product(
        trainer=profile,
        images=["http://example.com/old1.jpg", "http://example.com/old2.jpg"],
    )

    img = make_image_file(fmt="JPEG", name="new.jpg")
    # Keep only old1, drop old2, add new file
    payload = {
        "existing_images": "http://example.com/old1.jpg",
        "images": img,
    }
    res = api_client.put(detail_url(product.pk), payload, format="multipart")

    assert res.status_code == 200
    images = res.data["data"]["images"]
    assert "http://example.com/old1.jpg" in images
    assert "http://example.com/old2.jpg" not in images
    assert len(images) == 2  # old1 + new file


@pytest.mark.django_db
def test_update_product_exceeds_max_images_rejected(trainer_setup, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    _, profile, api_client = trainer_setup
    product = make_product(
        trainer=profile,
        images=["u1", "u2", "u3", "u4"],
    )

    img1 = make_image_file(fmt="JPEG", name="n1.jpg")
    img2 = make_image_file(fmt="JPEG", name="n2.jpg")
    payload = {
        "existing_images": ["u1", "u2", "u3", "u4"],
        "images": [img1, img2],  # 4 existing + 2 new = 6 → reject
    }
    res = api_client.put(detail_url(product.pk), payload, format="multipart")

    assert res.status_code == 400
