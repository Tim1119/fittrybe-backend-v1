"""
Marketplace serializers.
"""

from decimal import Decimal

from rest_framework import serializers

from apps.marketplace.models import Product, ProductEnquiry


class SellerSerializer(serializers.Serializer):
    """Read-only representation of the product owner (trainer or gym)."""

    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()
    slug = serializers.CharField()
    avg_rating = serializers.FloatField()
    seller_type = serializers.SerializerMethodField()

    def get_name(self, obj):
        if hasattr(obj, "full_name"):
            return obj.full_name
        return obj.gym_name

    def get_photo_url(self, obj):
        if hasattr(obj, "profile_photo_url"):
            return obj.profile_photo_url
        return obj.logo_url

    def get_seller_type(self, obj):
        if hasattr(obj, "full_name"):
            return "trainer"
        return "gym"


class ProductPublicSerializer(serializers.ModelSerializer):
    """Public-facing serializer — for browsing. Excludes internal fields."""

    seller = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "category",
            "price",
            "currency",
            "status",
            "images",
            "is_featured",
            "view_count",
            "enquiry_count",
            "seller",
            "created_at",
        ]

    def get_seller(self, obj):
        profile = obj.get_owner_profile()
        if profile is None:
            return None
        return SellerSerializer(profile).data


class ProductSerializer(serializers.ModelSerializer):
    """Full serializer for the product owner."""

    seller = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "category",
            "price",
            "currency",
            "status",
            "images",
            "is_featured",
            "view_count",
            "enquiry_count",
            "seller",
            "created_at",
            "updated_at",
        ]

    def get_seller(self, obj):
        profile = obj.get_owner_profile()
        if profile is None:
            return None
        return SellerSerializer(profile).data


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Writable serializer for create/update operations."""

    class Meta:
        model = Product
        fields = [
            "name",
            "description",
            "category",
            "price",
            "currency",
            "status",
            "images",
        ]
        extra_kwargs = {
            "description": {"required": False},
            "currency": {"required": False},
            "status": {"required": False},
            "images": {"required": False},
        }

    def validate_images(self, value):
        if len(value) > 5:
            raise serializers.ValidationError("A product can have at most 5 images.")
        return value

    def validate_price(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("Price must be greater than zero.")
        return value


class ProductEnquirySerializer(serializers.ModelSerializer):
    """Serializer for product enquiries."""

    product = serializers.SerializerMethodField()
    client = serializers.SerializerMethodField()

    class Meta:
        model = ProductEnquiry
        fields = [
            "id",
            "product",
            "client",
            "message",
            "status",
            "trainer_response",
            "responded_at",
            "created_at",
        ]

    def get_product(self, obj):
        return {"id": obj.product.id, "name": obj.product.name}

    def get_client(self, obj):
        return {
            "display_name": obj.client.display_name,
            "username": obj.client.username,
        }
