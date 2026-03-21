"""
Vision analysis for graphs, diagrams, and figures using Gemini Vision.
Provides natural language descriptions of visual content.
"""

import logging
import PIL.Image
from google import genai
from google.genai import types
from src.config import settings

logger = logging.getLogger(__name__)


class VisionAnalyzer:
    """Analyzes images using Gemini Vision models."""

    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model_name = "gemini-2.5-flash"

    def analyze(self, image_path: str, prompt: str = None) -> str:
        """
        Analyze an image and return a text description.

        Args:
            image_path: Path to the image file.
            prompt: Optional prompt to guide the analysis.

        Returns:
            Natural language description of the image content.
        """
        if prompt is None:
            prompt = (
                "Describe this image from a research paper in detail. "
                "If it's a graph, explain the axes, data trends, and key findings. "
                "If it's a diagram, explain the components and their relationships. "
                "If it's a table, summarize the key data. "
                "Provide a clear, technical, and concise description."
            )

        try:
            logger.info(f"Analyzing image with Gemini Vision: {image_path}")
            img = PIL.Image.open(image_path)
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, img],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=1024,
                ),
            )
            
            description = response.text.strip()
            logger.info(f"Successfully analyzed image: {image_path}")
            return description

        except Exception as e:
            logger.error(f"Error analyzing image {image_path}: {e}")
            return "Visual content description unavailable due to an error."
