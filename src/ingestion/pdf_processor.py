"""
PDF Text Extraction using PyMuPDF (fitz).
Extracts text with layout awareness, detects section headings,
and produces ExtractedElement objects for downstream chunking.
"""

import fitz  # PyMuPDF
import os
import logging
from pathlib import Path
from src.models.schemas import ExtractedElement

logger = logging.getLogger(__name__)


class PDFProcessor:
    """Extracts structured text from PDF documents."""

    # Common section heading patterns in research papers
    HEADING_KEYWORDS = [
        "abstract", "introduction", "background", "related work",
        "methodology", "method", "methods", "approach", "proposed",
        "experiment", "experiments", "results", "evaluation",
        "discussion", "conclusion", "conclusions", "future work",
        "references", "appendix", "acknowledgment", "acknowledgments",
    ]

    def extract(self, file_path: str) -> list[ExtractedElement]:
        """
        Extract text from a PDF file, producing a list of ExtractedElements.

        Each page is processed to detect:
        - Regular text blocks
        - Section headings (via font size heuristics)

        Args:
            file_path: Path to the PDF file.

        Returns:
            List of ExtractedElement objects with text content and metadata.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        elements: list[ExtractedElement] = []
        current_heading = ""

        try:
            doc = fitz.open(file_path)
            logger.info(f"Processing PDF: {file_path} ({len(doc)} pages)")

            for page_num in range(len(doc)):
                page = doc[page_num]
                blocks = page.get_text("dict", sort=True)["blocks"]

                page_text_parts = []
                page_headings = []

                for block in blocks:
                    if block["type"] != 0:  # 0 = text block
                        continue

                    for line in block.get("lines", []):
                        line_text = ""
                        max_font_size = 0

                        for span in line.get("spans", []):
                            text = span.get("text", "").strip()
                            if text:
                                line_text += text + " "
                                font_size = span.get("size", 12)
                                if font_size > max_font_size:
                                    max_font_size = font_size

                        line_text = line_text.strip()
                        if not line_text:
                            continue

                        # Detect headings: larger font or known keywords
                        is_heading = self._is_heading(line_text, max_font_size)
                        if is_heading:
                            # Save accumulated text before heading
                            if page_text_parts:
                                combined_text = "\n".join(page_text_parts).strip()
                                if combined_text:
                                    elements.append(ExtractedElement(
                                        content=combined_text,
                                        element_type="text",
                                        page_number=page_num + 1,
                                        section_heading=current_heading,
                                    ))
                                page_text_parts = []

                            current_heading = line_text
                            page_headings.append(line_text)
                        else:
                            page_text_parts.append(line_text)

                # Save remaining text on the page
                if page_text_parts:
                    combined_text = "\n".join(page_text_parts).strip()
                    if combined_text:
                        elements.append(ExtractedElement(
                            content=combined_text,
                            element_type="text",
                            page_number=page_num + 1,
                            section_heading=current_heading,
                        ))

            doc.close()
            logger.info(f"Extracted {len(elements)} text elements from {file_path}")
            return elements

        except Exception as e:
            logger.error(f"Error processing PDF {file_path}: {e}")
            raise

    def get_page_count(self, file_path: str) -> int:
        """Get the total number of pages in a PDF."""
        doc = fitz.open(file_path)
        count = len(doc)
        doc.close()
        return count

    def _is_heading(self, text: str, font_size: float) -> bool:
        """
        Heuristic heading detection:
        - Font size > 13 (larger than body text)
        - Text matches common section heading keywords
        - Short text (< 80 chars) with title-like casing
        """
        text_lower = text.lower().strip()

        # Check known heading keywords
        for keyword in self.HEADING_KEYWORDS:
            if text_lower == keyword or text_lower.startswith(f"{keyword}:"):
                return True
            # Numbered headings like "1. Introduction", "2.1 Method"
            stripped = text_lower.lstrip("0123456789. ")
            if stripped == keyword or stripped.startswith(f"{keyword}:"):
                return True

        # Font size heuristic (typical body is 10-12pt)
        if font_size >= 14 and len(text) < 100:
            return True

        return False
