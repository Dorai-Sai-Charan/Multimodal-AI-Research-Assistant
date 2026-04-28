"""
LLM client using Groq for text generation and Google Gemini for vision tasks.
Includes a global rate limiter and automatic retry on 429 errors.

Generation parameters (model, temperature, max_tokens, top_p, penalties, seed,
reasoning_effort) can be overridden per call via an ``llm_config`` dict so the
frontend settings panel can drive them dynamically.
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

# Gemini model for vision tasks (VisionAnalyzer, EquationExtractor)
GEMINI_MODEL = "gemini-2.0-flash"

# Groq models that support the `reasoning_effort` parameter.
REASONING_MODELS = {
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3-32b",
    "groq/compound-mini",
}


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
        self.enabled = bool(settings.groq_api_key)
        if not self.enabled:
            logger.warning(
                "GROQ_API_KEY is not set. Text generation features will be disabled. "
                "Get one from https://console.groq.com/keys and add it to your .env file."
            )
            self.client = None
        else:
            self.client = Groq(api_key=settings.groq_api_key)
            logger.info(f"Groq LLM client initialized (default model: {settings.llm_model})")

    # ------------------------------------------------------------------
    # Config resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_config(llm_config: dict | None) -> dict:
        """Merge a user-supplied override dict with the app defaults."""
        cfg = {
            "model": settings.llm_model,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
            "top_p": settings.llm_top_p,
            "frequency_penalty": settings.llm_frequency_penalty,
            "presence_penalty": settings.llm_presence_penalty,
            "seed": None,
            "reasoning_effort": settings.llm_reasoning_effort,
        }
        if llm_config:
            for k, v in llm_config.items():
                if v is not None and k in cfg:
                    cfg[k] = v
        return cfg

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        llm_config: dict | None = None,
        tools: list | None = None,
        tool_choice: str | None = None,
    ):
        """
        Generate a response using Groq with automatic retry on rate limits.

        When ``tools`` are provided the raw message object is returned so the
        caller can inspect ``.tool_calls``; otherwise a plain stripped string
        is returned, keeping all existing RAG callers working unchanged.

        ``temperature`` / ``max_tokens`` remain as positional-friendly shortcuts
        so existing callers keep working; ``llm_config`` is the full override
        dict driven by the frontend settings panel.
        """
        if not self.enabled:
            return (
                "ERROR: GROQ_API_KEY is not set. Please add it to your .env file "
                "to enable text generation and RAG features."
            )

        cfg = self._resolve_config(llm_config)
        if temperature is not None:
            cfg["temperature"] = temperature
        if max_tokens is not None:
            cfg["max_tokens"] = max_tokens

        kwargs: dict = {
            "model": cfg["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": cfg["temperature"],
            "max_tokens": cfg["max_tokens"],
            "top_p": cfg["top_p"],
            "frequency_penalty": cfg["frequency_penalty"],
            "presence_penalty": cfg["presence_penalty"],
        }
        if cfg["seed"] is not None:
            kwargs["seed"] = int(cfg["seed"])
        if cfg["model"] in REASONING_MODELS and cfg["reasoning_effort"]:
            # Model-specific overrides to avoid Groq API 400 errors
            if cfg["model"] in ["qwen/qwen3-32b", "groq/compound-mini"]:
                # These models report 'reasoning_effort is not supported' via Groq API
                pass
            else:
                # Only GPT-OSS models currently support low/medium/high
                kwargs["reasoning_effort"] = cfg["reasoning_effort"]

        # --- Native tool-calling support -----------------------------------
        # Pass tools to the API so the model can call them directly instead
        # of trying to call them through raw text output (which Groq rejects
        # with "Tool choice is none, but model called a tool").
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(**kwargs)
                message = response.choices[0].message
                # Return the full message object when tools are registered so
                # the caller (ResearchAgent) can inspect .tool_calls.
                if tools:
                    return message
                return message.content.strip()
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

    def generate_with_context(
        self,
        prompt_template: str,
        llm_config: dict | None = None,
        **kwargs,
    ) -> str:
        """Generate using a prompt template with variable substitution."""
        prompt = prompt_template.format(**kwargs)
        return self.generate(prompt, llm_config=llm_config)
