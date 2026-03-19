"""
Stripe payment gateway client.
"""

import stripe
from django.conf import settings


class StripeGateway:
    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY

    def create_customer(self, email, metadata=None):
        return stripe.Customer.create(email=email, metadata=metadata or {})

    def create_checkout_session(self, customer_id, price_id, success_url, cancel_url):
        return stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
        )

    def verify_webhook(self, payload, sig_header):
        return stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )

    def cancel_subscription(self, subscription_id):
        return stripe.Subscription.delete(subscription_id)
