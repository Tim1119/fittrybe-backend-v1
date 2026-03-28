"""
Marketplace views — product listings and enquiries.
"""

import os
import uuid

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import IsTrainerOrGym
from apps.core.error_codes import ErrorCode
from apps.core.pagination import StandardPagination
from apps.core.responses import APIResponse
from apps.marketplace.models import Product, ProductEnquiry
from apps.marketplace.serializers import (
    ProductCreateUpdateSerializer,
    ProductEnquirySerializer,
    ProductPublicSerializer,
    ProductSerializer,
)
from apps.notifications.models import Notification
from apps.notifications.tasks import send_push_notification

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _get_owner_profile(user):
    """Return (trainer_profile, gym_profile) based on user.role."""
    if user.role == "trainer":
        return getattr(user, "trainer_profile", None), None
    if user.role == "gym":
        return None, getattr(user, "gym_profile", None)
    return None, None


def _is_product_owner(product, user):
    """Return True if user owns the product."""
    if product.trainer_id and hasattr(user, "trainer_profile"):
        return product.trainer.user_id == user.id
    if product.gym_id and hasattr(user, "gym_profile"):
        return product.gym.user_id == user.id
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Product endpoints
# ─────────────────────────────────────────────────────────────────────────────


@extend_schema(tags=["Marketplace"])
class ProductListCreateView(APIView):
    """
    GET  — public browse, no auth required.
    POST — create a new product listing (trainer or gym only).
    """

    permission_classes = []

    @extend_schema(
        summary="List active product listings",
        description=(
            "Returns paginated active product listings. "
            "Supports filtering by keyword (q), category, seller type, "
            "location, price range, and featured status. "
            "No authentication required."
        ),
        parameters=[
            OpenApiParameter("q", str, description="Search name + description"),
            OpenApiParameter("category", str, description="Filter by category enum"),
            OpenApiParameter("type", str, description="'trainer' or 'gym'"),
            OpenApiParameter(
                "location", str, description="Filter by seller's location"
            ),
            OpenApiParameter("min_price", str, description="Minimum price"),
            OpenApiParameter("max_price", str, description="Maximum price"),
            OpenApiParameter(
                "is_featured", str, description="'true' for featured only"
            ),
        ],
        responses={
            200: OpenApiResponse(description="Paginated product listings"),
        },
        auth=[],
    )
    def get(self, request):
        qs = Product.objects.filter(status=Product.Status.ACTIVE).select_related(
            "trainer__user", "gym__user"
        )

        q = request.query_params.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)

        seller_type = request.query_params.get("type")
        if seller_type == "trainer":
            qs = qs.filter(trainer__isnull=False)
        elif seller_type == "gym":
            qs = qs.filter(gym__isnull=False)

        location = request.query_params.get("location")
        if location:
            qs = qs.filter(
                Q(trainer__location__icontains=location)
                | Q(gym__location__icontains=location)
            )

        min_price = request.query_params.get("min_price")
        if min_price:
            qs = qs.filter(price__gte=min_price)

        max_price = request.query_params.get("max_price")
        if max_price:
            qs = qs.filter(price__lte=max_price)

        is_featured = request.query_params.get("is_featured")
        if is_featured and is_featured.lower() == "true":
            qs = qs.filter(is_featured=True)

        qs = qs.order_by("-is_featured", "-created_at")

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = ProductPublicSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        summary="Create a product listing",
        description=(
            "Creates a new product listing. Caller must be a trainer or gym. "
            "The product is created with status=draft. "
            "Requires authentication."
        ),
        request=ProductCreateUpdateSerializer,
        responses={
            201: OpenApiResponse(description="Product created (draft)"),
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Not a trainer or gym"),
        },
    )
    def post(self, request):
        if not request.user.is_authenticated:
            return APIResponse.error(
                message="Authentication required.",
                code=ErrorCode.AUTHENTICATION_REQUIRED,
                status_code=401,
            )
        if request.user.role not in ("trainer", "gym"):
            return APIResponse.error(
                message="Only trainers and gyms can create listings.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        serializer = ProductCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message="Validation error.",
                errors=serializer.errors,
                code=ErrorCode.VALIDATION_ERROR,
            )

        trainer, gym = _get_owner_profile(request.user)
        product = serializer.save(trainer=trainer, gym=gym, status=Product.Status.DRAFT)
        return APIResponse.created(
            data=ProductSerializer(product).data,
            message="Product listing created.",
        )


@extend_schema(tags=["Marketplace"])
class ProductDetailView(APIView):
    """
    GET    — public, increments view count.
    PUT    — update (owner only).
    DELETE — soft archive (owner only).
    """

    permission_classes = []

    def _get_product(self, pk):
        try:
            return Product.objects.select_related("trainer__user", "gym__user").get(
                pk=pk
            )
        except Product.DoesNotExist:
            return None

    @extend_schema(
        summary="Retrieve a product listing",
        description=(
            "Returns a single active product. Increments view_count atomically."
        ),
        responses={
            200: OpenApiResponse(description="Product detail"),
            404: OpenApiResponse(description="Not found"),
        },
        auth=[],
    )
    def get(self, request, pk):
        product = self._get_product(pk)
        if not product:
            return APIResponse.error(
                message="Product not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        Product.objects.filter(pk=pk).update(view_count=F("view_count") + 1)
        product.refresh_from_db()
        return APIResponse.success(
            data=ProductPublicSerializer(product).data,
            message="Product retrieved.",
        )

    @extend_schema(
        summary="Update a product listing",
        description="Partial update allowed. Only the product owner may update.",
        request=ProductCreateUpdateSerializer,
        responses={
            200: OpenApiResponse(description="Updated product"),
            403: OpenApiResponse(description="Not the owner"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    def put(self, request, pk):
        if not request.user.is_authenticated:
            return APIResponse.error(
                message="Authentication required.",
                code=ErrorCode.AUTHENTICATION_REQUIRED,
                status_code=401,
            )
        product = self._get_product(pk)
        if not product:
            return APIResponse.error(
                message="Product not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        if not _is_product_owner(product, request.user):
            return APIResponse.error(
                message="You do not own this listing.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        serializer = ProductCreateUpdateSerializer(
            product, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return APIResponse.error(
                message="Validation error.",
                errors=serializer.errors,
                code=ErrorCode.VALIDATION_ERROR,
            )
        product = serializer.save()
        return APIResponse.success(
            data=ProductSerializer(product).data,
            message="Product updated.",
        )

    @extend_schema(
        summary="Archive a product listing",
        description=(
            "Sets status to 'archived'. Does not hard-delete. "
            "Only the owner may archive."
        ),
        responses={
            200: OpenApiResponse(description="Listing archived"),
            403: OpenApiResponse(description="Not the owner"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    def delete(self, request, pk):
        if not request.user.is_authenticated:
            return APIResponse.error(
                message="Authentication required.",
                code=ErrorCode.AUTHENTICATION_REQUIRED,
                status_code=401,
            )
        product = self._get_product(pk)
        if not product:
            return APIResponse.error(
                message="Product not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        if not _is_product_owner(product, request.user):
            return APIResponse.error(
                message="You do not own this listing.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )
        product.status = Product.Status.ARCHIVED
        product.save(update_fields=["status"])
        return APIResponse.success(message="Listing archived.")


@extend_schema(tags=["Marketplace"])
class MyProductsView(APIView):
    """GET — returns all listings owned by the authenticated trainer or gym."""

    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    @extend_schema(
        summary="List my product listings",
        description=(
            "Returns all products (all statuses: draft, active, archived, sold_out) "
            "owned by the authenticated trainer or gym. Paginated."
        ),
        responses={
            200: OpenApiResponse(description="Owner's product listings"),
        },
    )
    def get(self, request):
        trainer, gym = _get_owner_profile(request.user)
        if trainer:
            qs = Product.objects.filter(trainer=trainer)
        else:
            qs = Product.objects.filter(gym=gym)

        qs = qs.select_related("trainer__user", "gym__user").order_by("-created_at")
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = ProductSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# Image endpoints
# ─────────────────────────────────────────────────────────────────────────────

MAX_IMAGES = 5
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES = ("image/jpeg", "image/png")


@extend_schema(tags=["Marketplace"])
class ProductImageUploadView(APIView):
    """POST — upload an image for a product (owner only)."""

    permission_classes = []
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        summary="Upload a product image",
        description=(
            "Upload a JPEG or PNG image (max 5 MB). "
            "A product may have at most 5 images. "
            "Caller must be the product owner."
        ),
        responses={
            200: OpenApiResponse(description="Image uploaded, URLs returned"),
            400: OpenApiResponse(description="Validation error (size/type/limit)"),
            403: OpenApiResponse(description="Not the owner"),
            404: OpenApiResponse(description="Product not found"),
        },
    )
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return APIResponse.error(
                message="Authentication required.",
                code=ErrorCode.AUTHENTICATION_REQUIRED,
                status_code=401,
            )
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return APIResponse.error(
                message="Product not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        if not _is_product_owner(product, request.user):
            return APIResponse.error(
                message="You do not own this listing.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        image_file = request.FILES.get("image")
        if not image_file:
            return APIResponse.error(
                message="No image file provided.",
                code=ErrorCode.VALIDATION_ERROR,
            )

        if image_file.content_type not in ALLOWED_CONTENT_TYPES:
            return APIResponse.error(
                message="Only JPEG and PNG images are allowed.",
                code=ErrorCode.VALIDATION_ERROR,
            )

        if image_file.size > MAX_IMAGE_SIZE_BYTES:
            return APIResponse.error(
                message="Image must be smaller than 5 MB.",
                code=ErrorCode.VALIDATION_ERROR,
            )

        if len(product.images) >= MAX_IMAGES:
            return APIResponse.error(
                message=f"A product can have at most {MAX_IMAGES} images.",
                code=ErrorCode.VALIDATION_ERROR,
            )

        from django.conf import settings

        ext = "jpg" if image_file.content_type == "image/jpeg" else "png"
        filename = f"{uuid.uuid4()}.{ext}"
        rel_path = os.path.join("marketplace", "products", filename)
        abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)

        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "wb") as f:
            for chunk in image_file.chunks():
                f.write(chunk)

        url = f"{settings.MEDIA_URL}{rel_path}"
        product.images = list(product.images) + [url]
        product.save(update_fields=["images"])

        return APIResponse.success(
            data={"url": url, "images": product.images},
            message="Image uploaded.",
        )


@extend_schema(tags=["Marketplace"])
class ProductImageDeleteView(APIView):
    """DELETE — remove an image URL from a product (owner only)."""

    permission_classes = []

    @extend_schema(
        summary="Delete a product image",
        description=(
            "Remove an image URL from the product's images list. Caller must be owner."
        ),
        responses={
            200: OpenApiResponse(description="Remaining images returned"),
            400: OpenApiResponse(description="URL not in images list"),
            403: OpenApiResponse(description="Not the owner"),
            404: OpenApiResponse(description="Product not found"),
        },
    )
    def delete(self, request, pk):
        if not request.user.is_authenticated:
            return APIResponse.error(
                message="Authentication required.",
                code=ErrorCode.AUTHENTICATION_REQUIRED,
                status_code=401,
            )
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return APIResponse.error(
                message="Product not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        if not _is_product_owner(product, request.user):
            return APIResponse.error(
                message="You do not own this listing.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        url = request.data.get("url")
        if not url or url not in product.images:
            return APIResponse.error(
                message="URL not found in product images.",
                code=ErrorCode.NOT_FOUND,
            )

        images = list(product.images)
        images.remove(url)
        product.images = images
        product.save(update_fields=["images"])

        return APIResponse.success(
            data={"images": product.images},
            message="Image removed.",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Enquiry endpoints
# ─────────────────────────────────────────────────────────────────────────────


@extend_schema(tags=["Marketplace"])
class ProductEnquireView(APIView):
    """POST — send an enquiry on an active product (client only)."""

    permission_classes = []

    @extend_schema(
        summary="Send an enquiry on a product",
        description=(
            "A client sends an enquiry on an active product. "
            "Only one enquiry per client per product is allowed. "
            "The product owner receives a push notification and in-app notification."
        ),
        responses={
            201: OpenApiResponse(description="Enquiry created"),
            400: OpenApiResponse(description="Already enquired"),
            403: OpenApiResponse(description="Not a client"),
            404: OpenApiResponse(description="Product not found or not active"),
        },
    )
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return APIResponse.error(
                message="Authentication required.",
                code=ErrorCode.AUTHENTICATION_REQUIRED,
                status_code=401,
            )
        if request.user.role != "client":
            return APIResponse.error(
                message="Only clients can submit enquiries.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        try:
            product = Product.objects.select_related("trainer__user", "gym__user").get(
                pk=pk, status=Product.Status.ACTIVE
            )
        except Product.DoesNotExist:
            return APIResponse.error(
                message="Product not found or not available.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        client_profile = getattr(request.user, "client_profile", None)
        if client_profile is None:
            return APIResponse.error(
                message="Client profile not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        if ProductEnquiry.objects.filter(
            product=product, client=client_profile
        ).exists():
            return APIResponse.error(
                message="You have already sent an enquiry for this product.",
                code=ErrorCode.ALREADY_EXISTS,
            )

        message = request.data.get("message", "")

        with transaction.atomic():
            enquiry = ProductEnquiry.objects.create(
                product=product,
                client=client_profile,
                message=message,
            )
            Product.objects.filter(pk=pk).update(enquiry_count=F("enquiry_count") + 1)

        owner_user = product.get_owner_user()
        send_push_notification.delay(
            str(owner_user.id),
            "New Enquiry",
            f"{client_profile.display_name} enquired about {product.name}",
            {
                "type": "marketplace_enquiry",
                "product_id": str(product.id),
            },
        )
        Notification.objects.create(
            recipient=owner_user,
            notification_type=Notification.NotificationType.MARKETPLACE_ENQUIRY,
            title="New Enquiry",
            body=f"{client_profile.display_name} enquired about {product.name}",
            data={"product_id": str(product.id)},
        )

        return APIResponse.created(
            data=ProductEnquirySerializer(enquiry).data,
            message="Enquiry sent.",
        )


@extend_schema(tags=["Marketplace"])
class ProductEnquiryListView(APIView):
    """GET — list all enquiries for a product (owner only)."""

    permission_classes = []

    @extend_schema(
        summary="List enquiries for a product",
        description=(
            "Returns all enquiries for the given product. "
            "Only the product owner may access."
        ),
        responses={
            200: OpenApiResponse(description="Paginated enquiry list"),
            403: OpenApiResponse(description="Not the owner"),
            404: OpenApiResponse(description="Product not found"),
        },
    )
    def get(self, request, pk):
        if not request.user.is_authenticated:
            return APIResponse.error(
                message="Authentication required.",
                code=ErrorCode.AUTHENTICATION_REQUIRED,
                status_code=401,
            )
        try:
            product = Product.objects.select_related("trainer__user", "gym__user").get(
                pk=pk
            )
        except Product.DoesNotExist:
            return APIResponse.error(
                message="Product not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        if not _is_product_owner(product, request.user):
            return APIResponse.error(
                message="You do not own this listing.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        qs = (
            ProductEnquiry.objects.filter(product=product)
            .select_related("client", "product")
            .order_by("-created_at")
        )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = ProductEnquirySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema(tags=["Marketplace"])
class ProductEnquiryRespondView(APIView):
    """POST — respond to an enquiry (owner only)."""

    permission_classes = []

    @extend_schema(
        summary="Respond to a product enquiry",
        description=(
            "The product owner responds to a client enquiry. "
            "Sets trainer_response, status, and responded_at. "
            "The client receives a push notification."
        ),
        responses={
            200: OpenApiResponse(description="Enquiry updated with response"),
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Not the owner"),
            404: OpenApiResponse(description="Product or enquiry not found"),
        },
    )
    def post(self, request, pk, enq_pk):
        if not request.user.is_authenticated:
            return APIResponse.error(
                message="Authentication required.",
                code=ErrorCode.AUTHENTICATION_REQUIRED,
                status_code=401,
            )
        try:
            product = Product.objects.select_related("trainer__user", "gym__user").get(
                pk=pk
            )
        except Product.DoesNotExist:
            return APIResponse.error(
                message="Product not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        if not _is_product_owner(product, request.user):
            return APIResponse.error(
                message="You do not own this listing.",
                code=ErrorCode.PERMISSION_DENIED,
                status_code=403,
            )

        try:
            enquiry = ProductEnquiry.objects.select_related(
                "client__user", "product"
            ).get(pk=enq_pk, product=product)
        except ProductEnquiry.DoesNotExist:
            return APIResponse.error(
                message="Enquiry not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        response_text = request.data.get("response", "")
        new_status = request.data.get("status", ProductEnquiry.Status.RESPONDED)

        valid_statuses = (ProductEnquiry.Status.RESPONDED, ProductEnquiry.Status.CLOSED)
        if new_status not in valid_statuses:
            return APIResponse.error(
                message=f"Status must be one of: {', '.join(valid_statuses)}.",
                code=ErrorCode.VALIDATION_ERROR,
            )

        enquiry.trainer_response = response_text
        enquiry.status = new_status
        enquiry.responded_at = timezone.now()
        enquiry.save(update_fields=["trainer_response", "status", "responded_at"])

        seller_name = product.get_owner_profile()
        if hasattr(seller_name, "full_name"):
            seller_name = seller_name.full_name
        else:
            seller_name = seller_name.gym_name

        client_user = enquiry.client.user
        send_push_notification.delay(
            str(client_user.id),
            "Response to your enquiry",
            f"{seller_name} responded to your enquiry about {product.name}",
            {
                "type": "enquiry_response",
                "product_id": str(product.id),
            },
        )
        Notification.objects.create(
            recipient=client_user,
            notification_type=Notification.NotificationType.ENQUIRY_RESPONSE,
            title="Response to your enquiry",
            body=f"{seller_name} responded to your enquiry about {product.name}",
            data={"product_id": str(product.id)},
        )

        return APIResponse.success(
            data=ProductEnquirySerializer(enquiry).data,
            message="Response sent.",
        )
