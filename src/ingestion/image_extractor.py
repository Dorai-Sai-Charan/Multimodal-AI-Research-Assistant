"""
Image extraction from PDFs using PyMuPDF.
Extracts images, saves them locally, and returns them as structured objects.
"""

import fitz  # PyMuPDF
import os
import logging
from src.config import settings
from src.models.schemas import ExtractedElement

logger = logging.getLogger(__name__)


class ImageExtractor:
    """Extracts images from PDF documents."""

    def __init__(self, images_dir: str = None):
        self.images_dir = images_dir or settings.images_dir
        os.makedirs(self.images_dir, exist_ok=True)

    def extract(self, file_path: str, doc_id: str) -> list[ExtractedElement]:
        """
        Extract images from a PDF file.

        Args:
            file_path: Path to the PDF file.
            doc_id: ID of the document (used for naming images).

        Returns:
            List of ExtractedElement objects with image details.
        """
        elements: list[ExtractedElement] = []

        try:
            doc = fitz.open(file_path)
            logger.info(f"Extracting images from: {file_path}")
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images(full=True)
                
                for img_idx, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]

                    # --- Size filter at extraction time (50×50 px minimum) ---
                    width = base_image.get("width", 0)
                    height = base_image.get("height", 0)
                    if width < 50 or height < 50:
                        logger.debug(
                            f"Skipping small image {img_idx + 1} on page "
                            f"{page_num + 1} ({width}x{height} px)"
                        )
                        continue

                    # --- File size filter (skip images smaller than 5 KB) ---
                    if len(image_bytes) < 5 * 1024:
                        logger.debug(
                            f"Skipping tiny image {img_idx + 1} on page "
                            f"{page_num + 1} ({len(image_bytes)} bytes)"
                        )
                        continue

                    # Generate a unique path for the image
                    image_filename = f"{doc_id}_p{page_num + 1}_img{img_idx + 1}.{image_ext}"
                    image_path = os.path.join(self.images_dir, image_filename)

                    with open(image_path, "wb") as f:
                        f.write(image_bytes)

                    elements.append(ExtractedElement(
                        content=f"Image {img_idx + 1} from page {page_num + 1}",
                        element_type="figure",
                        page_number=page_num + 1,
                        image_path=image_path
                    ))

            doc.close()
            logger.info(f"Extracted {len(elements)} images from {file_path}")
            return elements

        except Exception as e:
            logger.error(f"Error extracting images from {file_path}: {e}")
            return []
