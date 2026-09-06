import re
from typing import Optional

import httpx
import structlog

from config import settings

logger = structlog.get_logger(__name__)


class LocalAIService:
    """
    Handles communication with local AI models (e.g., Ollama)
    to perform pre-processing, log triage, and secret scrubbing.
    """

    _instance: Optional["LocalAIService"] = None
    base_url: str
    model: str
    client: httpx.AsyncClient

    def __new__(cls) -> "LocalAIService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.base_url = settings.local_ai_url.rstrip("/")
            cls._instance.model = settings.local_ai_model
            cls._instance.client = httpx.AsyncClient(timeout=60.0)
        return cls._instance

    @classmethod
    async def aclose(cls) -> None:
        """Close the shared httpx client. Call on shutdown."""
        if cls._instance is not None:
            await cls._instance.client.aclose()
            cls._instance = None

    def scrub_secrets(self, text: str) -> str:
        """
        Redacts sensitive patterns (IPs, tokens, keys) locally
        to ensure privacy before any data reaches an external AI.
        """
        # Run specific high-confidence patterns FIRST to avoid generic regex overlap

        # Redact GitLab Tokens
        text = re.sub(r"glpat-[a-zA-Z0-9\-]{20,}", "[REDACTED_GITLAB_TOKEN]", text)
        # Redact GitHub tokens (classic, OAuth/app, and fine-grained tokens).
        text = re.sub(
            r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b",
            "[REDACTED_GITHUB_TOKEN]",
            text,
        )
        # Redact JWT tokens before chat tokens because JWTs also have three
        # dot-separated components.
        text = re.sub(
            r"eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*",
            "[REDACTED_JWT]",
            text,
        )
        # Redact Slack tokens and Discord bot tokens. Discord tokens have three
        # dot-separated components; requiring that shape avoids matching prose.
        text = re.sub(
            r"\bxox[baprs]-[A-Za-z0-9-]{10,}|"
            r"\bxapp-[0-9A-Za-z-]{10,}|"
            r"\bmfa\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b|"
            r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{20,}\b",
            "[REDACTED_CHAT_TOKEN]",
            text,
        )
        # Redact AWS Access Keys
        text = re.sub(r"AKIA[0-9A-Z]{16}", "[REDACTED_AWS_KEY]", text)
        # Redact AWS Secret Keys (basic)
        text = re.sub(
            r"aws_secret_access_key\s*[:=]\s*[a-zA-Z0-9/+=]{40}",
            "aws_secret_access_key: [REDACTED]",
            text,
            flags=re.IGNORECASE,
        )
        # Redact GCP service account keys
        text = re.sub(
            r"\"type\":\s*\"service_account\".*?\"private_key\":\s*\"-----BEGIN PRIVATE KEY-----.*?-----END PRIVATE KEY-----\"",
            '"type": "service_account", ... [REDACTED_GCP_KEY]',
            text,
            flags=re.DOTALL,
        )
        # Redact complete PEM/SSH private keys, including the body.  Matching
        # the closing marker prevents leaking the key material after the header.
        text = re.sub(
            r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----.*?"
            r"-----END (?:[A-Z0-9]+ )*PRIVATE KEY-----",
            "[REDACTED_PRIVATE_KEY]",
            text,
            flags=re.DOTALL,
        )
        # Keep the previous behavior for truncated logs containing only a
        # private-key header.
        text = re.sub(
            r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----",
            "[REDACTED_PRIVATE_KEY]",
            text,
        )
        # Redact database URLs only when they contain credentials.  This keeps
        # harmless references such as "postgres://localhost:5432/app" intact.
        text = re.sub(
            r"\b(?:jdbc:)?(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|"
            r"redis|rediss|mssql|sqlserver)://[^@\s\"'<>:/]+:[^@\s\"<>]+@[^"
            r"\s\"'<>]+",
            "[REDACTED_DATABASE_URL]",
            text,
            flags=re.IGNORECASE,
        )
        # OAuth client secrets are frequently emitted as environment variables
        # or query parameters and are distinct from non-sensitive client IDs.
        text = re.sub(
            r"(?i)(\b(?:oauth[_-]?)?client[_-]?secret\s*[:=]\s*)[^\s&\"']{8,}",
            r"\1[REDACTED_OAUTH_SECRET]",
            text,
        )
        text = re.sub(
            r"(?i)([?&](?:oauth[_-]?)?client[_-]?secret=)[^&\s]+",
            r"\1[REDACTED_OAUTH_SECRET]",
            text,
        )
        # Docker and Kubernetes credentials commonly appear in CI environment
        # dumps and config files.  Restrict this to credential-named fields.
        text = re.sub(
            r"(?i)(\b(?:docker[_-]?(?:password|token|auth(?:_config)?)|"
            r"kube(?:rnetes)?[_-]?token)\s*[:=]\s*)[^\s,}\"']{8,}",
            r"\1[REDACTED_CONTAINER_CREDENTIAL]",
            text,
        )
        text = re.sub(
            r"(?i)([\"']auth[\"']\s*:\s*[\"'])[^\"']{8,}([\"'])",
            r"\1[REDACTED_CONTAINER_CREDENTIAL]\2",
            text,
        )
        text = re.sub(
            r"(?i)(\bauthorization\s*:\s*bearer\s+)[A-Za-z0-9._~+/=-]{12,}",
            r"\1[REDACTED_CONTAINER_CREDENTIAL]",
            text,
        )
        # Redact private IPv4 ranges (avoids version numbers like 1.2.3.4)
        text = re.sub(
            r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b",
            "[REDACTED_IP]",
            text,
        )

        # Redact generic "password" or "token" assignments LAST,
        # but avoid consuming values that look like known structured tokens
        # or that have already been redacted by earlier patterns
        def _generic_redact(m: re.Match[str]) -> str:
            val = m.group(2)
            if val.startswith(("glpat-", "AKIA", "eyJ", "-----BEGIN")):
                return m.group(0)
            if val.startswith("[REDACTED"):
                return m.group(0)
            return f"{m.group(1)}: [REDACTED]"

        text = re.sub(
            r"(password|passwd|token|secret|key|auth)\s*[:=]\s*([^\s]{6,})",
            _generic_redact,
            text,
            flags=re.IGNORECASE,
        )

        return text

    async def generate_summary(self, prompt: str, context: str) -> str:  # type: ignore[no-any-return]
        """
        Calls the local model to generate a summary or triage analysis.
        """
        try:
            # Scrub context first (privacy first!)
            clean_context = self.scrub_secrets(context)

            # Construct the Ollama payload
            payload = {
                "model": self.model,
                "prompt": f"{prompt}\n\nContext:\n{clean_context}",
                "stream": False,
                "options": {
                    "num_ctx": 16384,  # Increased context for deeper log analysis
                    "temperature": 0.1,  # Keep it deterministic for triage
                },
            }

            response = await self.client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()

            result = response.json()
            return str(result.get("response", "Error: No response from local AI."))

        except Exception as e:
            logger.error(f"local_ai_error: {str(e)}")
            return f"Error: Local AI ({self.model}) is unavailable. Ensure Ollama is running at {self.base_url}. Details: {str(e)}"

    async def triage_job_log(self, job_id: int | str, log_content: str) -> str:
        """
        Specific workflow for triaging a failed job log locally.
        Uses a 'DevOps First-Responder' persona to find root causes.
        """
        prompt = (
            "You are a Senior DevOps Engineer. Analyze the provided GitLab job log. "
            "1. Pinpoint the EXACT line where the failure started.\n"
            "2. Identify the type of error (Network, Syntax, Auth, Timeout, etc.).\n"
            "3. Suggest 2-3 specific actions to fix the issue.\n"
            "Keep your response technical and concise. No fluff."
        )
        # Take the last 20,000 chars - usually enough for the 'blast zone' of a failure
        log_sample = log_content[-20000:] if len(log_content) > 20000 else log_content
        return await self.generate_summary(prompt, log_sample)

    async def summarize_large_context(self, context_type: str, data: str) -> str:
        """
        Generic tool to reduce massive data into a dense summary for the Expert AI.
        """
        prompt = f"Summarize this {context_type}. Focus on identifying potential issues, blockers, or critical information."
        # Use a safe middle-ground for sample size
        sample = data[:15000] if len(data) > 15000 else data
        return await self.generate_summary(prompt, sample)
