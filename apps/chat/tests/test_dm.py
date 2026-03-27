"""
CHAT-02 + CHAT-03 — DM tests.
"""

import pytest

from apps.chat.models import DirectMessageThread
from apps.chat.tests.conftest import (
    auth_client,
    make_client_user,
    make_membership,
    make_trainer_user,
)


def _setup_community_pair():
    """Returns trainer, client1, client2 sharing a community."""
    t_user, t_profile = make_trainer_user(email="dm_trainer@test.com")
    c1_user, c1_profile = make_client_user(email="dm_client1@test.com")
    c2_user, c2_profile = make_client_user(email="dm_client2@test.com")
    make_membership(c1_profile, trainer=t_profile)
    make_membership(c2_profile, trainer=t_profile)
    return t_user, t_profile, c1_user, c1_profile, c2_user, c2_profile


@pytest.mark.django_db
def test_send_dm_creates_thread(db):
    t_user, _, c_user, _, _, _ = _setup_community_pair()
    c_api = auth_client(c_user)
    resp = c_api.post(f"/api/v1/chat/dm/{t_user.id}/", {"content": "Hello trainer"})
    assert resp.status_code == 201
    assert DirectMessageThread.objects.filter(
        user_1__in=[t_user, c_user], user_2__in=[t_user, c_user]
    ).exists()


@pytest.mark.django_db
def test_send_dm_outside_community_forbidden(db):
    _, _, _, _, c2_user, _ = _setup_community_pair()
    # Create an outsider with no shared community
    outsider, _ = make_client_user(email="outsider_dm@test.com")
    outsider_api = auth_client(outsider)
    resp = outsider_api.post(f"/api/v1/chat/dm/{c2_user.id}/", {"content": "Stranger"})
    assert resp.status_code == 403


@pytest.mark.django_db
def test_dm_thread_list_includes_unread_count(db):
    t_user, _, c_user, _, _, _ = _setup_community_pair()
    t_api = auth_client(t_user)
    c_api = auth_client(c_user)
    c_api.post(f"/api/v1/chat/dm/{t_user.id}/", {"content": "Hey!"})

    resp = t_api.get("/api/v1/chat/dm/threads/")
    assert resp.status_code == 200
    threads = resp.data["data"]
    assert len(threads) >= 1
    assert "unread_count" in threads[0]
    assert threads[0]["unread_count"] == 1


@pytest.mark.django_db
def test_dm_message_list_paginated_oldest_first(db):
    t_user, _, c_user, _, _, _ = _setup_community_pair()
    c_api = auth_client(c_user)
    c_api.post(f"/api/v1/chat/dm/{t_user.id}/", {"content": "First"})
    c_api.post(f"/api/v1/chat/dm/{t_user.id}/", {"content": "Second"})

    t_api = auth_client(t_user)
    resp = t_api.get(f"/api/v1/chat/dm/{c_user.id}/messages/")
    assert resp.status_code == 200
    messages = resp.data["data"]
    assert len(messages) == 2
    assert messages[0]["content"] == "First"
    assert messages[1]["content"] == "Second"


@pytest.mark.django_db
def test_getting_dm_messages_resets_unread(db):
    t_user, _, c_user, _, _, _ = _setup_community_pair()
    c_api = auth_client(c_user)
    c_api.post(f"/api/v1/chat/dm/{t_user.id}/", {"content": "Msg"})

    # Trainer retrieves messages
    t_api = auth_client(t_user)
    t_api.get(f"/api/v1/chat/dm/{c_user.id}/messages/")

    thread = DirectMessageThread.objects.get(
        user_1__in=[t_user, c_user], user_2__in=[t_user, c_user]
    )
    if thread.user_1_id == t_user.id:
        assert thread.user_1_unread == 0
    else:
        assert thread.user_2_unread == 0


@pytest.mark.django_db
def test_dm_mark_read_resets_unread_and_sets_read_at(db):
    t_user, _, c_user, _, _, _ = _setup_community_pair()
    c_api = auth_client(c_user)
    c_api.post(f"/api/v1/chat/dm/{t_user.id}/", {"content": "Unread"})

    t_api = auth_client(t_user)
    resp = t_api.post(f"/api/v1/chat/dm/{c_user.id}/read/")
    assert resp.status_code == 200

    thread = DirectMessageThread.objects.get(
        user_1__in=[t_user, c_user], user_2__in=[t_user, c_user]
    )
    if thread.user_1_id == t_user.id:
        assert thread.user_1_unread == 0
    else:
        assert thread.user_2_unread == 0

    msg = thread.messages.first()
    assert msg.read_at is not None
