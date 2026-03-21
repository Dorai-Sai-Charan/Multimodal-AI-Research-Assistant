"""
FastAPI REST API routes.
"""

import os
import tempfile
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pydantic import BaseModel

from src.ingestion.pipeline import IngestionPipeline
from src.retrieval.rag_pipeline import RAGPipeline

logger = logging.getLogger(__name__)
router = APIRouter()

# Lazy-initialized singletons
_ingestion_pipeline = None
_rag_pipeline = None


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


# --- Request/Response Models ---

class QueryRequest(BaseModel):
    question: str
    top_k: int = 10
    filter_source: str | None = None


class QueryResponse(BaseModel):
    answer: str
    citations: list[dict]
    query: str
    intent: str
    chunks_used: int


class SummarizeRequest(BaseModel):
    source_file: str | None = None
    top_k: int = 20


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    total_pages: int
    total_chunks: int
    status: str
    ingested_at: str


# --- Endpoints ---

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...)):
    """Upload and ingest a PDF document."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Validate file type
    allowed_extensions = {".pdf"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {allowed_extensions}",
        )

    try:
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Ingest
        pipeline = get_ingestion_pipeline()
        doc = pipeline.ingest_file(tmp_path, file.filename)

        # Cleanup temp file
        os.unlink(tmp_path)

        return DocumentResponse(
            id=doc.id,
            filename=doc.filename,
            file_type=doc.file_type,
            total_pages=doc.total_pages,
            total_chunks=doc.total_chunks,
            status=doc.status,
            ingested_at=doc.ingested_at,
        )

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """Ask a question about uploaded documents."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        pipeline = get_rag_pipeline()
        response = pipeline.query(
            question=request.question,
            top_k=request.top_k,
            filter_source=request.filter_source,
        )

        return QueryResponse(
            answer=response.answer,
            citations=response.citations,
            query=response.query,
            intent=response.intent,
            chunks_used=response.chunks_used,
        )

    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summarize", response_model=QueryResponse)
async def summarize_document(request: SummarizeRequest):
    """Summarize uploaded documents."""
    try:
        pipeline = get_rag_pipeline()
        response = pipeline.summarize(
            source_file=request.source_file,
            top_k=request.top_k,
        )

        return QueryResponse(
            answer=response.answer,
            citations=response.citations,
            query=response.query,
            intent=response.intent,
            chunks_used=response.chunks_used,
        )

    except Exception as e:
        logger.error(f"Summarize failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents():
    """List all ingested documents."""
    pipeline = get_ingestion_pipeline()
    docs = pipeline.get_all_documents()
    return [
        DocumentResponse(
            id=doc.id,
            filename=doc.filename,
            file_type=doc.file_type,
            total_pages=doc.total_pages,
            total_chunks=doc.total_chunks,
            status=doc.status,
            ingested_at=doc.ingested_at,
        )
        for doc in docs
    ]


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document and its chunks."""
    pipeline = get_ingestion_pipeline()
    success = pipeline.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": f"Document {doc_id} deleted successfully"}


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Multimodal AI Research Assistant"}
