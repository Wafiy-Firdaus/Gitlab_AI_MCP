import pytest
from pydantic import ValidationError

from config import Settings


def test_settings_reject_cleartext_remote_gitlab_url():
    with pytest.raises(ValidationError, match="must use HTTPS"):
        Settings(GITLAB_URL="http://gitlab.example.com", GITLAB_TOKEN="test-token")


def test_settings_allow_local_cleartext_gitlab_url():
    settings = Settings(GITLAB_URL="http://localhost:8080", GITLAB_TOKEN="test-token")

    assert settings.gitlab_url == "http://localhost:8080"
