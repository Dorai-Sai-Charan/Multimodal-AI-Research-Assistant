"""
Equation extraction from research papers using Gemini Vision.
Converts visual equations to LaTeX and provides natural language explanations.
"""

import logging
import PIL.Image
from google import genai
from google.genai import types
from src.config import settings

logger = logging.getLogger(__name__)


class EquationExtractor:
    """Extracts and explains equations using Gemini Vision."""

    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model_name = "gemini-2.5-flash"

    def extract_from_image(self, image_path: str) -> dict:
        """
        Extract LaTeX from an image and provide an explanation.

        Args:
            image_path: Path to the image file containing an equation.

        Returns:
            Dictionary with 'latex' and 'explanation'.
        """
        prompt = (
            "This is an image from a research paper containing an equation. "
            "1. Extract the equation as a clean LaTeX string. "
            "2. Provide a brief natural language explanation of what the equation represents. "
            "Output the LaTeX first, followed by the explanation."
        )

        try:
            logger.info(f"Extracting equation with Gemini Vision: {image_path}")
            img = PIL.Image.open(image_path)
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, img],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=512,
                ),
            )
            
            output = response.text.strip()
            
            # Simple parsing (could be improved)
            parts = output.split("\n", 1)
            latex = parts[0] if len(parts) > 0 else ""
            explanation = parts[1] if len(parts) > 1 else ""

            return {
                "latex": latex.replace("```latex", "").replace("```", "").strip(),
                "explanation": explanation.strip()
            }

        except Exception as e:
            logger.error(f"Error extracting equation from {image_path}: {e}")
            return {"latex": "", "explanation": "Equation extraction failed."}
