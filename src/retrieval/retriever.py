"""
Semantic retriever.
Handles the retrieval pipeline: query → embed → search → rank → return.
"""

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

            chunk_text = f"{citation}\n{chunk.content}\n"

            if total_length + len(chunk_text) > max_context_length:
                break

            context_parts.append(chunk_text)
            total_length += len(chunk_text)

        return "\n---\n".join(context_parts)

    def get_citations(self, results: list[QueryResult]) -> list[dict]:
        """Extract structured citations from retrieval results."""
        citations = []
        seen = set()

        for result in results:
            chunk = result.chunk
            key = (chunk.metadata.source_file, chunk.metadata.page_number)
            if key not in seen:
                seen.add(key)
                citations.append({
                    "source_file": chunk.metadata.source_file,
                    "page_number": chunk.metadata.page_number,
                    "section": chunk.metadata.section_heading,
                    "relevance_score": round(result.score, 3),
                })

        return citations
