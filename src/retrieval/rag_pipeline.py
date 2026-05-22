"""
RAG Pipeline — combines retrieval and generation.
Covers: Q&A, summarization, paper comparison, literature survey,
research gap identification, concept explanation, paper recommendation,
research trend analysis, and multi-document reasoning.

All public methods accept an optional ``llm_config`` dict (model + generation
parameters) and ``similarity_threshold`` so the frontend settings panel can
override them per request.
"""

import logging
from src.retrieval.retriever import Retriever
from src.generation.llm_client import LLMClient
from src.generation.prompts import (
    QA_PROMPT,
    SUMMARIZE_PROMPT,
    COMPARE_PAPERS_PROMPT,
    LITERATURE_SURVEY_PROMPT,
    RESEARCH_GAP_PROMPT,
    CONCEPT_EXPLANATION_PROMPT,
    RECOMMENDATION_PROMPT,
    TREND_ANALYSIS_PROMPT,
    MULTI_DOC_PROMPT,
)
from src.models.schemas import GenerationResponse

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Retrieval-Augmented Generation pipeline.
    Each public method maps to one user-facing feature.
    """

    def __init__(self):
        self.retriever = Retriever()
        self.llm_client = LLMClient()

    # ------------------------------------------------------------------
    # 1. Question Answering (single-shot RAG)
    # ------------------------------------------------------------------

    def query(
        self,
        question: str,
        top_k: int = 10,
        filter_source: str | None = None,
        llm_config: dict | None = None,
        similarity_threshold: float | None = None,
        chat_history: list[dict] | None = None,
    ) -> GenerationResponse:
        """Answer a question using retrieved context.

        Fix 9 (2.10): If chat_history has at least 2 entries, rewrite the
        question as a standalone question using the last 2 turns before
        retrieval so the retriever can find the right chunks.
        """
        logger.info(f"RAG query: '{question[:80]}'")

        retrieval_question = question

        # Fix 9: chat history — rewrite question as standalone if history present
        if chat_history and len(chat_history) >= 2:
            last_two = chat_history[-2:]
            history_text = "\n".join(
                f"{turn.get('role', 'user').capitalize()}: {turn.get('content', '')}"
                for turn in last_two
            )
            rewrite_prompt = (
                f"Given this conversation history:\n{history_text}\n\n"
                f"Rephrase the following question as a standalone question "
                f"that can be understood without the conversation history. "
                f"Return only the rephrased question, nothing else.\n\n"
                f"Question: {question}"
            )
            try:
                retrieval_question = self.llm_client.generate(
                    rewrite_prompt, temperature=0.0, max_tokens=200
                ).strip()
                logger.info(f"Rewrote question to: '{retrieval_question[:80]}'")
            except Exception as e:
                logger.warning(f"Query rewriting failed, using original question: {e}")
                retrieval_question = question

        results = self.retriever.retrieve(
            query=retrieval_question,
            top_k=top_k,
            filter_source=filter_source,
            similarity_threshold=similarity_threshold,
        )

        if not results:
            return GenerationResponse(
                answer=(
                    "I couldn't find relevant information in the uploaded documents. "
                    "Please rephrase your question or upload relevant papers."
                ),
                citations=[],
                question=question,
                intent="question_answering",
                chunks_used=0,
            )

        context = self.retriever.build_context(results)
        answer = self.llm_client.generate_with_context(
            QA_PROMPT, llm_config=llm_config, context=context, question=question
        )

        return GenerationResponse(
            answer=answer,
            citations=self.retriever.get_citations(results),
            question=question,
            intent="question_answering",
            chunks_used=len(results),
        )

    def build_query_prompt(
        self,
        question: str,
        top_k: int = 10,
        filter_source: str | None = None,
        similarity_threshold: float | None = None,
        chat_history: list[dict] | None = None,
    ) -> tuple[str, list]:
        """
        Perform retrieval and build the final QA prompt string without calling
        the LLM.  Returns ``(prompt_string, results_list)`` so the streaming
        endpoint can pass the prompt directly to ``generate_stream()``.

        When ``chat_history`` has at least 2 entries the question is rewritten
        as a standalone question (same logic as ``query()``) so the retriever
        finds the right chunks even for follow-up questions.
        """
        logger.info(f"Building query prompt for: '{question[:80]}'")

        retrieval_question = question

        # Rewrite follow-up questions as standalone questions (mirrors query())
        if chat_history and len(chat_history) >= 2:
            last_two = chat_history[-2:]
            history_text = "\n".join(
                f"{turn.get('role', 'user').capitalize()}: {turn.get('content', '')}"
                for turn in last_two
            )
            rewrite_prompt = (
                f"Given this conversation history:\n{history_text}\n\n"
                f"Rephrase the following question as a standalone question "
                f"that can be understood without the conversation history. "
                f"Return only the rephrased question, nothing else.\n\n"
                f"Question: {question}"
            )
            try:
                retrieval_question = self.llm_client.generate(
                    rewrite_prompt, temperature=0.0, max_tokens=200
                ).strip()
                logger.info(f"Rewrote question to: '{retrieval_question[:80]}'")
            except Exception as e:
                logger.warning(f"Query rewriting failed, using original question: {e}")
                retrieval_question = question

        results = self.retriever.retrieve(
            query=retrieval_question,
            top_k=top_k,
            filter_source=filter_source,
            similarity_threshold=similarity_threshold,
        )

        if not results:
            # Return a prompt that will produce the "no info found" message
            no_context_prompt = QA_PROMPT.format(
                context="(No relevant documents found.)",
                question=question,
            )
            return no_context_prompt, []

        context = self.retriever.build_context(results)
        prompt = QA_PROMPT.format(context=context, question=question)
        return prompt, results

    # ------------------------------------------------------------------
    # 2. Summarization
    # ------------------------------------------------------------------

    def summarize(
        self,
        source_file: str | None = None,
        top_k: int = 20,
        llm_config: dict | None = None,
        similarity_threshold: float | None = None,
    ) -> GenerationResponse:
        """Summarize a specific paper or all uploaded papers.

        Fix 8 (2.9): Build an adaptive retrieval query by first fetching early
        chunks (chunk_index == 0) to extract title/abstract keywords, then use
        those keywords as the retrieval query.  Falls back to the generic query
        string when no early chunks are found or keyword extraction fails.
        """
        # Fix 8: adaptive query — extract keywords from early chunks
        query = self._build_adaptive_summary_query(
            source_file=source_file,
            fallback="main contributions methodology results conclusions abstract",
        )

        results = self.retriever.retrieve(
            query=query,
            top_k=top_k,
            filter_source=source_file,
            similarity_threshold=similarity_threshold,
        )

        if not results:
            return GenerationResponse(
                answer="No documents found to summarize.",
                citations=[],
                intent="summarization",
            )

        context = self.retriever.build_context(results, max_context_length=6000)
        answer = self.llm_client.generate_with_context(
            SUMMARIZE_PROMPT, llm_config=llm_config, context=context
        )

        return GenerationResponse(
            answer=answer,
            citations=self.retriever.get_citations(results),
            question=f"Summarize: {source_file or 'all documents'}",
            intent="summarization",
            chunks_used=len(results),
        )

    def _build_adaptive_summary_query(
        self,
        source_file: str | None,
        fallback: str,
    ) -> str:
        """
        Fix 8 (2.9): Return a query derived from the earliest chunks of the
        document, or ``fallback`` if that is not possible.
        """
        try:
            vs = self.retriever.vector_store
            where: dict = {"chunk_index": {"$eq": 0}}
            if source_file:
                where = {"$and": [{"source_file": source_file}, {"chunk_index": {"$eq": 0}}]}

            early = vs.collection.get(
                where=where,
                include=["documents"],
            )
            docs = early.get("documents") or []
            if not docs:
                return fallback

            # Take up to the first two early chunks and extract key noun phrases
            sample_text = " ".join(d[:400] for d in docs[:2])
            # Simple keyword extraction: take words longer than 5 chars, deduplicated
            words = [
                w.strip(".,;:\"'()[]") for w in sample_text.split()
                if len(w.strip(".,;:\"'()[]")) > 5
            ]
            seen: set[str] = set()
            keywords: list[str] = []
            for w in words:
                lw = w.lower()
                if lw not in seen:
                    seen.add(lw)
                    keywords.append(w)
                if len(keywords) >= 15:
                    break

            if not keywords:
                return fallback

            return " ".join(keywords)
        except Exception as e:
            logger.warning(f"Adaptive summary query extraction failed: {e}")
            return fallback

    # ------------------------------------------------------------------
    # 3. Paper Comparison
    # ------------------------------------------------------------------

    def compare(
        self,
        paper1: str,
        paper2: str,
        llm_config: dict | None = None,
        similarity_threshold: float | None = None,
    ) -> GenerationResponse:
        """Compare two research papers side-by-side."""
        logger.info(f"Comparing: '{paper1}' vs '{paper2}'")
        broad_query = "methodology approach contributions results evaluation"

        results_a = self.retriever.retrieve(
            query=broad_query, top_k=15, filter_source=paper1,
            similarity_threshold=similarity_threshold,
        )
        results_b = self.retriever.retrieve(
            query=broad_query, top_k=15, filter_source=paper2,
            similarity_threshold=similarity_threshold,
        )

        if not results_a and not results_b:
            return GenerationResponse(
                answer="Could not find content for either paper. Make sure both are uploaded.",
                citations=[],
                intent="comparison",
            )

        context_a = self.retriever.build_context(results_a, max_context_length=3000)
        context_b = self.retriever.build_context(results_b, max_context_length=3000)

        answer = self.llm_client.generate_with_context(
            COMPARE_PAPERS_PROMPT,
            llm_config=llm_config,
            paper1_name=paper1,
            context_a=context_a,
            paper2_name=paper2,
            context_b=context_b,
        )

        return GenerationResponse(
            answer=answer,
            citations=self.retriever.get_citations(results_a + results_b),
            question=f"Compare: {paper1} vs {paper2}",
            intent="comparison",
            chunks_used=len(results_a) + len(results_b),
        )

    # ------------------------------------------------------------------
    # 4. Literature Survey Generation
    # ------------------------------------------------------------------

    def literature_survey(
        self,
        topic: str = "",
        top_k: int = 30,
        llm_config: dict | None = None,
        similarity_threshold: float | None = None,
    ) -> GenerationResponse:
        """Generate a literature survey from the uploaded papers.

        Fix 7 (2.6): Instead of a single broad top_k query, retrieve up to 6
        chunks per available paper independently, then merge and pass all to
        the LLM.  Falls back to the original strategy when no source list can
        be obtained.
        """
        logger.info(f"Literature survey on topic: '{topic or 'general'}'")

        query = topic if topic else "contributions methodology evaluation results"

        # Fix 7: per-paper retrieval for diversity
        try:
            source_files = self.retriever.vector_store.get_all_sources()
        except Exception as e:
            logger.warning(f"Could not retrieve source list for per-paper survey: {e}")
            source_files = []

        if source_files:
            all_results: list = []
            seen_ids: set[str] = set()
            for source in source_files:
                per_paper = self.retriever.retrieve(
                    query=query,
                    top_k=6,
                    filter_source=source,
                    similarity_threshold=similarity_threshold,
                )
                for r in per_paper:
                    if r.chunk.id not in seen_ids:
                        all_results.append(r)
                        seen_ids.add(r.chunk.id)

            # Sort by relevance score descending
            all_results.sort(key=lambda r: r.score, reverse=True)
            results = all_results
        else:
            # Fallback to original single-query approach
            results = self.retriever.retrieve(
                query=query, top_k=top_k, similarity_threshold=similarity_threshold
            )

        if not results:
            return GenerationResponse(
                answer="No documents available. Please upload research papers first.",
                citations=[],
                intent="literature_survey",
            )

        context = self.retriever.build_context(results, max_context_length=8000)
        answer = self.llm_client.generate_with_context(
            LITERATURE_SURVEY_PROMPT,
            llm_config=llm_config,
            topic=topic or "the uploaded research papers",
            context=context,
        )

        return GenerationResponse(
            answer=answer,
            citations=self.retriever.get_citations(results),
            question=f"Literature survey: {topic or 'all papers'}",
            intent="literature_survey",
            chunks_used=len(results),
        )

    # ------------------------------------------------------------------
    # 5. Research Gap Identification
    # ------------------------------------------------------------------

    def identify_gaps(
        self,
        source_file: str | None = None,
        llm_config: dict | None = None,
        similarity_threshold: float | None = None,
    ) -> GenerationResponse:
        """Identify research gaps and future directions from uploaded papers."""
        logger.info("Identifying research gaps")

        gap_queries = [
            "limitations future work challenges open problems",
            "conclusion future directions",
            "drawbacks weaknesses shortcomings",
        ]

        all_results = []
        seen_ids: set[str] = set()

        for q in gap_queries:
            for r in self.retriever.retrieve(
                query=q, top_k=10, filter_source=source_file,
                similarity_threshold=similarity_threshold,
            ):
                if r.chunk.id not in seen_ids:
                    all_results.append(r)
                    seen_ids.add(r.chunk.id)

        if not all_results:
            return GenerationResponse(
                answer="No relevant content found. Please upload research papers first.",
                citations=[],
                intent="research_gaps",
            )

        context = self.retriever.build_context(all_results, max_context_length=6000)
        answer = self.llm_client.generate_with_context(
            RESEARCH_GAP_PROMPT, llm_config=llm_config, context=context
        )

        return GenerationResponse(
            answer=answer,
            citations=self.retriever.get_citations(all_results),
            question="Research gap identification",
            intent="research_gaps",
            chunks_used=len(all_results),
        )

    # ------------------------------------------------------------------
    # 6. Concept / Diagram / Table Explanation
    # ------------------------------------------------------------------

    def explain(
        self,
        concept: str,
        source_file: str | None = None,
        llm_config: dict | None = None,
        similarity_threshold: float | None = None,
    ) -> GenerationResponse:
        """Explain a technical concept, diagram description, or table found in the papers."""
        logger.info(f"Explaining concept: '{concept}'")

        results = self.retriever.retrieve(
            query=concept, top_k=12, filter_source=source_file,
            similarity_threshold=similarity_threshold,
        )

        if not results:
            return GenerationResponse(
                answer=f"No relevant content found for '{concept}' in the uploaded papers.",
                citations=[],
                intent="concept_explanation",
            )

        context = self.retriever.build_context(results, max_context_length=5000)
        answer = self.llm_client.generate_with_context(
            CONCEPT_EXPLANATION_PROMPT,
            llm_config=llm_config,
            concept=concept,
            context=context,
        )

        return GenerationResponse(
            answer=answer,
            citations=self.retriever.get_citations(results),
            question=f"Explain: {concept}",
            intent="concept_explanation",
            chunks_used=len(results),
        )

    # ------------------------------------------------------------------
    # 7. Related Paper Recommendation
    # ------------------------------------------------------------------

    def recommend(
        self,
        interest: str,
        top_k: int = 20,
        llm_config: dict | None = None,
        similarity_threshold: float | None = None,
    ) -> GenerationResponse:
        """Recommend which uploaded papers are most relevant to a given interest."""
        logger.info(f"Recommending papers for: '{interest}'")

        results = self.retriever.retrieve(
            query=interest, top_k=top_k, similarity_threshold=similarity_threshold
        )

        if not results:
            return GenerationResponse(
                answer="No papers available. Please upload research papers first.",
                citations=[],
                intent="recommendation",
            )

        context = self.retriever.build_context(results, max_context_length=6000)
        answer = self.llm_client.generate_with_context(
            RECOMMENDATION_PROMPT,
            llm_config=llm_config,
            query=interest,
            context=context,
        )

        return GenerationResponse(
            answer=answer,
            citations=self.retriever.get_citations(results),
            question=f"Recommend for: {interest}",
            intent="recommendation",
            chunks_used=len(results),
        )

    # ------------------------------------------------------------------
    # 8. Research Trend Analysis
    # ------------------------------------------------------------------

    def analyze_trends(
        self,
        llm_config: dict | None = None,
        similarity_threshold: float | None = None,
    ) -> GenerationResponse:
        """Analyse research trends across all uploaded papers."""
        logger.info("Analysing research trends")

        trend_queries = [
            "methodology approach technique method architecture",
            "results performance accuracy benchmark evaluation",
            "dataset training evaluation metric comparison",
        ]

        all_results = []
        seen_ids: set[str] = set()

        for q in trend_queries:
            for r in self.retriever.retrieve(
                query=q, top_k=15, similarity_threshold=similarity_threshold
            ):
                if r.chunk.id not in seen_ids:
                    all_results.append(r)
                    seen_ids.add(r.chunk.id)

        if not all_results:
            return GenerationResponse(
                answer="No documents available for trend analysis.",
                citations=[],
                intent="trend_analysis",
            )

        context = self.retriever.build_context(all_results, max_context_length=8000)
        answer = self.llm_client.generate_with_context(
            TREND_ANALYSIS_PROMPT, llm_config=llm_config, context=context
        )

        return GenerationResponse(
            answer=answer,
            citations=self.retriever.get_citations(all_results),
            question="Research trend analysis",
            intent="trend_analysis",
            chunks_used=len(all_results),
        )

    # ------------------------------------------------------------------
    # 9. Multi-document Reasoning
    # ------------------------------------------------------------------

    def multi_doc_query(
        self,
        question: str,
        top_k: int = 20,
        llm_config: dict | None = None,
        similarity_threshold: float | None = None,
    ) -> GenerationResponse:
        """
        Answer a question by synthesising information across multiple papers.

        Fix 6 (2.5): Enforce multi-paper coverage — if more than 80 % of the
        initial results come from a single paper, redistribute by retrieving
        top 5 chunks per paper separately and merging.
        """
        logger.info(f"Multi-doc query: '{question[:80]}'")

        results = self.retriever.retrieve(
            query=question, top_k=top_k, similarity_threshold=similarity_threshold
        )

        if not results:
            return GenerationResponse(
                answer="No relevant content found across the uploaded papers.",
                citations=[],
                intent="multi_doc_reasoning",
            )

        # Fix 6: check cross-paper coverage
        results = self._enforce_multi_paper_coverage(
            results=results,
            question=question,
            similarity_threshold=similarity_threshold,
        )

        context = self.retriever.build_context(results, max_context_length=7000)
        answer = self.llm_client.generate_with_context(
            MULTI_DOC_PROMPT,
            llm_config=llm_config,
            question=question,
            context=context,
        )

        return GenerationResponse(
            answer=answer,
            citations=self.retriever.get_citations(results),
            question=question,
            intent="multi_doc_reasoning",
            chunks_used=len(results),
        )

    def _enforce_multi_paper_coverage(
        self,
        results: list,
        question: str,
        similarity_threshold: float | None,
    ) -> list:
        """
        Fix 6 (2.5): If >80 % of retrieved results come from one paper,
        redistribute by querying each available paper separately (top 5 each)
        and merging the deduplicated results.
        """
        if not results:
            return results

        # Count results per source
        from collections import Counter
        source_counts: Counter = Counter(
            r.chunk.metadata.source_file for r in results
        )
        total = len(results)
        dominant_source, dominant_count = source_counts.most_common(1)[0]

        if dominant_count / total <= 0.8:
            # Coverage is already diverse
            return results

        logger.info(
            f"Multi-doc: {dominant_count}/{total} results from '{dominant_source}'. "
            "Redistributing across all papers."
        )

        try:
            all_sources = self.retriever.vector_store.get_all_sources()
        except Exception as e:
            logger.warning(f"Could not get source list for redistribution: {e}")
            return results

        merged: list = []
        seen_ids: set[str] = set()
        for source in all_sources:
            per_paper = self.retriever.retrieve(
                query=question,
                top_k=5,
                filter_source=source,
                similarity_threshold=similarity_threshold,
            )
            for r in per_paper:
                if r.chunk.id not in seen_ids:
                    merged.append(r)
                    seen_ids.add(r.chunk.id)

        if not merged:
            return results

        # Sort by relevance descending
        merged.sort(key=lambda r: r.score, reverse=True)
        return merged
