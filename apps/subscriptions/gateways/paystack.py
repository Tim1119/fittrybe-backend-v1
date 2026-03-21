"""
Paystack payment gateway client.
"""

import hashlib
import hmac

import requests
from django.conf import settings

PAYSTACK_BASE_URL = "https://api.paystack.co"


class PaystackGateway:
    def __init__(self):
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    def initialize_transaction(self, email, amount_kobo, metadata=None, plan=None):
        payload = {
            "email": email,
            "amount": amount_kobo,
            "metadata": metadata or {},
            "callback_url": f"{settings.FRONTEND_URL}/subscription/callback",
        }
        if plan:
            payload["plan"] = plan
        response = requests.post(
            f"{PAYSTACK_BASE_URL}/transaction/initialize",
            json=payload,
            headers=self.headers,
            timeout=30,
        )
        return response.json()

    def verify_transaction(self, reference):
        response = requests.get(
            f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
            headers=self.headers,
            timeout=30,
        )
        return response.json()

    def create_subscription(self, customer_code, plan_code):
        payload = {
            "customer": customer_code,
            "plan": plan_code,
        }
        response = requests.post(
            f"{PAYSTACK_BASE_URL}/subscription",
            json=payload,
            headers=self.headers,
            timeout=30,
        )
        return response.json()

    def verify_webhook(self, payload, signature):
        expected = hmac.new(
            self.secret_key.encode("utf-8"), payload, hashlib.sha512
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
