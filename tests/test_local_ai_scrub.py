"""Tests for LocalAIService.scrub_secrets — pure regex, no network."""

from services.local_ai_service import LocalAIService


def scrub(text: str) -> str:
    return LocalAIService().scrub_secrets(text)


def test_redacts_gitlab_token():
    result = scrub("token: glpat-abc123456789012345678")
    assert "glpat-" not in result
    assert "[REDACTED_GITLAB_TOKEN]" in result


def test_redacts_aws_access_key():
    result = scrub("key: AKIAIOSFODNN7EXAMPLE")
    assert "AKIAIOSFODNN7EXAMPLE" not in result
    assert "[REDACTED_AWS_KEY]" in result


def test_redacts_jwt():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.SomeSignatureHere"
    result = scrub(f"Authorization: Bearer {jwt}")
    assert "eyJhbGciOiJIUzI1NiJ9" not in result
    assert "[REDACTED_JWT]" in result


def test_redacts_private_ip():
    result = scrub("host: 192.168.1.100")
    assert "192.168.1.100" not in result
    assert "[REDACTED_IP]" in result


def test_does_not_redact_public_ip():
    result = scrub("server: 8.8.8.8")
    assert "8.8.8.8" in result


def test_redacts_generic_password():
    result = scrub("password: supersecretvalue123")
    assert "supersecretvalue123" not in result
    assert "[REDACTED]" in result


def test_skips_already_redacted_value():
    already = "password: [REDACTED]"
    result = scrub(already)
    assert result == already


def test_redacts_pem_private_key_header():
    result = scrub("-----BEGIN RSA PRIVATE KEY-----")
    assert "[REDACTED_PRIVATE_KEY]" in result


def test_plain_text_unchanged():
    text = "Just a normal log line with no secrets"
    assert scrub(text) == text
