"""
ChromaDB Vector Store wrapper.
Handles storing, searching, and managing document chunks.
"""

import logging
import json
import chromadb
from chromadb.config import Settings as ChromaSettings
from src.config import settings
from src.models.schemas import Chunk, QueryResult, ChunkMetadata

logger = logging.getLogger(__name__)

COLLECTION_NAME = "research_chunks"


class VectorStore:
    """
    ChromaDB-backed vector store for chunk storage and retrieval.
    """

    def __init__(self):
        logger.info(f"Initializing ChromaDB at: {settings.chroma_persist_dir}")
        self.client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"ChromaDB collection '{COLLECTION_NAME}' ready "
            f"({self.collection.count()} existing chunks)"
        )

    def add_chunks(self, chunks: list[Chunk]) -> int:
        """
        Add chunks with their embeddings to the vector store.

        Args:
            chunks: List of Chunk objects (must have embeddings set).

        Returns:
            Number of chunks added.
        """
        if not chunks:
            return 0

        ids = []
        embeddings = []
        documents = []
        metadatas = []

        for chunk in chunks:
            if chunk.embedding is None:
                logger.warning(f"Skipping chunk {chunk.id} — no embedding")
                continue

            ids.append(chunk.id)
            embeddings.append(chunk.embedding)
            documents.append(chunk.content)
            # ChromaDB metadata only supports simple types, so we serialize dicts
            table_json = json.dumps(chunk.metadata.table_data) if chunk.metadata.table_data else None

            metadatas.append({
                "source_file": chunk.metadata.source_file,
                "page_number": chunk.metadata.page_number,
                "section_heading": chunk.metadata.section_heading,
                "chunk_index": chunk.metadata.chunk_index,
                "element_type": chunk.metadata.element_type,
                "content_type": chunk.content_type,
                "confidence": chunk.metadata.confidence,
                "created_at": chunk.metadata.created_at,
                "image_path": chunk.metadata.image_path or "",
                "image_description": chunk.metadata.image_description or "",
                "latex_source": chunk.metadata.latex_source or "",
                "table_data_json": table_json or "",
            })

        if not ids:
            return 0

        # ChromaDB batch upsert (handles duplicates gracefully)
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        logger.info(f"Added {len(ids)} chunks to vector store")
        return len(ids)

    def search(
        self,
        query_embedding: list[float],
        top_k: int | None = None,
        filter_source: str | None = None,
        filter_type: str | None = None,
    ) -> list[QueryResult]:
        """
        Search the vector store by similarity.

        Args:
            query_embedding: The query vector.
            top_k: Number of results to return.
            filter_source: Optional filter by source filename.
            filter_type: Optional filter by content type.

        Returns:
            List of QueryResult objects sorted by relevance.
        """
        top_k = top_k or settings.top_k

        # Build where filter
        where_filter = None
        conditions = []
        if filter_source:
            conditions.append({"source_file": filter_source})
        if filter_type:
            conditions.append({"content_type": filter_type})

        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$and": conditions}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        query_results = []
        if results and results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                metadata_dict = results["metadatas"][0][i]
                distance = results["distances"][0][i]
                # ChromaDB stores cosine distance = 1 - cosine_similarity,
                # so similarity = 1.0 - distance (range: 0–1).
                similarity = 1.0 - distance

                if similarity < settings.similarity_threshold:
                    continue

                # Deserialize table data if present
                table_data = None
                table_json = metadata_dict.get("table_data_json")
                if table_json:
                    try:
                        table_data = json.loads(table_json)
                    except:
                        pass

                chunk = Chunk(
                    content=results["documents"][0][i],
                    content_type=metadata_dict.get("content_type", "text"),
                    metadata=ChunkMetadata(
                        source_file=metadata_dict.get("source_file", ""),
                        page_number=metadata_dict.get("page_number", 0),
                        section_heading=metadata_dict.get("section_heading", ""),
                        chunk_index=metadata_dict.get("chunk_index", 0),
                        element_type=metadata_dict.get("element_type", "paragraph"),
                        confidence=metadata_dict.get("confidence", 1.0),
                        created_at=metadata_dict.get("created_at", ""),
                        image_path=metadata_dict.get("image_path"),
                        image_description=metadata_dict.get("image_description"),
                        latex_source=metadata_dict.get("latex_source"),
                        table_data=table_data,
                    ),
                    id=chunk_id,
                )

                query_results.append(QueryResult(
                    chunk=chunk,
                    score=similarity,
                    rank=i + 1,
                ))

        logger.info(
            f"Search returned {len(query_results)} results "
            f"(top_k={top_k}, filter_source={filter_source})"
        )
        return query_results

    def get_all_chunks(self) -> list[dict]:
        """Return all stored chunks as {id, text} dicts — used by BM25 index builder."""
        try:
            result = self.collection.get(include=["documents"])
            ids = result.get("ids", [])
            docs = result.get("documents", [])
            return [{"id": id_, "text": text} for id_, text in zip(ids, docs)]
        except Exception as e:
            logger.warning(f"get_all_chunks failed: {e}")
            return []

    def delete_by_source(self, source_file: str) -> int:
        """Delete all chunks from a specific source file."""
        results = self.collection.get(
            where={"source_file": source_file},
            include=[],
        )
        if results and results["ids"]:
            self.collection.delete(ids=results["ids"])
            logger.info(f"Deleted {len(results['ids'])} chunks for '{source_file}'")
            return len(results["ids"])
        return 0

    def get_all_sources(self) -> list[str]:
        """Get a list of all unique source filenames in the store."""
        results = self.collection.get(include=["metadatas"])
        sources = set()
        if results and results["metadatas"]:
            for meta in results["metadatas"]:
                source = meta.get("source_file", "")
                if source:
                    sources.add(source)
        return sorted(sources)

    @property
    def count(self) -> int:
        """Total number of chunks in the store."""
        return self.collection.count()
