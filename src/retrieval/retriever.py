"""
Semantic retriever.
Handles the retrieval pipeline: query → embed → search → rank → return.
"""

import os
import logging
from src.storage.embedding_service import EmbeddingService
from src.storage.vector_store import VectorStore
from src.models.schemas import QueryResult

logger = logging.getLogger(__name__)


class Retriever:
    """
    Retrieval pipeline that embeds queries and searches the vector store.
    """

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore()

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filter_source: str | None = None,
        filter_type: str | None = None,
        similarity_threshold: float | None = None,
    ) -> list[QueryResult]:
        """
        Retrieve relevant chunks for a given query.

        Args:
            query: User's natural language query.
            top_k: Number of results to return.
            filter_source: Optional filter by source filename.
            filter_type: Optional filter by content type.

        Returns:
            List of QueryResult objects sorted by relevance.
        """
        logger.info(f"Retrieving for query: '{query[:80]}...' (top_k={top_k})")

        # Step 1: Embed the query
        query_embedding = self.embedding_service.embed_text(query)

        # Step 2: Search the vector store
        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_source=filter_source,
            filter_type=filter_type,
        )

        if similarity_threshold is not None and similarity_threshold > 0:
            before = len(results)
            results = [r for r in results if r.score >= similarity_threshold]
            logger.info(
                f"Similarity threshold {similarity_threshold} filtered "
                f"{before - len(results)}/{before} results"
            )

        logger.info(f"Retrieved {len(results)} relevant chunks")
        return results

    def build_context(
        self,
        results: list[QueryResult],
        max_context_length: int = 4000,
    ) -> str:
        """
        Build a formatted context string from retrieval results.
        Includes source citations for each chunk.

        Args:
            results: List of QueryResult objects.
            max_context_length: Maximum character length for the context.

        Returns:
            Formatted context string with citations.
        """
        context_parts = []
        total_length = 0

        for result in results:
            chunk = result.chunk
            citation = (
                f"[Source: {chunk.metadata.source_file}, "
                f"Page {chunk.metadata.page_number}"
            )
            if chunk.metadata.section_heading:
                citation += f", Section: {chunk.metadata.section_heading}"
            citation += f"] (Relevance: {result.score:.2f})"

            # Truncate individual chunks to 600 chars so all top-k results
            # are included rather than stopping early at max_context_length.
            chunk_body = chunk.content
            truncated = chunk_body[:600] if len(chunk_body) > 600 else chunk_body
            chunk_text = f"{citation}\n{truncated}\n"

            context_parts.append(chunk_text)
            total_length += len(chunk_text)

        return "\n---\n".join(context_parts)

    def get_citations(self, results: list[QueryResult]) -> list[dict]:
        """Extract structured citations including visual metadata (images, tables, equations)."""
        citations = []
        seen = set()

        for result in results:
            chunk = result.chunk
            meta = chunk.metadata
            is_visual = meta.element_type in ("figure", "table", "equation")

            # Visual elements each get their own citation entry; text deduplicates by page
            dedup_key = (
                meta.source_file,
                meta.page_number,
                meta.element_type if is_visual else "text",
                os.path.basename(meta.image_path) if meta.image_path else "",
            )
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            citation: dict = {
                "source_file": meta.source_file,
                "page_number": meta.page_number,
                "section": meta.section_heading,
                "relevance_score": round(result.score, 3),
                "element_type": meta.element_type,
                "content_type": chunk.content_type,
            }

            if meta.image_path and os.path.exists(meta.image_path):
                citation["image_url"] = f"/images/{os.path.basename(meta.image_path)}"
            if meta.image_description:
                citation["image_description"] = meta.image_description
            if meta.table_data:
                citation["table_data"] = meta.table_data
            if meta.latex_source:
                citation["latex_source"] = meta.latex_source

            citations.append(citation)

        return citations
