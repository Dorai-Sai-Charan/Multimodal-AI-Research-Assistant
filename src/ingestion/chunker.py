"""
Semantic text chunker.
Splits extracted elements into appropriately-sized chunks
while preserving metadata and section boundaries.
"""

import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.models.schemas import ExtractedElement, Chunk, ChunkMetadata
from src.config import settings

logger = logging.getLogger(__name__)


class SemanticChunker:
    """
    Chunks extracted elements into pieces suitable for embedding.
    Uses RecursiveCharacterTextSplitter for intelligent splitting.
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
                # Split long text elements into multiple chunks
                text_chunks = self.splitter.split_text(element.content)

                for text in text_chunks:
                    if not text.strip():
                        continue

                    metadata = ChunkMetadata(
                        source_file=source_file,
                        page_number=element.page_number,
                        section_heading=element.section_heading,
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
                # Tables are stored as single chunks with structured data
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
                    content=element.content,
                    content_type="table",
                    metadata=metadata,
                ))
                chunk_index += 1

            elif element.element_type == "figure":
                # Figures: embed the image description
                metadata = ChunkMetadata(
                    source_file=source_file,
                    page_number=element.page_number,
                    section_heading=element.section_heading,
                    chunk_index=chunk_index,
                    element_type="figure",
                    image_path=element.image_path,
                    image_description=element.content,
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

        logger.info(
            f"Chunked {len(elements)} elements into {len(chunks)} chunks "
            f"for '{source_file}'"
        )
        return chunks
