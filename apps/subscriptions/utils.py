"""
Subscription utility functions.
"""

from datetime import timedelta

from django.utils import timezone


def create_trial_subscription(user):
    """
    Create a trial subscription for a trainer or gym user.
    Idempotent — returns the existing subscription if one already exists.
    """
    from apps.subscriptions.models import PlanConfig, Subscription

    if hasattr(user, "subscription"):
        return user.subscription

    plan = PlanConfig.get_for_role(user.role)
    return Subscription.objects.create(
        user=user,
        plan=plan,
        status=Subscription.Status.TRIAL,
        trial_end=timezone.now() + timedelta(days=plan.trial_days),
    )
