"""
FastAPI REST API routes.
Covers all 20 system features via dedicated endpoints.
"""

import os
import shutil
import tempfile
import logging
import threading
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from src.ingestion.pipeline import IngestionPipeline
from src.retrieval.rag_pipeline import RAGPipeline
from src.agents.research_agent import ResearchAgent

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Lazy-initialized singletons (avoid loading heavy models at import time)
# ---------------------------------------------------------------------------

_ingestion_pipeline: IngestionPipeline | None = None
_rag_pipeline: RAGPipeline | None = None
_agent: ResearchAgent | None = None


def get_ingestion_pipeline() -> IngestionPipeline:
    global _ingestion_pipeline
    if _ingestion_pipeline is None:
        _ingestion_pipeline = IngestionPipeline()
    return _ingestion_pipeline


def get_rag_pipeline() -> RAGPipeline:
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline


def get_agent() -> ResearchAgent:
    global _agent
    if _agent is None:
        _agent = ResearchAgent()
    return _agent


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class LLMConfig(BaseModel):
    """Per-request overrides for model and generation parameters."""
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=32768)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    seed: int | None = None
    reasoning_effort: str | None = None  # "low" | "medium" | "high"


class TunableRequest(BaseModel):
    """Shared base for requests that allow LLM + retrieval overrides."""
    llm_config: LLMConfig | None = None
    similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class QueryRequest(TunableRequest):
    question: str
    top_k: int = 10
    filter_source: str | None = None


class AgentQueryRequest(TunableRequest):
    question: str
    chat_history: list[dict] = []


class SummarizeRequest(TunableRequest):
    source_file: str | None = None
    top_k: int = 20


class CompareRequest(TunableRequest):
    paper1: str
    paper2: str


class LiteratureSurveyRequest(TunableRequest):
    topic: str = ""
    top_k: int = 30


class ResearchGapsRequest(TunableRequest):
    source_file: str | None = None


class ExplainRequest(TunableRequest):
    concept: str
    source_file: str | None = None


class RecommendRequest(TunableRequest):
    interest: str
    top_k: int = 20


class TrendsRequest(TunableRequest):
    pass


class MultiDocRequest(TunableRequest):
    question: str
    top_k: int = 20


class QueryResponse(BaseModel):
    answer: str
    citations: list[dict]
    query: str
    intent: str
    chunks_used: int


class AgentQueryResponse(BaseModel):
    answer: str
    citations: list[dict]
    query: str
    intent: str
    chunks_used: int
    reasoning_steps: list[dict]
    total_steps: int


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    total_pages: int
    total_chunks: int
    status: str
    ingested_at: str


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _llm_kwargs(req: TunableRequest) -> dict:
    """Extract llm_config + similarity_threshold as kwargs for pipeline calls."""
    return {
        "llm_config": req.llm_config.model_dump(exclude_none=True) if req.llm_config else None,
        "similarity_threshold": req.similarity_threshold,
    }


def _to_query_response(resp) -> QueryResponse:
    return QueryResponse(
        answer=resp.answer,
        citations=resp.citations,
        query=resp.query,
        intent=resp.intent,
        chunks_used=resp.chunks_used,
    )


# ---------------------------------------------------------------------------
# Document management
# ---------------------------------------------------------------------------

_ingest_lock = threading.Lock()  # serialize document ingestion


def _ingest_in_background(saved_path: str, filename: str):
    """Run the full ingestion pipeline in a background thread (serialized)."""
    with _ingest_lock:
        try:
            pipeline = get_ingestion_pipeline()
            pipeline.ingest_file(saved_path, filename)
            logger.info(f"Background ingestion completed for {filename}")
        except Exception as e:
            logger.error(f"Background ingestion failed for {filename}: {e}")


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a PDF research paper.
    Returns immediately with status 'processing'.
    Actual ingestion runs in a background thread — poll GET /documents for updates.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext != ".pdf":
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Only PDF is accepted.",
        )

    try:
        # Save to a persistent temp file (not auto-deleted)
        from src.config import settings, ensure_directories
        ensure_directories()

        tmp_dir = os.path.join(settings.upload_dir, "_tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        saved_path = os.path.join(tmp_dir, file.filename)
        with open(saved_path, "wb") as f:
            f.write(await file.read())

        # Kick off ingestion in a background thread
        thread = threading.Thread(
            target=_ingest_in_background,
            args=(saved_path, file.filename),
            daemon=True,
        )
        thread.start()

        from datetime import datetime
        return DocumentResponse(
            id="processing",
            filename=file.filename,
            file_type="pdf",
            total_pages=0,
            total_chunks=0,
            status="processing",
            ingested_at=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents():
    """List all ingested documents."""
    docs = get_ingestion_pipeline().get_all_documents()
    return [
        DocumentResponse(
            id=d.id,
            filename=d.filename,
            file_type=d.file_type,
            total_pages=d.total_pages,
            total_chunks=d.total_chunks,
            status=d.status,
            ingested_at=d.ingested_at,
        )
        for d in docs
    ]


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document and all its indexed chunks."""
    if not get_ingestion_pipeline().delete_document(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": f"Document {doc_id} deleted"}


# ---------------------------------------------------------------------------
# Core RAG features
# ---------------------------------------------------------------------------

@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """Answer a question using single-shot RAG."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        return _to_query_response(
            get_rag_pipeline().query(
                question=request.question,
                top_k=request.top_k,
                filter_source=request.filter_source,
                **_llm_kwargs(request),
            )
        )
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent", response_model=AgentQueryResponse)
async def agent_query(request: AgentQueryRequest):
    """
    Answer a question using the ReAct agent with multi-hop retrieval.
    Supports complex, multi-step questions and conversational context.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        resp = get_agent().run(
            question=request.question,
            chat_history=request.chat_history,
            llm_config=(
                request.llm_config.model_dump(exclude_none=True)
                if request.llm_config else None
            ),
        )
        return AgentQueryResponse(
            answer=resp.answer,
            citations=resp.citations,
            query=resp.query,
            intent=resp.intent,
            chunks_used=resp.chunks_used,
            reasoning_steps=[
                {
                    "step": s.step_number,
                    "thought": s.thought,
                    "action": s.action,
                    "action_input": s.action_input,
                    "observation": s.observation,
                }
                for s in resp.reasoning_steps
            ],
            total_steps=resp.total_steps,
        )
    except Exception as e:
        logger.error(f"Agent query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summarize", response_model=QueryResponse)
async def summarize_document(request: SummarizeRequest):
    """Summarize one or all uploaded papers."""
    try:
        return _to_query_response(
            get_rag_pipeline().summarize(
                source_file=request.source_file,
                top_k=request.top_k,
                **_llm_kwargs(request),
            )
        )
    except Exception as e:
        logger.error(f"Summarize failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare", response_model=QueryResponse)
async def compare_papers(request: CompareRequest):
    """Compare two research papers side-by-side."""
    if not request.paper1 or not request.paper2:
        raise HTTPException(status_code=400, detail="Both paper1 and paper2 are required")
    try:
        return _to_query_response(
            get_rag_pipeline().compare(
                request.paper1, request.paper2, **_llm_kwargs(request)
            )
        )
    except Exception as e:
        logger.error(f"Compare failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/literature-survey", response_model=QueryResponse)
async def literature_survey(request: LiteratureSurveyRequest):
    """Generate a literature survey from the uploaded papers."""
    try:
        return _to_query_response(
            get_rag_pipeline().literature_survey(
                topic=request.topic,
                top_k=request.top_k,
                **_llm_kwargs(request),
            )
        )
    except Exception as e:
        logger.error(f"Literature survey failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/research-gaps", response_model=QueryResponse)
async def research_gaps(request: ResearchGapsRequest):
    """Identify research gaps and future directions."""
    try:
        return _to_query_response(
            get_rag_pipeline().identify_gaps(
                source_file=request.source_file, **_llm_kwargs(request)
            )
        )
    except Exception as e:
        logger.error(f"Research gaps failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explain", response_model=QueryResponse)
async def explain_concept(request: ExplainRequest):
    """Explain a technical concept, diagram, or table found in the papers."""
    if not request.concept.strip():
        raise HTTPException(status_code=400, detail="Concept cannot be empty")
    try:
        return _to_query_response(
            get_rag_pipeline().explain(
                concept=request.concept,
                source_file=request.source_file,
                **_llm_kwargs(request),
            )
        )
    except Exception as e:
        logger.error(f"Explain failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommend", response_model=QueryResponse)
async def recommend_papers(request: RecommendRequest):
    """Recommend papers based on a research interest."""
    if not request.interest.strip():
        raise HTTPException(status_code=400, detail="Interest cannot be empty")
    try:
        return _to_query_response(
            get_rag_pipeline().recommend(
                interest=request.interest,
                top_k=request.top_k,
                **_llm_kwargs(request),
            )
        )
    except Exception as e:
        logger.error(f"Recommend failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trends", response_model=QueryResponse)
async def research_trends(request: TrendsRequest = TrendsRequest()):
    """Analyse research trends across all uploaded papers."""
    try:
        return _to_query_response(
            get_rag_pipeline().analyze_trends(**_llm_kwargs(request))
        )
    except Exception as e:
        logger.error(f"Trends failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/multi-doc", response_model=QueryResponse)
async def multi_doc_query(request: MultiDocRequest):
    """Answer a question by reasoning across multiple papers simultaneously."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        return _to_query_response(
            get_rag_pipeline().multi_doc_query(
                question=request.question,
                top_k=request.top_k,
                **_llm_kwargs(request),
            )
        )
    except Exception as e:
        logger.error(f"Multi-doc query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Multimodal AI Research Assistant"}


# ---------------------------------------------------------------------------
# Model catalogue — curated Groq text-generation models with usage guidance
# ---------------------------------------------------------------------------

AVAILABLE_MODELS = [
    {
        "id": "openai/gpt-oss-120b",
        "label": "GPT-OSS 120B — Highest quality",
        "family": "OpenAI",
        "best_for": "Deep reasoning, literature surveys, complex multi-hop questions",
        "supports_reasoning_effort": True,
    },
    {
        "id": "openai/gpt-oss-20b",
        "label": "GPT-OSS 20B — Fast & capable",
        "family": "OpenAI",
        "best_for": "Quick Q&A with good reasoning when latency matters",
        "supports_reasoning_effort": True,
    },
    {
        "id": "llama-3.3-70b-versatile",
        "label": "Llama 3.3 70B — Balanced default",
        "family": "Meta",
        "best_for": "General research Q&A, summarization, everyday RAG",
        "supports_reasoning_effort": False,
    },
    {
        "id": "llama-3.1-8b-instant",
        "label": "Llama 3.1 8B — Ultra-fast",
        "family": "Meta",
        "best_for": "Low-latency lookups, simple factual questions, drafts",
        "supports_reasoning_effort": False,
    },
    {
        "id": "qwen/qwen3-32b",
        "label": "Qwen3 32B — Strong reasoning (multilingual)",
        "family": "Qwen",
        "best_for": "Technical reasoning, math-heavy papers, non-English content",
        "supports_reasoning_effort": True,
    },
    {
        "id": "groq/compound",
        "label": "Groq Compound — Agentic / tool-use",
        "family": "Groq",
        "best_for": "Agent Mode multi-hop workflows and tool calling",
        "supports_reasoning_effort": True,
    },
    {
        "id": "groq/compound-mini",
        "label": "Groq Compound Mini — Fast agent",
        "family": "Groq",
        "best_for": "Faster agent runs when quality tradeoff is acceptable",
        "supports_reasoning_effort": True,
    },
]


@router.get("/models")
async def list_models():
    """Return the curated list of selectable Groq text models with guidance."""
    from src.config import settings
    return {
        "default": settings.llm_model,
        "models": AVAILABLE_MODELS,
        "defaults": {
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
            "top_p": settings.llm_top_p,
            "frequency_penalty": settings.llm_frequency_penalty,
            "presence_penalty": settings.llm_presence_penalty,
            "reasoning_effort": settings.llm_reasoning_effort,
            "top_k": settings.top_k,
            "similarity_threshold": settings.similarity_threshold,
        },
    }
