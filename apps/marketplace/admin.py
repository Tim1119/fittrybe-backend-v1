from django.contrib import admin

from apps.marketplace.models import Product, ProductEnquiry


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "category",
        "status",
        "price",
        "is_featured",
        "view_count",
        "enquiry_count",
        "created_at",
    ]
    list_filter = ["category", "status", "is_featured"]
    search_fields = ["name", "description"]
    actions = ["make_active", "make_archived", "make_featured"]

    @admin.action(description="Mark selected as Active")
    def make_active(self, request, queryset):
        queryset.update(status=Product.Status.ACTIVE)

    @admin.action(description="Mark selected as Archived")
    def make_archived(self, request, queryset):
        queryset.update(status=Product.Status.ARCHIVED)

    @admin.action(description="Mark selected as Featured")
    def make_featured(self, request, queryset):
        queryset.update(is_featured=True)


@admin.register(ProductEnquiry)
class ProductEnquiryAdmin(admin.ModelAdmin):
    list_display = ["product", "client", "status", "responded_at", "created_at"]
    list_filter = ["status"]
    search_fields = ["product__name", "client__username"]
