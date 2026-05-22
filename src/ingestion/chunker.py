"""
Recursive text chunker.
Splits extracted elements into appropriately-sized chunks
while preserving metadata and section boundaries.
"""

import re
import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.models.schemas import ExtractedElement, Chunk, ChunkMetadata
from src.config import settings

logger = logging.getLogger(__name__)


_SECTION_RE = re.compile(
    r'^(\d+\.(?:\d+\.?)*\s+\w|Abstract|Introduction|Related Work|Background|'
    r'Methodology|Methods|Experiments?|Results?|Discussion|Conclusion|'
    r'References?|Acknowledgements?|Appendix)',
    re.IGNORECASE | re.MULTILINE,
)


class RecursiveChunker:
    """
    Chunks extracted elements into pieces suitable for embedding.
    Uses RecursiveCharacterTextSplitter for intelligent splitting.

    Minimum chunk length: 15 words (shorter chunks are discarded).
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def _split_at_sections(self, text: str) -> list[str]:
        """Split text at section heading boundaries so headings start chunks."""
        boundaries = [m.start() for m in _SECTION_RE.finditer(text)]
        if len(boundaries) <= 1:
            return [text]
        sections = []
        for i, start in enumerate(boundaries):
            end = boundaries[i + 1] if i + 1 < len(boundaries) else len(text)
            sections.append(text[start:end].strip())
        # Prepend any text that appears before the first heading
        if boundaries[0] > 0:
            sections.insert(0, text[:boundaries[0]].strip())
        return [s for s in sections if s]

    def chunk(
        self,
        elements: list[ExtractedElement],
        source_file: str,
    ) -> list[Chunk]:
        """
        Convert a list of ExtractedElements into indexable Chunks.

        Args:
            elements: Extracted elements from a document.
            source_file: Original filename for metadata.

        Returns:
            List of Chunk objects ready for embedding and storage.
        """
        chunks: list[Chunk] = []
        chunk_index = 0

        for element in elements:
            if not element.content.strip():
                continue

            if element.element_type == "text":
                # Split at section boundaries first, then chunk each section
                sections = self._split_at_sections(element.content)

                for section in sections:
                    # Carry the section heading into metadata if this section
                    # starts with a heading pattern
                    heading_match = _SECTION_RE.match(section)
                    section_heading = (
                        heading_match.group(0).strip()
                        if heading_match
                        else element.section_heading
                    )

                    text_chunks = self.splitter.split_text(section)

                    for text in text_chunks:
                        if not text.strip():
                            continue

                        metadata = ChunkMetadata(
                            source_file=source_file,
                            page_number=element.page_number,
                            section_heading=section_heading,
                            chunk_index=chunk_index,
                            element_type="paragraph",
                            confidence=element.confidence,
                        )

                        chunks.append(Chunk(
                            content=text.strip(),
                            content_type="text",
                            metadata=metadata,
                        ))
                        chunk_index += 1

            elif element.element_type == "table":
                # Tables are stored as single chunks with structured data.
                # Prepend column headers so queries like "what columns does
                # Table 2 have?" match the embedded text.
                if element.table_data:
                    cols = element.table_data.get("cols", [])
                    if cols:
                        header_prefix = f"Table columns: {', '.join(cols)}\n"
                        content = header_prefix + element.content
                    else:
                        content = element.content
                else:
                    content = element.content

                metadata = ChunkMetadata(
                    source_file=source_file,
                    page_number=element.page_number,
                    section_heading=element.section_heading,
                    chunk_index=chunk_index,
                    element_type="table",
                    table_data=element.table_data,
                    confidence=element.confidence,
                )

                chunks.append(Chunk(
                    content=content,
                    content_type="table",
                    metadata=metadata,
                ))
                chunk_index += 1

            elif element.element_type == "figure":
                # Figures: embed the image description (may include OCR text)
                # Carry through any LaTeX extracted during ingestion
                latex_src = getattr(element, "_latex_source", None)
                metadata = ChunkMetadata(
                    source_file=source_file,
                    page_number=element.page_number,
                    section_heading=element.section_heading,
                    chunk_index=chunk_index,
                    element_type="figure",
                    image_path=element.image_path,
                    image_description=element.content,
                    latex_source=latex_src,
                    confidence=element.confidence,
                )

                chunks.append(Chunk(
                    content=element.content,
                    content_type="figure",
                    metadata=metadata,
                ))
                chunk_index += 1

            elif element.element_type == "equation":
                metadata = ChunkMetadata(
                    source_file=source_file,
                    page_number=element.page_number,
                    section_heading=element.section_heading,
                    chunk_index=chunk_index,
                    element_type="equation",
                    latex_source=element.content,
                    confidence=element.confidence,
                )

                chunks.append(Chunk(
                    content=element.content,
                    content_type="equation",
                    metadata=metadata,
                ))
                chunk_index += 1

        # Filter out chunks that are too short to be meaningful (< 15 words)
        before_filter = len(chunks)
        chunks = [c for c in chunks if len(c.content.split()) >= 15]
        removed = before_filter - len(chunks)
        if removed:
            logger.info(f"Removed {removed} chunks shorter than 15 words")

        logger.info(
            f"Chunked {len(elements)} elements into {len(chunks)} chunks "
            f"for '{source_file}'"
        )
        return chunks
