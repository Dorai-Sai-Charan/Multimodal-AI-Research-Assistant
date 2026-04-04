"""
LLM client using Groq for text generation and Google Gemini for vision tasks.
Includes a global rate limiter and automatic retry on 429 errors.
"""

import time
import threading
import logging
from groq import Groq
from google import genai
from google.genai import types
from src.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
RETRY_BASE_DELAY = 15  # seconds

# Groq model for text generation
GROQ_MODEL = "llama-3.3-70b-versatile"

# Gemini model for vision tasks (VisionAnalyzer, EquationExtractor)
GEMINI_MODEL = "gemini-2.0-flash"


class _GeminiRateLimiter:
    """
    Rate limiter for Gemini Vision calls only (used during ingestion).
    """

    _lock = threading.Lock()
    _last_call: float = 0.0
    MIN_INTERVAL = 4.0

    @classmethod
    def wait(cls):
        with cls._lock:
            now = time.time()
            elapsed = now - cls._last_call
            if elapsed < cls.MIN_INTERVAL:
                gap = cls.MIN_INTERVAL - elapsed
                logger.debug(f"Gemini rate limiter: sleeping {gap:.1f}s")
                time.sleep(gap)
            cls._last_call = time.time()


def gemini_call_with_retry(client, contents, temperature=0.3, max_tokens=2048):
    """
    Shared Gemini API caller with rate limiting and retry.
    Used by VisionAnalyzer and EquationExtractor for image-based tasks.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        _GeminiRateLimiter.wait()
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
                    f"Gemini rate limited (attempt {attempt}/{MAX_RETRIES}). "
                    f"Waiting {wait}s…"
                )
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("Gemini API rate limit exceeded after all retries.")


class LLMClient:
    """Groq LLM client for text generation with automatic retry."""

    def __init__(self):
        if not settings.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. "
                "Get one from https://console.groq.com/keys "
                "and add it to your .env file."
            )
        self.client = Groq(api_key=settings.groq_api_key)
        logger.info(f"Groq LLM client initialized (model: {GROQ_MODEL})")

    def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        """Generate a response using Groq with automatic retry on rate limits."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate" in error_str.lower():
                    wait = RETRY_BASE_DELAY * attempt
                    logger.warning(
                        f"Groq rate limited (attempt {attempt}/{MAX_RETRIES}). "
                        f"Waiting {wait}s…"
                    )
                    time.sleep(wait)
                    continue
                raise
        raise RuntimeError("Groq API rate limit exceeded after all retries.")

    def generate_with_context(self, prompt_template: str, **kwargs) -> str:
        """Generate using a prompt template with variable substitution."""
        prompt = prompt_template.format(**kwargs)
        return self.generate(prompt)
