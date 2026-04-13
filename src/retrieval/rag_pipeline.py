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
    ) -> GenerationResponse:
        """Answer a question using retrieved context."""
        logger.info(f"RAG query: '{question[:80]}'")

        results = self.retriever.retrieve(
            query=question,
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
                query=question,
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
            query=question,
            intent="question_answering",
            chunks_used=len(results),
        )

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
        """Summarize a specific paper or all uploaded papers."""
        query = "main contributions methodology results conclusions abstract"
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
            query=f"Summarize: {source_file or 'all documents'}",
            intent="summarization",
            chunks_used=len(results),
        )

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
            query=f"Compare: {paper1} vs {paper2}",
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
        """Generate a literature survey from the uploaded papers."""
        logger.info(f"Literature survey on topic: '{topic or 'general'}'")

        query = topic if topic else "contributions methodology evaluation results"
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
            query=f"Literature survey: {topic or 'all papers'}",
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
            query="Research gap identification",
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
            query=f"Explain: {concept}",
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
            query=f"Recommend for: {interest}",
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
            query="Research trend analysis",
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
        Retrieves broadly (no source filter) to ensure multi-paper coverage.
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
            query=question,
            intent="multi_doc_reasoning",
            chunks_used=len(results),
        )
