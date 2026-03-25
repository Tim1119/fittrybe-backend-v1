"""
Email utilities for the clients app.
All emails send both a plain-text fallback and an HTML version
using EmailMultiAlternatives.
"""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def _mobile_url():
    return getattr(settings, "MOBILE_URL", "fittrybe://")


def send_client_reminder_email(membership, owner_name):
    """
    Send a payment/renewal reminder to the client (HTML + plain text).

    Args:
        membership: ClientMembership instance
        owner_name: display name of trainer or gym
    """
    client_email = membership.client.user.email
    client_name = membership.client.display_name or client_email.split("@")[0]
    mobile_url = _mobile_url()

    context = {
        "client_name": client_name,
        "trainer_or_gym_name": owner_name,
        "renewal_date": membership.renewal_date or "not set",
        "payment_amount": membership.payment_amount,
        "payment_currency": membership.payment_currency,
        "payment_notes": membership.payment_notes,
        "web_url": settings.FRONTEND_URL,
        "mobile_url": mobile_url,
    }

    html_content = render_to_string("clients/emails/payment_reminder.html", context)
    text_content = render_to_string("clients/emails/payment_reminder.txt", context)

    email = EmailMultiAlternatives(
        subject=f"Membership reminder from {owner_name}",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[client_email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=True)
