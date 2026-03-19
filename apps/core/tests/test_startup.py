"""
Tests for apps/core/startup.py — environment validation.
"""

import os
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.core.startup import validate_environment


class TestValidateEnvironment:
    def test_passes_with_all_vars_set(self):
        # All required vars are present in the test environment (.env)
        validate_environment()

    def test_raises_when_secret_key_missing(self):
        env = os.environ.copy()
        env["SECRET_KEY"] = ""
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ImproperlyConfigured) as exc_info:
                validate_environment()
        assert "SECRET_KEY" in str(exc_info.value)

    def test_raises_when_frontend_url_missing(self):
        env = os.environ.copy()
        env["FRONTEND_URL"] = ""
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ImproperlyConfigured) as exc_info:
                validate_environment()
        assert "FRONTEND_URL" in str(exc_info.value)

    def test_lists_all_missing_vars_in_message(self):
        env = os.environ.copy()
        env["SECRET_KEY"] = ""
        env["FRONTEND_URL"] = ""
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ImproperlyConfigured) as exc_info:
                validate_environment()
        msg = str(exc_info.value)
        assert "SECRET_KEY" in msg
        assert "FRONTEND_URL" in msg

    def test_raises_when_default_from_email_missing(self):
        env = os.environ.copy()
        env["DEFAULT_FROM_EMAIL"] = ""
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ImproperlyConfigured) as exc_info:
                validate_environment()
        assert "DEFAULT_FROM_EMAIL" in str(exc_info.value)
