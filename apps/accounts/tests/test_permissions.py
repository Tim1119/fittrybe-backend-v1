"""
Tests for custom permission classes.
"""

from unittest.mock import MagicMock

from apps.accounts.permissions import (
    IsClient,
    IsGym,
    IsTrainer,
    IsTrainerOrGym,
    IsVerified,
)


def _mock_user(role=None, authenticated=True, verified=True):
    user = MagicMock()
    user.is_authenticated = authenticated
    user.role = role
    user.is_email_verified = verified
    return user


def _request(role=None, authenticated=True, verified=True):
    req = MagicMock()
    req.user = _mock_user(role=role, authenticated=authenticated, verified=verified)
    return req


class TestIsTrainer:
    def test_allows_trainer(self):
        assert IsTrainer().has_permission(_request(role="trainer"), None) is True

    def test_blocks_gym(self):
        assert IsTrainer().has_permission(_request(role="gym"), None) is False

    def test_blocks_client(self):
        assert IsTrainer().has_permission(_request(role="client"), None) is False

    def test_blocks_anonymous(self):
        assert IsTrainer().has_permission(_request(authenticated=False), None) is False


class TestIsGym:
    def test_allows_gym(self):
        assert IsGym().has_permission(_request(role="gym"), None) is True

    def test_blocks_trainer(self):
        assert IsGym().has_permission(_request(role="trainer"), None) is False

    def test_blocks_client(self):
        assert IsGym().has_permission(_request(role="client"), None) is False

    def test_blocks_anonymous(self):
        assert IsGym().has_permission(_request(authenticated=False), None) is False


class TestIsClient:
    def test_allows_client(self):
        assert IsClient().has_permission(_request(role="client"), None) is True

    def test_blocks_trainer(self):
        assert IsClient().has_permission(_request(role="trainer"), None) is False

    def test_blocks_gym(self):
        assert IsClient().has_permission(_request(role="gym"), None) is False

    def test_blocks_anonymous(self):
        assert IsClient().has_permission(_request(authenticated=False), None) is False


class TestIsTrainerOrGym:
    def test_allows_trainer(self):
        assert IsTrainerOrGym().has_permission(_request(role="trainer"), None) is True

    def test_allows_gym(self):
        assert IsTrainerOrGym().has_permission(_request(role="gym"), None) is True

    def test_blocks_client(self):
        assert IsTrainerOrGym().has_permission(_request(role="client"), None) is False

    def test_blocks_anonymous(self):
        assert (
            IsTrainerOrGym().has_permission(_request(authenticated=False), None)
            is False
        )


class TestIsVerified:
    def test_allows_verified(self):
        assert IsVerified().has_permission(_request(verified=True), None) is True

    def test_blocks_unverified(self):
        assert IsVerified().has_permission(_request(verified=False), None) is False

    def test_blocks_anonymous(self):
        assert IsVerified().has_permission(_request(authenticated=False), None) is False
