"""
Table extraction from PDFs using pdfplumber.
Extracts tabular data and returns them as structured objects.
"""

import pdfplumber
import logging
from src.models.schemas import ExtractedElement

logger = logging.getLogger(__name__)


class TableExtractor:
    """Extracts tables from PDF documents."""

    def extract(self, file_path: str) -> list[ExtractedElement]:
        """
        Extract tables from a PDF file.

        Args:
            file_path: Path to the PDF file.

        Returns:
            List of ExtractedElement objects with table content and structured data.
        """
        elements: list[ExtractedElement] = []

        try:
            with pdfplumber.open(file_path) as pdf:
                logger.info(f"Extracting tables from: {file_path}")
                for page_num, page in enumerate(pdf.pages):
                    tables = page.extract_tables()
                    for table_num, table in enumerate(tables):
                        if not table:
                            continue

                        # Convert table to markdown for embedding/display
                        markdown_table = self._to_markdown(table)

                        # Build processed_table (None → "") for shape extraction
                        processed_table = [
                            [str(cell) if cell is not None else "" for cell in row]
                            for row in table
                        ]

                        # Structured data for metadata.
                        # cols/rows match the shape expected by visual-citations.tsx:
                        #   cols: string[]          — header row
                        #   rows: string[][]        — data rows
                        # row_count/col_count kept for backwards compatibility.
                        table_data = {
                            "cols": processed_table[0] if processed_table else [],
                            "rows": processed_table[1:] if len(processed_table) > 1 else [],
                            "row_count": len(table),
                            "col_count": len(table[0]) if table else 0,
                        }

                        elements.append(ExtractedElement(
                            content=markdown_table,
                            element_type="table",
                            page_number=page_num + 1,
                            section_heading=f"Table {table_num + 1}",
                            table_data=table_data
                        ))

            logger.info(f"Extracted {len(elements)} tables from {file_path}")
            return elements

        except Exception as e:
            logger.error(f"Error extracting tables from {file_path}: {e}")
            return []

    def _to_markdown(self, table: list[list[str]]) -> str:
        """Convert a list-of-lists table to a markdown string."""
        if not table:
            return ""

        # Remove None values
        processed_table = [[str(cell) if cell is not None else "" for cell in row] for row in table]
        
        if not processed_table:
            return ""

        headers = processed_table[0]
        rows = processed_table[1:]

        md = "| " + " | ".join(headers) + " |\n"
        md += "| " + " | ".join(["---"] * len(headers)) + " |\n"
        for row in rows:
            md += "| " + " | ".join(row) + " |\n"
        
        return md
