from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    # GitLab Settings
    gitlab_url: str = Field(..., alias="GITLAB_URL")
    gitlab_token: str = Field(..., alias="GITLAB_TOKEN")

    gitlab_max_retries: int = Field(3, alias="GITLAB_MAX_RETRIES")
    gitlab_retry_delay: float = Field(1.0, alias="GITLAB_RETRY_DELAY")
    gitlab_read_only: bool = Field(False, alias="GITLAB_READ_ONLY")
    debug: bool = Field(False, alias="DEBUG")

    # Local AI Settings (Ollama)
    local_ai_url: str = Field("http://localhost:11434", alias="LOCAL_AI_URL")
    local_ai_model: str = Field("llama3.1:8b", alias="LOCAL_AI_MODEL")

    @field_validator("gitlab_url")
    @classmethod
    def validate_gitlab_url(cls, value: str) -> str:
        parsed = urlparse(value)
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in local_hosts
        ):
            raise ValueError("GITLAB_URL must use HTTPS, except for local development hosts")
        if not parsed.netloc:
            raise ValueError("GITLAB_URL must include a valid host")
        return value.rstrip("/")

    model_config = SettingsConfigDict(
        env_file=str(DEFAULT_ENV_FILE), env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()  # type: ignore[call-arg]
