"""
OCR processing for scanned documents and handwritten notes using EasyOCR.
Extracts text from images and returns it as structured elements.
"""

import easyocr
import logging
from src.models.schemas import ExtractedElement

logger = logging.getLogger(__name__)


class OCRProcessor:
    """Extracts text from images using EasyOCR."""

    def __init__(self, languages=['en']):
        """
        Initialize the OCR engine.
        
        Args:
            languages: List of languages to support (e.g., ['en']).
        """
        logger.info(f"Initializing EasyOCR for languages: {languages}")
        self.reader = easyocr.Reader(languages, gpu=False) # GPU=False for better compatibility in env

    def extract_from_image(self, image_path: str, page_number: int = 1) -> ExtractedElement:
        """
        Extract text from an image file.

        Args:
            image_path: Path to the image file.
            page_number: Page number the image was found on.

        Returns:
            ExtractedElement object with the OCR text.
        """
        try:
            logger.info(f"Performing OCR on: {image_path}")
            results = self.reader.readtext(image_path)
            
            # Combine all detected text blocks
            text = " ".join([result[1] for result in results])
            
            # Use confidence of the first block as a proxy (or average if needed)
            confidence = results[0][2] if results else 0.0

            return ExtractedElement(
                content=text,
                element_type="text",
                page_number=page_number,
                section_heading="OCR Extraction",
                confidence=confidence
            )

        except Exception as e:
            logger.error(f"Error during OCR on {image_path}: {e}")
            return ExtractedElement(
                content="",
                element_type="text",
                page_number=page_number,
                section_heading="OCR Extraction Failed",
                confidence=0.0
            )
