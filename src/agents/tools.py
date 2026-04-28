"""
Tool implementations for the ResearchAgent.
Each tool wraps a specific retrieval strategy (text / table / figure / equation).
"""

import logging
from src.storage.embedding_service import EmbeddingService
from src.storage.vector_store import VectorStore
from src.storage.document_store import DocumentStore
from src.models.schemas import QueryResult

logger = logging.getLogger(__name__)


class AgentTools:
    """
    Collection of retrieval tools available to the ReAct agent.
    All search tools return a formatted string ready to be used as an Observation.
    """

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore()
        self.document_store = DocumentStore()

    # ------------------------------------------------------------------
    # Search tools
    # ------------------------------------------------------------------

    def search_text(self, query: str, source_file: str = None) -> str:
        """Search textual content in the uploaded papers."""
        return self._search(query, content_type="text", source_file=source_file)

    def search_tables(self, query: str, source_file: str = None) -> str:
        """Search table content in the uploaded papers."""
        return self._search(query, content_type="table", source_file=source_file)

    def search_figures(self, query: str, source_file: str = None) -> str:
        """Search figure / diagram descriptions in the uploaded papers."""
        return self._search(query, content_type="figure", source_file=source_file)

    def search_equations(self, query: str, source_file: str = None) -> str:
        """Search mathematical equations and formulas in the uploaded papers."""
        return self._search(query, content_type="equation", source_file=source_file)

    def get_paper_preview(self, source_file: str) -> str:
        """
        Return the first few chunks of a specific paper.
        Best for finding Title, Authors, Abstract, and Introduction.
        """
        source_file = source_file.strip()
        # We search specifically for chunk_index 0, 1, 2 for this paper
        # ChromaDB's .get() is more efficient than .query() for metadata-only lookups
        results = self.vector_store.collection.get(
            where={
                "$and": [
                    {"source_file": source_file},
                    {"chunk_index": {"$in": [0, 1, 2]}}
                ]
            },
            include=["documents", "metadatas"]
        )

        if not results or not results["documents"]:
            return f"No preview available for paper '{source_file}'."

        # Sort by chunk_index to ensure logical order
        combined = []
        for doc, meta in zip(results["documents"], results["metadatas"]):
            combined.append((meta.get("chunk_index", 0), doc))
        
        combined.sort(key=lambda x: x[0])
        
        preview = f"Preview of top sections in '{source_file}':\n\n"
        for idx, text in combined:
            preview += f"--- [Chunk {idx}] ---\n{text}\n\n"
        
        return preview

    def get_paper_list(self) -> str:
        """Return a list of all successfully ingested research papers."""
        docs = self.document_store.get_all_documents()
        completed = [d for d in docs if d.status == "completed"]
        if not completed:
            return "No papers have been uploaded and processed yet."
        lines = [
            f"- {d.filename}  ({d.total_pages} pages, {d.total_chunks} chunks)"
            for d in completed
        ]
        return "Available research papers:\n" + "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _search(
        self,
        query: str,
        content_type: str,
        source_file: str = None,
        top_k: int = 5,
    ) -> str:
        query_embedding = self.embedding_service.embed_text(query)
        results: list[QueryResult] = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_source=source_file,
            filter_type=content_type,
        )

        if not results:
            # Fall back to unfiltered search so the agent never gets an empty result
            results = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                filter_source=source_file,
            )

        if not results:
            return f"No relevant {content_type} content found for query: '{query}'."

        parts = []
        for r in results:
            chunk = r.chunk
            citation = f"[{chunk.metadata.source_file}, p.{chunk.metadata.page_number}"
            if chunk.metadata.section_heading:
                citation += f", §{chunk.metadata.section_heading}"
            citation += f"] (score={r.score:.2f})"
            parts.append(f"{citation}\n{chunk.content}")

        return "\n\n".join(parts)
