"""
Email utilities for the clients app.
"""

from django.conf import settings
from django.core.mail import send_mail


def send_client_reminder_email(membership, owner_name):
    """
    Send a payment/renewal reminder to the client.

    Args:
        membership: ClientMembership instance
        owner_name: display name of trainer or gym
    """
    client_email = membership.client.user.email
    renewal_info = (
        f"Your renewal date is {membership.renewal_date}."
        if membership.renewal_date
        else "Please check with your trainer for your renewal date."
    )
    body = (
        f"Hi,\n\n"
        f"This is a reminder from {owner_name} at Fit Trybe.\n\n"
        f"{renewal_info}\n\n"
        f"Please ensure your membership is kept up to date.\n\n"
        f"Visit Fit Trybe: {settings.FRONTEND_URL}\n"
    )
    send_mail(
        subject=f"Membership reminder from {owner_name}",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[client_email],
        fail_silently=True,
    )
