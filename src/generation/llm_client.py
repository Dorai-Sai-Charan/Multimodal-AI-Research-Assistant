"""
LLM client for Google Gemini using the new google-genai SDK.
Includes a global rate limiter and automatic retry on 429 errors.
"""

import time
import threading
import logging
from google import genai
from google.genai import types
from src.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
RETRY_BASE_DELAY = 15  # seconds

# Model used across the application
GEMINI_MODEL = "gemini-2.5-flash-lite"


class _RateLimiter:
    """
    Global rate limiter shared by ALL Gemini calls.
    gemini-2.5-flash-lite free tier: higher limits than flash.
    """

    _lock = threading.Lock()
    _last_call: float = 0.0
    MIN_INTERVAL = 4.0  # seconds between API calls

    @classmethod
    def wait(cls):
        with cls._lock:
            now = time.time()
            elapsed = now - cls._last_call
            if elapsed < cls.MIN_INTERVAL:
                gap = cls.MIN_INTERVAL - elapsed
                logger.debug(f"Rate limiter: sleeping {gap:.1f}s")
                time.sleep(gap)
            cls._last_call = time.time()


def gemini_call_with_retry(client, contents, temperature=0.3, max_tokens=2048):
    """
    Shared Gemini API caller with rate limiting and retry.
    Used by LLMClient, VisionAnalyzer, and EquationExtractor.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        _RateLimiter.wait()
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            return response.text.strip()
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                wait = RETRY_BASE_DELAY * attempt
                logger.warning(
                    f"Rate limited (attempt {attempt}/{MAX_RETRIES}). "
                    f"Waiting {wait}s…"
                )
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("Gemini API rate limit exceeded after all retries.")


class LLMClient:
    """Google Gemini LLM client with built-in rate limiting and retry."""

    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Get one from https://aistudio.google.com/apikey "
                "and add it to your .env file."
            )
        self.client = genai.Client(api_key=settings.gemini_api_key)
        logger.info(f"Gemini LLM client initialized (model: {GEMINI_MODEL})")

    def generate(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """Generate a response with rate limiting and automatic retry."""
        return gemini_call_with_retry(
            self.client, prompt, temperature=temperature, max_tokens=max_tokens
        )

    def generate_with_context(self, prompt_template: str, **kwargs) -> str:
        """Generate using a prompt template with variable substitution."""
        prompt = prompt_template.format(**kwargs)
        return self.generate(prompt)
