from django.urls import path

from apps.marketplace.views import (
    MyProductsView,
    ProductDetailView,
    ProductEnquireView,
    ProductEnquiryListView,
    ProductEnquiryRespondView,
    ProductImageDeleteView,
    ProductImageUploadView,
    ProductListCreateView,
)

urlpatterns = [
    path("products/", ProductListCreateView.as_view()),
    path("products/my/", MyProductsView.as_view()),
    path("products/<int:pk>/", ProductDetailView.as_view()),
    path("products/<int:pk>/images/", ProductImageUploadView.as_view()),
    path("products/<int:pk>/images/delete/", ProductImageDeleteView.as_view()),
    path("products/<int:pk>/enquire/", ProductEnquireView.as_view()),
    path("products/<int:pk>/enquiries/", ProductEnquiryListView.as_view()),
    path(
        "products/<int:pk>/enquiries/<int:enq_pk>/respond/",
        ProductEnquiryRespondView.as_view(),
    ),
]
