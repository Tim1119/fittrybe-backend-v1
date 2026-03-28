"""
Tests for product image upload/delete endpoints.
"""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.marketplace.tests.conftest import make_product


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
