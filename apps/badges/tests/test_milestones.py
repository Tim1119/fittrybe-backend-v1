"""
TDD tests for milestone badge Celery tasks.
"""

import datetime
from unittest.mock import patch

import pytest

from apps.accounts.tests.factories import TrainerFactory
from apps.badges.models import BadgeAssignment
from apps.profiles.tests.factories import ClientProfileFactory, TrainerProfileFactory
from apps.sessions.models import Session
from apps.sessions.tests.factories import SessionFactory


def _make_sessions(trainer_profile, client_profile, count, status="completed"):
    today = datetime.date.today()
    for i in range(count):
        SessionFactory(
            trainer=trainer_profile,
            client=client_profile,
            status=status,
            session_date=today - datetime.timedelta(days=i),
        )


# ──────────────────────────────────────────────────────────────────────────────
# check_milestone_badges
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCheckMilestoneBadges:

    def test_awards_first_session_badge_at_total_1(self):
        from apps.badges.tasks import check_milestone_badges

        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        client_profile = ClientProfileFactory()

        _make_sessions(trainer_profile, client_profile, 1)

        with (
            patch("apps.badges.tasks.post_badge_to_chatroom") as mock_chat,
            patch("apps.notifications.tasks.send_push_notification") as mock_push,
        ):
            check_milestone_badges(str(client_profile.id), str(trainer_profile.id))

        assert BadgeAssignment.objects.filter(
            client=client_profile,
            badge__name="First Session",
        ).exists()
        mock_chat.delay.assert_called_once()
        mock_push.delay.assert_called_once()

    def test_awards_5_sessions_badge_at_total_5(self):
        from apps.badges.tasks import check_milestone_badges

        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        client_profile = ClientProfileFactory()

        _make_sessions(trainer_profile, client_profile, 5)

        with (
            patch("apps.badges.tasks.post_badge_to_chatroom"),
            patch("apps.notifications.tasks.send_push_notification"),
        ):
            check_milestone_badges(str(client_profile.id), str(trainer_profile.id))

        assert BadgeAssignment.objects.filter(
            client=client_profile,
            badge__name="5 Sessions",
        ).exists()

    def test_awards_10_sessions_badge_at_total_10(self):
        from apps.badges.tasks import check_milestone_badges

        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        client_profile = ClientProfileFactory()

        _make_sessions(trainer_profile, client_profile, 10)

        with (
            patch("apps.badges.tasks.post_badge_to_chatroom"),
            patch("apps.notifications.tasks.send_push_notification"),
        ):
            check_milestone_badges(str(client_profile.id), str(trainer_profile.id))

        assert BadgeAssignment.objects.filter(
            client=client_profile,
            badge__name="10 Sessions",
        ).exists()

    def test_no_badge_at_non_milestone_count(self):
        from apps.badges.tasks import check_milestone_badges

        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        client_profile = ClientProfileFactory()

        for n in [3, 7, 11]:
            # Clean up previous sessions
            Session.all_objects.filter(
                trainer=trainer_profile, client=client_profile
            ).delete()
            BadgeAssignment.objects.filter(client=client_profile).delete()

            _make_sessions(trainer_profile, client_profile, n)
            with (
                patch("apps.badges.tasks.post_badge_to_chatroom"),
                patch("apps.notifications.tasks.send_push_notification"),
            ):
                check_milestone_badges(str(client_profile.id), str(trainer_profile.id))

            assert BadgeAssignment.objects.filter(client=client_profile).count() == 0

    def test_does_not_duplicate_badge_already_awarded(self):
        from apps.badges.tasks import check_milestone_badges

        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        client_profile = ClientProfileFactory()

        _make_sessions(trainer_profile, client_profile, 1)

        with (
            patch("apps.badges.tasks.post_badge_to_chatroom"),
            patch("apps.notifications.tasks.send_push_notification"),
        ):
            check_milestone_badges(str(client_profile.id), str(trainer_profile.id))
            check_milestone_badges(str(client_profile.id), str(trainer_profile.id))

        assert (
            BadgeAssignment.objects.filter(
                client=client_profile,
                badge__name="First Session",
            ).count()
            == 1
        )

    def test_graceful_on_missing_client(self):
        from apps.badges.tasks import check_milestone_badges

        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)

        # Should not raise — 999999 is a non-existent integer id
        check_milestone_badges("999999", str(trainer_profile.id))

    def test_only_completed_sessions_count(self):
        from apps.badges.tasks import check_milestone_badges

        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer)
        client_profile = ClientProfileFactory()

        # 1 completed + 1 cancelled = should NOT award "First Session" yet
        _make_sessions(trainer_profile, client_profile, 1, status="completed")
        # The cancelled one shouldn't matter, but let's also cancel one
        _make_sessions(trainer_profile, client_profile, 1, status="cancelled")

        with (
            patch("apps.badges.tasks.post_badge_to_chatroom"),
            patch("apps.notifications.tasks.send_push_notification"),
        ):
            check_milestone_badges(str(client_profile.id), str(trainer_profile.id))

        # Only 1 completed → "First Session" SHOULD be awarded
        assert BadgeAssignment.objects.filter(
            client=client_profile,
            badge__name="First Session",
        ).exists()


# ──────────────────────────────────────────────────────────────────────────────
# award_weekly_top_badges
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAwardWeeklyTopBadges:

    def test_awards_top_3_per_trainer(self):
        from apps.badges.tasks import award_weekly_top_badges

        trainer = TrainerFactory()
        trainer_profile = TrainerProfileFactory(user=trainer, is_published=True)
        clients = [ClientProfileFactory() for _ in range(4)]
        today = datetime.date.today()

        # client[0] gets 5 sessions, [1] gets 3, [2] gets 2, [3] gets 1
        for i, count in enumerate([5, 3, 2, 1]):
            for j in range(count):
                SessionFactory(
                    trainer=trainer_profile,
                    client=clients[i],
                    status="completed",
                    session_date=today - datetime.timedelta(days=j),
                )

        with patch("apps.badges.tasks.post_badge_to_chatroom"):
            award_weekly_top_badges()

        assert BadgeAssignment.objects.filter(
            trainer=trainer_profile,
            badge__name="Weekly Top 1",
            client=clients[0],
        ).exists()
        assert BadgeAssignment.objects.filter(
            trainer=trainer_profile,
            badge__name="Weekly Top 2",
            client=clients[1],
        ).exists()
        assert BadgeAssignment.objects.filter(
            trainer=trainer_profile,
            badge__name="Weekly Top 3",
            client=clients[2],
        ).exists()
        # 4th client should not get a badge
        assert not BadgeAssignment.objects.filter(client=clients[3]).exists()

    def test_skips_trainers_with_no_sessions_this_week(self):
        from apps.badges.tasks import award_weekly_top_badges

        trainer = TrainerFactory()
        TrainerProfileFactory(user=trainer, is_published=True)

        with patch("apps.badges.tasks.post_badge_to_chatroom") as mock_chat:
            award_weekly_top_badges()

        assert BadgeAssignment.objects.count() == 0
        mock_chat.delay.assert_not_called()
