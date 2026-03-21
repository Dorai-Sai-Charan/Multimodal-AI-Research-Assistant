"""
LLM client for Google Gemini using the new google-genai SDK.
Handles generation requests with context injection.
"""

import logging
from google import genai
from google.genai import types
from src.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Google Gemini LLM client for text generation."""

    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Get one from https://aistudio.google.com/apikey "
                "and add it to your .env file."
            )
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model_name = "gemini-2.5-flash"
        logger.info(f"Gemini LLM client initialized (model: {self.model_name})")

    def generate(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """
        Generate a response from the LLM.

        Args:
            prompt: The complete prompt including context and question.
            temperature: Sampling temperature (lower = more focused).
            max_tokens: Maximum tokens in the response.

        Returns:
            Generated text response.
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            raise

    def generate_with_context(
        self,
        prompt_template: str,
        **kwargs,
    ) -> str:
        """
        Generate using a prompt template with variable substitution.

        Args:
            prompt_template: Template string with {placeholders}.
            **kwargs: Values to fill the placeholders.

        Returns:
            Generated text response.
        """
        prompt = prompt_template.format(**kwargs)
        return self.generate(prompt)
