from django.urls import path

from . import views

app_name = "subscriptions"

urlpatterns = [
    path("plans/", views.PlansView.as_view(), name="plans"),
    path("status/", views.SubscriptionStatusView.as_view(), name="status"),
    path(
        "checkout/paystack/",
        views.PaystackCheckoutView.as_view(),
        name="checkout-paystack",
    ),
    path(
        "checkout/stripe/",
        views.StripeCheckoutView.as_view(),
        name="checkout-stripe",
    ),
    path(
        "webhook/paystack/",
        views.PaystackWebhookView.as_view(),
        name="webhook-paystack",
    ),
    path(
        "webhook/stripe/",
        views.StripeWebhookView.as_view(),
        name="webhook-stripe",
    ),
    path("cancel/", views.CancelSubscriptionView.as_view(), name="cancel"),
    path("billing/", views.BillingHistoryView.as_view(), name="billing-history"),
]
