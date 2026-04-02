import httpx
import logging
import re
from typing import Any
from config import settings

logger = logging.getLogger(__name__)

class LocalAIService:
    """
    Handles communication with local AI models (e.g., Ollama) 
    to perform pre-processing, log triage, and secret scrubbing.
    """
    
    def __init__(self):
        self.base_url = settings.local_ai_url.rstrip("/")
        self.model = settings.local_ai_model
        self.client = httpx.AsyncClient(timeout=60.0)

    async def scrub_secrets(self, text: str) -> str:
        """
        Redacts sensitive patterns (IPs, tokens, keys) locally 
        to ensure privacy before any data reaches an external AI.
        """
        # Redact IPv4
        text = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[REDACTED_IP]', text)
        # Redact GitLab Tokens
        text = re.sub(r'glpat-[a-zA-Z0-9\-]{20,}', '[REDACTED_GITLAB_TOKEN]', text)
        # Redact AWS Access Keys
        text = re.sub(r'AKIA[0-9A-Z]{16}', '[REDACTED_AWS_KEY]', text)
        # Redact AWS Secret Keys (basic)
        text = re.sub(r'aws_secret_access_key\s*[:=]\s*[a-zA-Z0-9/+=]{40}', 'aws_secret_access_key: [REDACTED]', text, flags=re.IGNORECASE)
        # Redact generic "password" or "token" assignments
        text = re.sub(r'(password|passwd|token|secret|key|auth)\s*[:=]\s*[^\s]{6,}', r'\1: [REDACTED]', text, flags=re.IGNORECASE)
        # Redact long hex strings (potential keys)
        text = re.sub(r'\b[a-fA-F0-9]{32,}\b', '[REDACTED_HEX_TOKEN]', text)
        
        return text

    async def generate_summary(self, prompt: str, context: str) -> str:
        """
        Calls the local model to generate a summary or triage analysis.
        """
        try:
            # Scrub context first (privacy first!)
            clean_context = await self.scrub_secrets(context)
            
            # Construct the Ollama payload
            payload = {
                "model": self.model,
                "prompt": f"{prompt}\n\nContext:\n{clean_context}",
                "stream": False,
                "options": {
                    "num_ctx": 16384, # Increased context for deeper log analysis
                    "temperature": 0.1 # Keep it deterministic for triage
                }
            }
            
            response = await self.client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "Error: No response from local AI.")
            
        except Exception as e:
            logger.error(f"local_ai_error: {str(e)}")
            return f"Error: Local AI ({self.model}) is unavailable. Ensure Ollama is running at {self.base_url}. Details: {str(e)}"

    async def triage_job_log(self, job_id: int, log_content: str) -> str:
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
