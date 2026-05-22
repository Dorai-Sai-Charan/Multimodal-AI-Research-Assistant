"""
Retrieval pipeline: query → embed → hybrid-search → rerank → MMR → return.
Implements: BM25+dense RRF fusion, cross-encoder reranking, MMR diversity, HyDE.
"""

import os
import logging
import math
import numpy as np
from src.storage.embedding_service import EmbeddingService
from src.storage.vector_store import VectorStore
from src.models.schemas import QueryResult
from src.config import settings

logger = logging.getLogger(__name__)


class Retriever:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore()
        self._bm25_corpus: list[str] = []
        self._bm25_ids: list[str] = []
        self._bm25_index = None
        self._cross_encoder = None

    # ------------------------------------------------------------------
    # BM25 index
    # ------------------------------------------------------------------

    def build_bm25_index(self) -> None:
        """Build (or rebuild) the in-memory BM25 index from all stored chunks."""
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            logger.warning("rank-bm25 not installed; BM25 unavailable. pip install rank-bm25")
            return
        chunks = self.vector_store.get_all_chunks()
        if not chunks:
            logger.warning("BM25 index empty — no chunks in vector store yet")
            return
        self._bm25_corpus = [c["text"] for c in chunks]
        self._bm25_ids = [c["id"] for c in chunks]
        tokenized = [text.lower().split() for text in self._bm25_corpus]
        self._bm25_index = BM25Okapi(tokenized)
        logger.info(f"BM25 index built with {len(self._bm25_corpus)} chunks")

    def _bm25_retrieve(self, query: str, top_k: int) -> list[tuple[str, float]]:
        """Return list of (chunk_id, bm25_score) sorted desc."""
        if self._bm25_index is None:
            return []
        tokens = query.lower().split()
        scores = self._bm25_index.get_scores(tokens)
        ranked = sorted(
            zip(self._bm25_ids, scores), key=lambda x: x[1], reverse=True
        )
        return ranked[:top_k]

    # ------------------------------------------------------------------
    # RRF fusion
    # ------------------------------------------------------------------

    def _rrf_fusion(
        self,
        dense_results: list[QueryResult],
        bm25_results: list[tuple[str, float]],
        k: int = 60,
    ) -> list[QueryResult]:
        """Merge dense and BM25 rankings with Reciprocal Rank Fusion."""
        scores: dict[str, float] = {}
        id_to_result: dict[str, QueryResult] = {}

        for rank, r in enumerate(dense_results):
            chunk_id = r.chunk.id if hasattr(r.chunk, "id") else str(rank)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rank + k)
            id_to_result[chunk_id] = r

        for rank, (chunk_id, _) in enumerate(bm25_results):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rank + k)

        # Sort by RRF score, only return results that exist in dense_results
        fused_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
        fused = []
        for cid in fused_ids:
            if cid in id_to_result:
                result = id_to_result[cid]
                result.score = scores[cid]
                fused.append(result)
        return fused

    # ------------------------------------------------------------------
    # Cross-encoder reranking
    # ------------------------------------------------------------------

    def _get_cross_encoder(self):
        if self._cross_encoder is None:
            try:
                from sentence_transformers import CrossEncoder
                self._cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                logger.info("Cross-encoder loaded")
            except Exception as e:
                logger.warning(f"Cross-encoder unavailable: {e}")
                self._cross_encoder = False  # mark failed so we don't retry
        return self._cross_encoder if self._cross_encoder else None

    def _rerank(self, query: str, results: list[QueryResult], top_k: int) -> list[QueryResult]:
        """Rerank using cross-encoder; fall back to original order on failure."""
        ce = self._get_cross_encoder()
        if ce is None or not results:
            return results[:top_k]
        try:
            pairs = [(query, r.chunk.content) for r in results]
            scores = ce.predict(pairs)
            ranked = sorted(zip(results, scores), key=lambda x: x[1], reverse=True)
            reranked = [r for r, _ in ranked[:top_k]]
            logger.info(f"Cross-encoder reranked {len(results)} → {len(reranked)} results")
            return reranked
        except Exception as e:
            logger.warning(f"Cross-encoder reranking failed: {e}")
            return results[:top_k]

    # ------------------------------------------------------------------
    # MMR diversity
    # ------------------------------------------------------------------

    @staticmethod
    def _jaccard(a: str, b: str) -> float:
        sa, sb = set(a.lower().split()), set(b.lower().split())
        return len(sa & sb) / len(sa | sb) if (sa | sb) else 0.0

    def _mmr(
        self,
        results: list[QueryResult],
        lambda_param: float = 0.7,
    ) -> list[QueryResult]:
        """Maximal Marginal Relevance using Jaccard text similarity for diversity."""
        if len(results) <= 1:
            return results
        selected: list[QueryResult] = []
        remaining = list(results)
        while remaining:
            if not selected:
                selected.append(remaining.pop(0))
                continue
            best_idx, best_score = 0, -math.inf
            for i, cand in enumerate(remaining):
                sim_q = cand.score
                max_sim = max(
                    self._jaccard(cand.chunk.content, s.chunk.content)
                    for s in selected
                )
                score = lambda_param * sim_q - (1 - lambda_param) * max_sim
                if score > best_score:
                    best_score, best_idx = score, i
            selected.append(remaining.pop(best_idx))
        return selected

    # ------------------------------------------------------------------
    # HyDE
    # ------------------------------------------------------------------

    def _hyde_embed(self, query: str) -> list[float]:
        """Generate a hypothetical answer and embed it for improved retrieval."""
        try:
            from src.generation.llm_client import LLMClient
            llm = LLMClient()
            hypo_prompt = (
                f"Write a short passage (2-3 sentences) that would appear in an "
                f"academic paper answering: {query}"
            )
            hypo_text = llm.generate(hypo_prompt)
            if hypo_text and len(hypo_text) > 20:
                return self.embedding_service.embed_text(hypo_text)
        except Exception as e:
            logger.warning(f"HyDE embedding failed, using raw query: {e}")
        return self.embedding_service.embed_text(query)

    # ------------------------------------------------------------------
    # Main retrieve
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filter_source: str | None = None,
        filter_type: str | None = None,
        similarity_threshold: float | None = None,
        use_hyde: bool = False,
    ) -> list[QueryResult]:
        """
        Full hybrid retrieval pipeline:
        1. Dense embedding (or HyDE) → ChromaDB
        2. BM25 keyword search (if index available)
        3. RRF fusion
        4. Cross-encoder reranking
        5. MMR diversity
        """
        logger.info(f"Retrieving for: '{query[:80]}' (top_k={top_k}, hyde={use_hyde})")

        candidate_k = max(top_k * 2, 20)

        # Step 1: Dense retrieval
        query_embedding = (
            self._hyde_embed(query) if use_hyde
            else self.embedding_service.embed_text(query)
        )
        dense_results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=candidate_k,
            filter_source=filter_source,
            filter_type=filter_type,
        )

        # Step 2: BM25 retrieval
        bm25_results = self._bm25_retrieve(query, candidate_k)

        # Step 3: RRF fusion (or pure dense if BM25 unavailable)
        if bm25_results:
            fused = self._rrf_fusion(dense_results, bm25_results)
        else:
            logger.debug("BM25 index not available; using dense-only results")
            fused = dense_results

        # Step 4: Similarity threshold filter
        threshold = similarity_threshold if similarity_threshold is not None else settings.similarity_threshold
        before = len(fused)
        fused = [r for r in fused if r.score >= threshold]
        if before != len(fused):
            logger.info(f"Threshold {threshold} filtered {before-len(fused)}/{before}")

        # Step 5: Cross-encoder reranking (top 20 → top top_k)
        reranked = self._rerank(query, fused[:20], top_k)

        # Step 6: MMR diversity
        diverse = self._mmr(reranked)

        logger.info(f"Final result count: {len(diverse)}")
        return diverse

    # ------------------------------------------------------------------
    # Context building
    # ------------------------------------------------------------------

    def build_context(self, results: list[QueryResult], max_context_length: int = 4000) -> str:
        context_parts = []
        total_length = 0
        for result in results:
            chunk = result.chunk
            citation = f"[Source: {chunk.metadata.source_file}, Page {chunk.metadata.page_number}"
            if chunk.metadata.section_heading:
                citation += f", Section: {chunk.metadata.section_heading}"
            citation += f"] (Relevance: {result.score:.2f})"
            truncated = chunk.content[:600] if len(chunk.content) > 600 else chunk.content
            chunk_text = f"{citation}\n{truncated}\n"
            context_parts.append(chunk_text)
            total_length += len(chunk_text)
        return "\n---\n".join(context_parts)

    # ------------------------------------------------------------------
    # Citations
    # ------------------------------------------------------------------

    def get_citations(self, results: list[QueryResult]) -> list[dict]:
        """Extract structured citations including visual metadata."""
        citations = []
        seen = set()
        for result in results:
            chunk = result.chunk
            meta = chunk.metadata
            is_visual = meta.element_type in ("figure", "table", "equation")
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
