"""
PDF Text Extraction using PyMuPDF (fitz).
Extracts text with layout awareness, detects section headings,
and produces ExtractedElement objects for downstream chunking.
"""

import fitz  # PyMuPDF
import os
import re
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

    # Prefixes that indicate figure/table captions, not headings
    CAPTION_PREFIXES = (
        "figure", "fig.", "table", "eq.", "equation", "scheme",
    )

    # Numbering patterns that are typical for section headings
    _NUMBERING_RE = re.compile(
        r"^(?:"
        r"\d+\."            # 1.  or 2.3
        r"|\d+\.\d+"
        r"|[IVXLCDM]+\."   # Roman numerals: I. II. III.
        r")"
    )

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
                blocks = self._extract_blocks_in_reading_order(page)

                page_text_parts = []
                page_headings = []

                for block in blocks:

                    for line in block.get("lines", []):
                        line_text = ""
                        max_font_size = 0
                        all_spans = line.get("spans", [])
                        all_bold = bool(all_spans)  # assume all bold until proven otherwise

                        for span in all_spans:
                            text = span.get("text", "").strip()
                            if text:
                                line_text += text + " "
                                font_size = span.get("size", 12)
                                if font_size > max_font_size:
                                    max_font_size = font_size
                                # Bold flag is bit 4 (value 16) in PyMuPDF font flags
                                if not (span.get("flags", 0) & 16):
                                    all_bold = False

                        line_text = line_text.strip()
                        if not line_text:
                            continue

                        # Detect headings: larger font or known keywords
                        is_heading = self._is_heading(line_text, max_font_size, all_bold)
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

    def _extract_blocks_in_reading_order(self, page) -> list:
        """Return text blocks sorted in correct reading order (handles 2-column layouts)."""
        blocks = page.get_text("dict", sort=False)["blocks"]
        page_width = page.rect.width
        midpoint = page_width / 2

        text_blocks = [b for b in blocks if b.get("type") == 0]  # type 0 = text

        if not text_blocks:
            return text_blocks

        # Detect 2-column layout: check if blocks cluster into left/right groups
        # Use 70% of midpoint as the threshold to separate left vs right columns
        left_blocks = [b for b in text_blocks if b["bbox"][0] < midpoint * 0.7]
        right_blocks = [b for b in text_blocks if b["bbox"][0] >= midpoint * 0.7]

        # Two-column if significant content on both sides (at least 2 blocks each)
        is_two_column = len(left_blocks) >= 2 and len(right_blocks) >= 2

        if is_two_column:
            # Sort each column top-to-bottom, then concatenate left then right
            left_sorted = sorted(left_blocks, key=lambda b: b["bbox"][1])
            right_sorted = sorted(right_blocks, key=lambda b: b["bbox"][1])
            return left_sorted + right_sorted
        else:
            # Single column: sort all by y then x
            return sorted(text_blocks, key=lambda b: (b["bbox"][1], b["bbox"][0]))

    def _is_heading(self, text: str, font_size: float, all_bold: bool = False) -> bool:
        """
        Improved heuristic heading detection.

        Requirements to be classified as a heading:
        1. Font size >= 14 AND text length < 100, PLUS at least one of:
           a. Starts with a numbering pattern (e.g. "1.", "2.3", "III.")
           b. Entire line is bold (font flag bit-4 set on all spans)
           c. Matches a known section-heading keyword (with or without a
              leading section number)
        2. OR: keyword match even without a large font (backward-compat for
           exact keyword lines in normal-sized fonts).

        Caption prefixes (Figure, Table, Eq., …) are always excluded.
        """
        text_stripped = text.strip()
        text_lower = text_stripped.lower()

        # --- 0. Skip figure/table captions -----------------------------------
        for prefix in self.CAPTION_PREFIXES:
            if text_lower.startswith(prefix):
                return False

        # --- 1. Keyword match (exact or after stripping leading number) ------
        def _keyword_match(candidate: str) -> bool:
            for keyword in self.HEADING_KEYWORDS:
                if candidate == keyword or candidate.startswith(f"{keyword}:"):
                    return True
            return False

        # bare keyword (any font size)
        if _keyword_match(text_lower):
            return True

        # strip a leading section number then re-check
        stripped_lower = re.sub(r"^[\d\.\s]+", "", text_lower).strip()
        if stripped_lower and _keyword_match(stripped_lower):
            return True

        # --- 2. Font-size gate (>= 14 pt, < 100 chars) with signal check ----
        if font_size >= 14 and len(text_stripped) < 100:
            has_numbering = bool(self._NUMBERING_RE.match(text_stripped))
            if has_numbering or all_bold or _keyword_match(stripped_lower):
                return True

        return False
