"""Tests for LocalAIService secret scrubbing and privacy features."""

from services.local_ai_service import LocalAIService


def _fresh() -> LocalAIService:
    LocalAIService._instance = None
    return LocalAIService()


class TestScrubSecrets:
    def test_redacts_gitlab_token(self):
        result = _fresh().scrub_secrets("Token: glpat-xxxxxxxxxxxxxxxxxxxx")
        assert "[REDACTED_GITLAB_TOKEN]" in result
        assert "glpat-" not in result

    def test_redacts_aws_access_key(self):
        result = _fresh().scrub_secrets("Key: AKIAIOSFODNN7EXAMPLE")
        assert "[REDACTED_AWS_KEY]" in result
        assert "AKIAIOSFODNN7EXAMPLE" not in result

    def test_redacts_private_ipv4(self):
        result = _fresh().scrub_secrets("Server at 10.0.1.50 and 192.168.1.1")
        assert "[REDACTED_IP]" in result
        assert "10.0.1.50" not in result

    def test_does_not_redact_version_numbers(self):
        result = _fresh().scrub_secrets("Version 1.2.3.4 is installed")
        assert "1.2.3.4" in result
        assert "[REDACTED_IP]" not in result

    def test_does_not_redact_git_sha(self):
        result = _fresh().scrub_secrets("Commit abc123def4567890abcdef1234567890abcdef12")
        assert "abc123def4567890abcdef1234567890abcdef12" in result
        assert "[REDACTED_HEX_TOKEN]" not in result

    def test_redacts_jwt_token(self):
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = _fresh().scrub_secrets(f"Bearer {jwt}")
        assert "[REDACTED_JWT]" in result
        assert "eyJhbGciOiJIUzI1Ni" not in result

    def test_redacts_private_key_header(self):
        result = _fresh().scrub_secrets("-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEAx...")
        assert "[REDACTED_PRIVATE_KEY]" in result
        assert "-----BEGIN RSA PRIVATE KEY-----" not in result

    def test_redacts_password_assignment(self):
        result = _fresh().scrub_secrets("password = super_secret_value123")
        assert "[REDACTED]" in result
        assert "super_secret_value123" not in result

    def test_preserves_structured_tokens_in_generic_regex(self):
        """Generic token regex must not overwrite already-specific redactions."""
        result = _fresh().scrub_secrets(
            "Token: glpat-xxxxxxxxxxxxxxxxxxxx and Key: AKIAIOSFODNN7EXAMPLE"
        )
        assert "[REDACTED_GITLAB_TOKEN]" in result
        assert "[REDACTED_AWS_KEY]" in result
        assert "Token: [REDACTED]" not in result
        assert "Key: [REDACTED]" not in result

    def test_plain_text_unchanged(self):
        text = "Just a normal log line with no secrets"
        assert _fresh().scrub_secrets(text) == text
