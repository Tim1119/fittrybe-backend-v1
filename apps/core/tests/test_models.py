"""
Tests for core abstract models via concrete implementations.

SoftDeleteModel / TimeStampedModel / BaseModel are abstract, so they are
tested through the concrete models that inherit from them:
  - PlanConfig   (BaseModel)
  - Subscription (BaseModel)
  - TrainerProfile (BaseModel)
"""

import pytest

from apps.accounts.tests.factories import TrainerFactory
from apps.subscriptions.models import PlanConfig, Subscription
from apps.subscriptions.tests.factories import BasicPlanFactory, SubscriptionFactory


# ---------------------------------------------------------------------------
# SoftDeleteModel — tested via PlanConfig (BaseModel subclass)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestSoftDeleteModel:
    def test_delete_sets_deleted_at_not_removes_row(self):
        plan = BasicPlanFactory()
        pk = plan.pk
        plan.delete()
        # Row still exists in all_objects
        assert PlanConfig.all_objects.filter(pk=pk).exists()
        plan.refresh_from_db()
        assert plan.deleted_at is not None

    def test_restore_clears_deleted_at(self):
        plan = BasicPlanFactory()
        plan.delete()
        plan.restore()
        plan.refresh_from_db()
        assert plan.deleted_at is None

    def test_is_deleted_true_after_delete(self):
        plan = BasicPlanFactory()
        plan.delete()
        plan.refresh_from_db()
        assert plan.is_deleted is True

    def test_is_deleted_false_before_delete(self):
        plan = BasicPlanFactory()
        assert plan.is_deleted is False

    def test_objects_manager_excludes_deleted(self):
        BasicPlanFactory()  # basic — visible
        # Delete basic, create a variant to test exclusion
        plan = PlanConfig.objects.get(plan="basic")
        plan.delete()
        assert not PlanConfig.objects.filter(plan="basic").exists()

    def test_all_objects_manager_includes_deleted(self):
        plan = BasicPlanFactory()
        plan.delete()
        assert PlanConfig.all_objects.filter(pk=plan.pk).exists()

    def test_hard_delete_removes_from_database(self):
        user = TrainerFactory()
        sub = SubscriptionFactory(user=user)
        pk = sub.pk
        sub.hard_delete()
        assert not Subscription.all_objects.filter(pk=pk).exists()


# ---------------------------------------------------------------------------
# TimeStampedModel — created_at / updated_at
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestTimeStampedModel:
    def test_created_at_is_set_on_create(self):
        plan = BasicPlanFactory()
        assert plan.created_at is not None

    def test_updated_at_is_set_on_create(self):
        plan = BasicPlanFactory()
        assert plan.updated_at is not None

    def test_updated_at_changes_on_save(self):
        plan = BasicPlanFactory()
        original = plan.updated_at
        plan.description = "updated description"
        plan.save(update_fields=["description"])
        plan.refresh_from_db()
        assert plan.updated_at >= original


# ---------------------------------------------------------------------------
# BaseModel — inherits both SoftDelete and TimeStamped
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestBaseModel:
    def test_base_model_has_soft_delete_via_subscription(self):
        user = TrainerFactory()
        sub = SubscriptionFactory(user=user)
        sub.delete()
        sub.refresh_from_db()
        assert sub.is_deleted is True

    def test_base_model_has_timestamps_via_subscription(self):
        user = TrainerFactory()
        sub = SubscriptionFactory(user=user)
        assert sub.created_at is not None
        assert sub.updated_at is not None

    def test_soft_deleted_objects_excluded_from_default_manager(self):
        user = TrainerFactory()
        sub = SubscriptionFactory(user=user)
        pk = sub.pk
        sub.delete()
        assert not Subscription.objects.filter(pk=pk).exists()
        assert Subscription.all_objects.filter(pk=pk).exists()
