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


def test_redacts_private_key_body():
    pem = "-----BEGIN PRIVATE KEY-----\nsecret-key-material\n-----END PRIVATE KEY-----"
    result = scrub(pem)
    assert result == "[REDACTED_PRIVATE_KEY]"
    assert "secret-key-material" not in result


def test_redacts_github_tokens():
    result = scrub("ghp_1234567890abcdefghijklmnopqrstuv and github_pat_1234567890abcdefghijkl")
    assert result.count("[REDACTED_GITHUB_TOKEN]") == 2
    assert "ghp_" not in result
    assert "github_pat_" not in result


def test_redacts_slack_and_discord_tokens():
    discord_token = ".".join(
        [
            "MTIzNDU2Nzg5MDEyMzQ1Njc4OTAx",
            "MTIzNDU",
            "abcdef_12345678901234567890",
        ]
    )
    result = scrub(
        f"xoxb-1234567890-abcdef and {discord_token}"
    )
    assert result.count("[REDACTED_CHAT_TOKEN]") == 2


def test_redacts_database_url_with_credentials():
    result = scrub("DATABASE_URL=postgres://app:supersecret@db.example.test:5432/app")
    assert result == "DATABASE_URL=[REDACTED_DATABASE_URL]"


def test_preserves_database_url_without_credentials():
    value = "postgres://localhost:5432/app"
    assert value in scrub(value)


def test_redacts_oauth_and_container_credentials():
    result = scrub(
        "client_secret=oauth-secret-value "
        "DOCKER_PASSWORD=registry-password-value "
        '"auth": "dXNlcjpwYXNzd29yZA=="'
    )
    assert "[REDACTED_OAUTH_SECRET]" in result
    assert "[REDACTED_CONTAINER_CREDENTIAL]" in result
    assert "oauth-secret-value" not in result
    assert "registry-password-value" not in result


def test_preserves_normal_versions_and_text():
    text = "client_id=public-client-123 Version 1.2.3.4"
    assert scrub(text) == text


def test_plain_text_unchanged():
    text = "Just a normal log line with no secrets"
    assert scrub(text) == text
