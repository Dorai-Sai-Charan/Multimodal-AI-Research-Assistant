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
from pydantic import BaseModel

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

class QueryRequest(BaseModel):
    question: str
    top_k: int = 10
    filter_source: str | None = None


class AgentQueryRequest(BaseModel):
    question: str
    chat_history: list[dict] = []


class SummarizeRequest(BaseModel):
    source_file: str | None = None
    top_k: int = 20


class CompareRequest(BaseModel):
    paper1: str
    paper2: str


class LiteratureSurveyRequest(BaseModel):
    topic: str = ""
    top_k: int = 30


class ResearchGapsRequest(BaseModel):
    source_file: str | None = None


class ExplainRequest(BaseModel):
    concept: str
    source_file: str | None = None


class RecommendRequest(BaseModel):
    interest: str
    top_k: int = 20


class MultiDocRequest(BaseModel):
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
            get_rag_pipeline().compare(request.paper1, request.paper2)
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
            get_rag_pipeline().identify_gaps(source_file=request.source_file)
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
            )
        )
    except Exception as e:
        logger.error(f"Recommend failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trends", response_model=QueryResponse)
async def research_trends():
    """Analyse research trends across all uploaded papers."""
    try:
        return _to_query_response(get_rag_pipeline().analyze_trends())
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
