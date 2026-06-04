"""Tests for scrub_secrets edge cases and resolve_ids_or_fail negative paths."""

from gitlab.client import GitLabClient
from services.gitlab_service import GitLabService
from services.local_ai_service import LocalAIService
from tools._utils import resolve_ids_or_fail


def _fresh_ai() -> LocalAIService:
    LocalAIService._instance = None
    return LocalAIService()


class TestScrubSecretsEdgeCases:
    def test_redacts_gitlab_token(self):
        result = _fresh_ai().scrub_secrets("token: glpat-abc123456789012345678")
        assert "[REDACTED_GITLAB_TOKEN]" in result
        assert "glpat-" not in result

    def test_redacts_aws_access_key(self):
        result = _fresh_ai().scrub_secrets("key: AKIAIOSFODNN7EXAMPLE")
        assert "[REDACTED_AWS_KEY]" in result

    def test_redacts_jwt(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.SomeSignatureHere"
        result = _fresh_ai().scrub_secrets(f"Authorization: Bearer {jwt}")
        assert "[REDACTED_JWT]" in result
        assert "eyJhbGciOiJIUzI1NiJ9" not in result

    def test_redacts_private_ip(self):
        result = _fresh_ai().scrub_secrets("host: 192.168.1.100")
        assert "192.168.1.100" not in result
        assert "[REDACTED_IP]" in result

    def test_does_not_redact_public_ip(self):
        result = _fresh_ai().scrub_secrets("server: 8.8.8.8")
        assert "8.8.8.8" in result

    def test_skips_already_redacted(self):
        already = "password: [REDACTED]"
        assert _fresh_ai().scrub_secrets(already) == already

    def test_plain_text_unchanged(self):
        text = "Normal log line with no secrets"
        assert _fresh_ai().scrub_secrets(text) == text

    def test_redacts_pem_header(self):
        result = _fresh_ai().scrub_secrets("-----BEGIN RSA PRIVATE KEY-----")
        assert "[REDACTED_PRIVATE_KEY]" in result

    def test_specific_redactions_not_consumed_by_generic(self):
        text = "Token: glpat-xxxxxxxxxxxxxxxxxxxx and Key: AKIAIOSFODNN7EXAMPLE"
        result = _fresh_ai().scrub_secrets(text)
        assert "[REDACTED_GITLAB_TOKEN]" in result
        assert "[REDACTED_AWS_KEY]" in result
        assert "Token: [REDACTED]" not in result
        assert "Key: [REDACTED]" not in result


class TestResolveIdsOrFailNegativePaths:
    def _service(self) -> GitLabService:
        return GitLabService(GitLabClient())

    def test_returns_error_dict_when_all_none(self):
        result = resolve_ids_or_fail(self._service(), None, None, None, "issue_iid")
        assert isinstance(result, dict)
        assert "Error" in result["summary"]
        assert "key_findings" in result
        assert "next_action" in result

    def test_returns_error_dict_when_url_unrecognised(self):
        result = resolve_ids_or_fail(
            self._service(), "https://notgitlab.com/foo/bar", None, None, "mr_iid"
        )
        assert isinstance(result, dict)
        assert "Error" in result["summary"]

    def test_returns_tuple_when_ids_provided(self):
        result = resolve_ids_or_fail(self._service(), None, 42, 7, "mr_iid")
        assert result == (42, 7)

    def test_returns_tuple_when_valid_url(self):
        url = "https://gitlab.example.com/group/project/-/issues/10"
        result = resolve_ids_or_fail(self._service(), url, None, None, "issue_iid")
        assert isinstance(result, tuple)
        p_id, r_id = result
        assert p_id == "group/project"
        assert r_id == 10
