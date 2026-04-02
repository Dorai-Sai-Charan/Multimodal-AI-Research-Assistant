"""
Equation extraction from research papers using Gemini Vision.
Uses the shared rate limiter and retry logic from llm_client.
"""

import logging
import PIL.Image
from google import genai
from src.config import settings
from src.generation.llm_client import gemini_call_with_retry

logger = logging.getLogger(__name__)


class EquationExtractor:
    """Extracts and explains equations using Gemini Vision."""

    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        self.client = genai.Client(api_key=settings.gemini_api_key)

    def extract_from_image(self, image_path: str) -> dict:
        """Extract LaTeX from an image and provide an explanation (with retry)."""
        prompt = (
            "This is an image from a research paper containing an equation. "
            "1. Extract the equation as a clean LaTeX string. "
            "2. Provide a brief natural language explanation of what the equation represents. "
            "Output the LaTeX first, followed by the explanation."
        )

        try:
            logger.info(f"Extracting equation: {image_path}")
            img = PIL.Image.open(image_path)
            output = gemini_call_with_retry(
                self.client, [prompt, img], temperature=0.1, max_tokens=512
            )

            parts = output.split("\n", 1)
            latex = parts[0] if len(parts) > 0 else ""
            explanation = parts[1] if len(parts) > 1 else ""

            return {
                "latex": latex.replace("```latex", "").replace("```", "").strip(),
                "explanation": explanation.strip(),
            }
        except Exception as e:
            logger.error(f"Error extracting equation from {image_path}: {e}")
            return {"latex": "", "explanation": "Equation extraction failed."}
