"""Tests for version consistency."""

from _version import __version__
from gitlab.client import GitLabClient


class TestVersionConsistency:
    def test_version_is_semver(self):
        parts = __version__.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_user_agent_contains_version(self):
        client = GitLabClient()
        assert __version__ in client.headers["User-Agent"]
