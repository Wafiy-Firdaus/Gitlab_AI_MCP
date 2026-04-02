from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    # GitLab Settings
    gitlab_url: str = Field(..., alias="GITLAB_URL")
    gitlab_token: str = Field(..., alias="GITLAB_TOKEN")
    debug: bool = Field(False, alias="DEBUG")
    
    # Local AI Settings (Ollama)
    local_ai_url: str = Field("http://localhost:11434", alias="LOCAL_AI_URL")
    local_ai_model: str = Field("llama3.1:8b", alias="LOCAL_AI_MODEL")
    
    model_config = SettingsConfigDict(
        env_file=str(DEFAULT_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
