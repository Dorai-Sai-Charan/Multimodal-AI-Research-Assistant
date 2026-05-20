"""
LLM client using Groq for text generation and Google Gemini for vision tasks.
Includes a global rate limiter and automatic retry on 429 errors.

Generation parameters (model, temperature, max_tokens, top_p, penalties, seed,
reasoning_effort) can be overridden per call via an ``llm_config`` dict so the
frontend settings panel can drive them dynamically.
"""

import time
import asyncio
import threading
import logging
from groq import Groq
from google import genai
from google.genai import types
from src.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
RETRY_BASE_DELAY = 15  # seconds
MAX_TOTAL_RETRY_WAIT = 30  # seconds — cap total wait time (Fix 12)


def _sleep(seconds: float) -> None:
    """
    Fix 12: Sleep without blocking the event loop.

    When called from a thread that is NOT running an asyncio event loop
    (background ingestion thread, humanizer thread, executor worker), this
    falls back to the plain ``time.sleep`` so those paths are unaffected.
    When called from a coroutine that is running on an event loop, we
    schedule an asyncio sleep on the running loop so the event loop is not
    blocked.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        # We are inside a running event loop — schedule a non-blocking sleep.
        # run_coroutine_threadsafe blocks this thread but yields the loop.
        future = asyncio.run_coroutine_threadsafe(asyncio.sleep(seconds), loop)
        future.result()
    else:
        time.sleep(seconds)


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
                _sleep(gap)  # Fix 12: use non-blocking sleep
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
                wait = min(RETRY_BASE_DELAY * attempt, MAX_TOTAL_RETRY_WAIT)  # Fix 12: cap wait
                logger.warning(
                    f"Gemini rate limited (attempt {attempt}/{MAX_RETRIES}). "
                    f"Waiting {wait}s…"
                )
                _sleep(wait)  # Fix 12: use non-blocking sleep
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
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert AI research assistant specializing in scientific "
                        "paper analysis. Always be precise, technical, and cite your sources. "
                        "When context is provided, base your answer strictly on that context."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
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
                    wait = min(RETRY_BASE_DELAY * attempt, MAX_TOTAL_RETRY_WAIT)  # Fix 12: cap wait
                    logger.warning(
                        f"Groq rate limited (attempt {attempt}/{MAX_RETRIES}). "
                        f"Waiting {wait}s…"
                    )
                    _sleep(wait)  # Fix 12: use non-blocking sleep
                    continue
                raise
        raise RuntimeError("Groq API rate limit exceeded after all retries.")

    def generate_with_image(
        self,
        prompt: str,
        image_path: str,
        model: str = "meta-llama/llama-4-scout-17b-16e-instruct",
        temperature: float = 0.3,
        max_tokens: int = 1500,
    ) -> str:
        """
        Generate a response using Groq's multimodal vision model.

        Sends an image + prompt to a Llama 4 vision model — much higher free-tier
        limits than Gemini, and runs alongside the existing Groq text client.

        Args:
            prompt: The text instructions / question about the image.
            image_path: Local path to an image file (PNG, JPG, JPEG).
            model: Groq vision model id. Defaults to Llama 4 Scout.
            temperature: Sampling temperature.
            max_tokens: Max output tokens.

        Returns:
            The model's response as a stripped string.
        """
        if not self.enabled:
            return "ERROR: GROQ_API_KEY is not set."

        import base64
        import os

        if not os.path.exists(image_path):
            return f"Image not found at {image_path}"

        # Read & base64-encode the image
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        b64 = base64.b64encode(image_bytes).decode("utf-8")

        # Detect MIME type from extension
        ext = os.path.splitext(image_path)[1].lower().lstrip(".")
        mime_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}
        mime = mime_map.get(ext, "png")
        data_url = f"data:image/{mime};base64,{b64}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ]

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate" in error_str.lower():
                    wait = min(RETRY_BASE_DELAY * attempt, MAX_TOTAL_RETRY_WAIT)  # Fix 12: cap wait
                    logger.warning(
                        f"Groq vision rate limited (attempt {attempt}/{MAX_RETRIES}). "
                        f"Waiting {wait}s…"
                    )
                    _sleep(wait)  # Fix 12: use non-blocking sleep
                    continue
                logger.error(f"Groq vision error: {e}")
                raise
        raise RuntimeError("Groq vision API rate limit exceeded after all retries.")

    def generate_stream(self, prompt: str, llm_config: dict | None = None):
        """
        Generator that yields text chunks as they stream from Groq.

        Builds the same messages array as ``generate()`` and calls the Groq
        client with ``stream=True``.  Each non-empty delta content chunk is
        yielded immediately so the caller can push tokens to the client as they
        arrive.

        Rate-limit errors (429) trigger a single retry without sleeping so the
        stream is not stalled.
        """
        if not self.enabled:
            yield (
                "ERROR: GROQ_API_KEY is not set. Please add it to your .env file "
                "to enable text generation and RAG features."
            )
            return

        cfg = self._resolve_config(llm_config)

        kwargs: dict = {
            "model": cfg["model"],
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert AI research assistant specializing in scientific "
                        "paper analysis. Always be precise, technical, and cite your sources. "
                        "When context is provided, base your answer strictly on that context."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": cfg["temperature"],
            "max_tokens": cfg["max_tokens"],
            "top_p": cfg["top_p"],
            "frequency_penalty": cfg["frequency_penalty"],
            "presence_penalty": cfg["presence_penalty"],
            "stream": True,
        }
        if cfg["seed"] is not None:
            kwargs["seed"] = int(cfg["seed"])
        if cfg["model"] in REASONING_MODELS and cfg["reasoning_effort"]:
            if cfg["model"] not in ["qwen/qwen3-32b", "groq/compound-mini"]:
                kwargs["reasoning_effort"] = cfg["reasoning_effort"]

        for attempt in range(1, 3):  # one retry on rate limit
            try:
                stream = self.client.chat.completions.create(**kwargs)
                for chunk in stream:
                    delta_content = chunk.choices[0].delta.content
                    if delta_content:
                        yield delta_content
                return  # stream exhausted successfully
            except Exception as e:
                error_str = str(e)
                if ("429" in error_str or "rate" in error_str.lower()) and attempt == 1:
                    logger.warning("Groq rate limited during streaming — retrying once…")
                    continue
                raise

    def generate_with_context(
        self,
        prompt_template: str,
        llm_config: dict | None = None,
        **kwargs,
    ) -> str:
        """Generate using a prompt template with variable substitution."""
        prompt = prompt_template.format(**kwargs)
        return self.generate(prompt, llm_config=llm_config)
