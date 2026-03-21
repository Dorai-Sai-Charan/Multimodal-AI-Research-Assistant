"""
RAG Pipeline — combines retrieval and generation.
This is the main query interface for the application.
"""

import logging
from src.retrieval.retriever import Retriever
from src.generation.llm_client import LLMClient
from src.generation.prompts import QA_PROMPT, SUMMARIZE_PROMPT
from src.models.schemas import GenerationResponse

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Retrieval-Augmented Generation pipeline.
    Handles: query → retrieve → build context → generate → format response.
    """

    def __init__(self):
        self.retriever = Retriever()
        self.llm_client = LLMClient()

    def query(
        self,
        question: str,
        top_k: int = 10,
        filter_source: str | None = None,
    ) -> GenerationResponse:
        """
        Answer a question using RAG.

        Args:
            question: User's natural language question.
            top_k: Number of chunks to retrieve.
            filter_source: Optional source file filter.

        Returns:
            GenerationResponse with answer and citations.
        """
        logger.info(f"RAG query: '{question[:80]}...'")

        # Step 1: Retrieve relevant chunks
        results = self.retriever.retrieve(
            query=question,
            top_k=top_k,
            filter_source=filter_source,
        )

        if not results:
            return GenerationResponse(
                answer="I couldn't find any relevant information in the uploaded documents to answer your question. Please try rephrasing or upload relevant documents.",
                citations=[],
                query=question,
                intent="question_answering",
                chunks_used=0,
            )

        # Step 2: Build context from retrieved chunks
        context = self.retriever.build_context(results)

        # Step 3: Generate answer using LLM
        answer = self.llm_client.generate_with_context(
            QA_PROMPT,
            context=context,
            question=question,
        )

        # Step 4: Extract citations
        citations = self.retriever.get_citations(results)

        return GenerationResponse(
            answer=answer,
            citations=citations,
            query=question,
            intent="question_answering",
            chunks_used=len(results),
        )

    def summarize(
        self,
        source_file: str | None = None,
        top_k: int = 20,
    ) -> GenerationResponse:
        """
        Summarize a document or all documents.

        Args:
            source_file: Specific document to summarize (or all if None).
            top_k: Number of chunks for context.

        Returns:
            GenerationResponse with summary.
        """
        # Retrieve broadly to cover the document
        query = "main contributions methodology results conclusions"
        results = self.retriever.retrieve(
            query=query,
            top_k=top_k,
            filter_source=source_file,
        )

        if not results:
            return GenerationResponse(
                answer="No documents found to summarize.",
                citations=[],
                intent="summarization",
            )

        context = self.retriever.build_context(results, max_context_length=6000)

        answer = self.llm_client.generate_with_context(
            SUMMARIZE_PROMPT,
            context=context,
        )

        citations = self.retriever.get_citations(results)

        return GenerationResponse(
            answer=answer,
            citations=citations,
            query=f"Summarize: {source_file or 'all documents'}",
            intent="summarization",
            chunks_used=len(results),
        )
