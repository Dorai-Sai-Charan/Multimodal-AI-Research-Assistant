"""
Vision analysis for graphs, diagrams, and figures using Gemini Vision.
Uses the shared rate limiter and retry logic from llm_client.
"""

import logging
import PIL.Image
from google import genai
from src.config import settings
from src.generation.llm_client import gemini_call_with_retry

logger = logging.getLogger(__name__)


class VisionAnalyzer:
    """Analyzes images using Gemini Vision models."""

    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        self.client = genai.Client(api_key=settings.gemini_api_key)

    def analyze(self, image_path: str, prompt: str = None) -> str:
        """Analyze an image and return a text description (with retry)."""
        if prompt is None:
            prompt = (
                "Describe this image from a research paper in detail. "
                "If it's a graph, explain the axes, data trends, and key findings. "
                "If it's a diagram, explain the components and their relationships. "
                "If it's a table, summarize the key data. "
                "Provide a clear, technical, and concise description."
            )

        try:
            logger.info(f"Analyzing image: {image_path}")
            img = PIL.Image.open(image_path)
            description = gemini_call_with_retry(
                self.client, [prompt, img], temperature=0.2, max_tokens=1024
            )
            logger.info(f"Successfully analyzed image: {image_path}")
            return description
        except Exception as e:
            logger.error(f"Error analyzing image {image_path}: {e}")
            return "Visual content description unavailable."
