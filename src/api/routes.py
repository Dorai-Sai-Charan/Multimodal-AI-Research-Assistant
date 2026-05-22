"""
FastAPI REST API routes.
Covers all 20 system features via dedicated endpoints.
"""

import os
import re
import json
import asyncio
import shutil
import tempfile
import logging
import threading
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.ingestion.pipeline import IngestionPipeline
from src.retrieval.rag_pipeline import RAGPipeline
from src.agents.research_agent import ResearchAgent
from src.generation.humanizer import HumanizationEngine
from src.models.schemas import (
    TextAnalysisRequest,
    AIDetectionResponse,
    HumanizationResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Lazy-initialized singletons (avoid loading heavy models at import time)
# ---------------------------------------------------------------------------

_ingestion_pipeline: IngestionPipeline | None = None
_rag_pipeline: RAGPipeline | None = None
_agent: ResearchAgent | None = None
_humanizer: HumanizationEngine | None = None
_retriever = None


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


def get_humanizer() -> HumanizationEngine:
    global _humanizer
    if _humanizer is None:
        _humanizer = HumanizationEngine()
    return _humanizer


def get_retriever():
    global _retriever
    if _retriever is None:
        from src.retrieval.retriever import Retriever
        _retriever = Retriever()
    return _retriever


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
    chat_history: list[dict] | None = None


class AgentQueryRequest(TunableRequest):
    question: str
    chat_history: list[dict] = []
    filter_source: str | None = None


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
    question: str
    intent: str
    chunks_used: int


class AgentQueryResponse(BaseModel):
    answer: str
    citations: list[dict]
    question: str
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
    progress: str = ""


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
        question=resp.question,
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
            # Rebuild BM25 index so new chunks are searchable immediately
            try:
                get_retriever().build_bm25_index()
            except Exception as bm25_exc:
                logger.warning(f"BM25 index rebuild failed after ingestion: {bm25_exc}")
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

        # Fix 1: sanitize filename to prevent path traversal attacks
        safe_name = os.path.basename(file.filename)
        # Fix 4 (L11): normalize spaces and special characters in filename
        safe_name = re.sub(r'[^\w\-_\.]', '_', safe_name)
        safe_name = re.sub(r'_+', '_', safe_name)  # collapse multiple underscores
        saved_path = os.path.join(tmp_dir, safe_name)

        # Fix 2: enforce 50 MB file size limit
        contents = await file.read()
        if len(contents) > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 50MB.")

        # Fix 3: catch OSError separately to avoid leaking internal paths
        try:
            with open(saved_path, "wb") as f:
                f.write(contents)
        except OSError as oe:
            logger.error(f"Failed to write uploaded file: {oe}")
            raise HTTPException(status_code=500, detail="File processing failed. Please try again.")

        # Kick off ingestion in a background thread
        thread = threading.Thread(
            target=_ingest_in_background,
            args=(saved_path, safe_name),
            daemon=True,
        )
        thread.start()

        from datetime import datetime
        return DocumentResponse(
            id="processing",
            filename=safe_name,
            file_type="pdf",
            total_pages=0,
            total_chunks=0,
            status="processing",
            ingested_at=datetime.utcnow().isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed. Please try again.")


@router.post("/upload/batch")
async def upload_batch(files: list[UploadFile] = File(...)):
    """
    Upload multiple PDF files at once.
    Applies the same validation as single /upload (PDF only, 50 MB limit,
    filename sanitization, SHA-256 duplicate detection).
    Returns immediately — ingestion runs in background threads.
    Poll GET /documents for status updates.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    from src.config import settings, ensure_directories
    from datetime import datetime

    ensure_directories()
    tmp_dir = os.path.join(settings.upload_dir, "_tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    results = []
    for file in files:
        if not file.filename:
            results.append({"filename": "", "error": "Empty filename", "status": "rejected"})
            continue

        ext = os.path.splitext(file.filename)[1].lower()
        if ext != ".pdf":
            results.append({
                "filename": file.filename,
                "error": f"Unsupported file type '{ext}'. Only PDF is accepted.",
                "status": "rejected",
            })
            continue

        # Sanitize filename
        safe_name = os.path.basename(file.filename)
        safe_name = re.sub(r'[^\w\-_\.]', '_', safe_name)
        safe_name = re.sub(r'_+', '_', safe_name)

        # Read and size-check
        try:
            contents = await file.read()
        except Exception as read_err:
            logger.error(f"Failed to read uploaded file {file.filename}: {read_err}")
            results.append({"filename": file.filename, "error": "Failed to read file", "status": "rejected"})
            continue

        if len(contents) > 50 * 1024 * 1024:
            results.append({
                "filename": file.filename,
                "error": "File too large. Maximum size is 50MB.",
                "status": "rejected",
            })
            continue

        saved_path = os.path.join(tmp_dir, safe_name)
        try:
            with open(saved_path, "wb") as f:
                f.write(contents)
        except OSError as oe:
            logger.error(f"Failed to write uploaded file {safe_name}: {oe}")
            results.append({"filename": file.filename, "error": "File processing failed.", "status": "rejected"})
            continue

        # Kick off ingestion in a background thread
        thread = threading.Thread(
            target=_ingest_in_background,
            args=(saved_path, safe_name),
            daemon=True,
        )
        thread.start()

        results.append({
            "filename": safe_name,
            "status": "processing",
        })

    return {"uploaded": len([r for r in results if r["status"] == "processing"]), "documents": results}


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
            progress=d.progress,
        )
        for d in docs
    ]


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document and all its indexed chunks."""
    if not get_ingestion_pipeline().delete_document(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": f"Document {doc_id} deleted"}


@router.get("/documents/{source_file}/visuals")
async def get_document_visuals(source_file: str):
    """
    Return all visual elements (figures, tables, equations) from a document.

    Filters out tiny decorative images (e.g. logos, separators under 50x50 px)
    that aren't useful for explanation.
    """
    import json
    import os
    from urllib.parse import unquote
    from PIL import Image

    source_file = unquote(source_file)
    MIN_IMAGE_DIM = 50  # filter out icons / pixel decorations

    try:
        vs = get_rag_pipeline().retriever.vector_store
        results = vs.collection.get(
            where={"source_file": source_file},
            include=["documents", "metadatas"],
        )

        visuals = []
        if results and results["ids"]:
            for i, chunk_id in enumerate(results["ids"]):
                meta = results["metadatas"][i] or {}
                element_type = meta.get("element_type", "paragraph")
                if element_type not in ("figure", "table", "equation"):
                    continue

                item = {
                    "id": chunk_id,
                    "element_type": element_type,
                    "page_number": meta.get("page_number", 0),
                    "section_heading": meta.get("section_heading", ""),
                    "content": (results["documents"][i] or "")[:500],
                }

                # Image URL for figures — skip tiny decorations
                img_path = meta.get("image_path")
                if img_path and os.path.exists(img_path):
                    try:
                        with Image.open(img_path) as im:
                            w, h = im.size
                        if w < MIN_IMAGE_DIM or h < MIN_IMAGE_DIM:
                            continue  # Skip this visual entirely
                        item["image_url"] = f"/images/{os.path.basename(img_path)}"
                        item["image_width"] = w
                        item["image_height"] = h
                    except Exception:
                        # If we can't read the image, skip it
                        continue
                elif element_type == "figure":
                    # Figure without a valid image path — skip
                    continue

                if meta.get("image_description"):
                    item["image_description"] = meta["image_description"]

                # Table data
                table_json = meta.get("table_data_json")
                if table_json:
                    try:
                        item["table_data"] = json.loads(table_json)
                    except Exception:
                        pass

                # Equation LaTeX
                if meta.get("latex_source"):
                    item["latex_source"] = meta["latex_source"]

                visuals.append(item)

        # Sort by page number, then by element type
        type_order = {"figure": 0, "table": 1, "equation": 2}
        visuals.sort(key=lambda v: (v["page_number"], type_order.get(v["element_type"], 3)))

        return {"source_file": source_file, "count": len(visuals), "visuals": visuals}

    except Exception as e:
        logger.error(f"Failed to fetch visuals for {source_file}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Core RAG features
# ---------------------------------------------------------------------------

@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """Answer a question using single-shot RAG."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    if len(request.question) > 2000:
        raise HTTPException(status_code=422, detail="Question must be 2000 characters or fewer.")

    # Fix 6: validate filter_source before running the query
    if request.filter_source:
        all_docs = get_ingestion_pipeline().get_all_documents()
        known_sources = {d.filename for d in all_docs}
        if request.filter_source not in known_sources:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No document with source '{request.filter_source}' found. "
                    "Please check the filename."
                ),
            )

    try:
        return _to_query_response(
            get_rag_pipeline().query(
                question=request.question,
                top_k=request.top_k,
                filter_source=request.filter_source,
                chat_history=request.chat_history,
                **_llm_kwargs(request),
            )
        )
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/stream")
async def query_documents_stream(request: QueryRequest):
    """
    Answer a question using single-shot RAG with Server-Sent Events streaming.

    Tokens are emitted progressively as ``data: {"token": "..."}`` lines so the
    frontend can render the answer in real time instead of waiting for the full
    response.  The stream is terminated with ``data: [DONE]``.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    if len(request.question) > 2000:
        raise HTTPException(status_code=422, detail="Question must be 2000 characters or fewer.")

    if request.filter_source:
        all_docs = get_ingestion_pipeline().get_all_documents()
        known_sources = {d.filename for d in all_docs}
        if request.filter_source not in known_sources:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No document with source '{request.filter_source}' found. "
                    "Please check the filename."
                ),
            )

    rag_pipeline = get_rag_pipeline()

    try:
        llm_config = (
            request.llm_config.model_dump(exclude_none=True)
            if request.llm_config else None
        )
        prompt, results = rag_pipeline.build_query_prompt(
            question=request.question,
            top_k=request.top_k,
            filter_source=request.filter_source,
            similarity_threshold=request.similarity_threshold,
            chat_history=request.chat_history,
        )
        citations = rag_pipeline.retriever.get_citations(results) if results else []
    except Exception as e:
        logger.error(f"Streaming query prompt build failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    async def event_generator():
        try:
            for token in rag_pipeline.llm_client.generate_stream(prompt, llm_config=llm_config):
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as exc:
            logger.error(f"Streaming generation error: {exc}")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        # Send citations alongside the done signal before the DONE sentinel
        yield f"data: {json.dumps({'citations': citations, 'done': True})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/agent", response_model=AgentQueryResponse)
async def agent_query(request: AgentQueryRequest):
    """
    Answer a question using the ReAct agent with multi-hop retrieval.
    Supports complex, multi-step questions and conversational context.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    if len(request.question) > 2000:
        raise HTTPException(status_code=422, detail="Question must be 2000 characters or fewer.")
    try:
        # Fix 4: agent.run() is synchronous — run it in a thread pool so it
        # does not block the event loop while waiting on Groq responses.
        _llm_config = (
            request.llm_config.model_dump(exclude_none=True)
            if request.llm_config else None
        )
        resp = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: get_agent().run(
                question=request.question,
                chat_history=request.chat_history,
                llm_config=_llm_config,
                filter_source=request.filter_source,
            ),
        )
        return AgentQueryResponse(
            answer=resp.answer,
            citations=resp.citations,
            question=resp.question,
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
    if len(request.paper1) > 2000:
        raise HTTPException(status_code=422, detail="Question must be 2000 characters or fewer.")
    if len(request.paper2) > 2000:
        raise HTTPException(status_code=422, detail="Question must be 2000 characters or fewer.")
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
    if request.topic and len(request.topic) > 2000:
        raise HTTPException(status_code=422, detail="Question must be 2000 characters or fewer.")
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
    if len(request.concept) > 2000:
        raise HTTPException(status_code=422, detail="Question must be 2000 characters or fewer.")
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


class ExplainVisualRequest(BaseModel):
    chunk_id: str | None = None
    image_path: str | None = None  # alternative to chunk_id
    user_question: str | None = None  # optional follow-up question


@router.post("/explain-visual")
async def explain_visual(request: ExplainVisualRequest):
    """
    Explain a specific visual (figure, table, equation) using Vision AI.

    Unlike /explain (which is text-only via Groq), this endpoint:
    - Loads the actual image file from disk
    - Sends it to Vision AI for true visual analysis
    - Combines that with surrounding text from the paper (when chunk_id given)
    - Returns a detailed structured explanation

    Accepts either chunk_id (UUID from ChromaDB) or image_path (direct file path).
    """
    import os
    from src.ingestion.vision_analyzer import VisionAnalyzer

    if not request.chunk_id and not request.image_path:
        raise HTTPException(status_code=400, detail="Either chunk_id or image_path is required.")

    # --- Path A: image_path provided without chunk_id -------------------------
    if request.image_path and not request.chunk_id:
        image_path = request.image_path
        if not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail=f"Image file not found: {image_path}")

        base_prompt = (
            "You are analyzing a figure from a research paper. Provide a CLEAR, STRUCTURED explanation:\n\n"
            "1. **What it shows** — describe what the figure depicts\n"
            "2. **Components & Labels** — identify every key element, label, axis, legend\n"
            "3. **Key insight** — what is the figure trying to communicate?\n\n"
            "Use markdown formatting with headings and bullet points for clarity."
        )
        full_prompt = base_prompt
        if request.user_question and request.user_question.strip():
            full_prompt += f"\n\n**Specific question from the user:** {request.user_question}\n"

        try:
            from src.generation.llm_client import LLMClient
            llm = LLMClient()
            if llm.enabled:
                explanation = llm.generate_with_image(
                    prompt=full_prompt,
                    image_path=image_path,
                    temperature=0.3,
                    max_tokens=2000,
                )
            else:
                analyzer = VisionAnalyzer()
                if analyzer.enabled:
                    explanation = analyzer.analyze(image_path, prompt=full_prompt)
                else:
                    explanation = "No vision API configured. Cannot analyze image."
        except Exception as e:
            logger.error(f"Vision analysis via image_path failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

        return {
            "answer": explanation,
            "citations": [{"image_url": f"/images/{os.path.basename(image_path)}", "relevance_score": 1.0}],
            "question": f"Explain image: {os.path.basename(image_path)}",
            "intent": "explain_visual",
            "chunks_used": 1,
        }

    # --- Path B: chunk_id provided (original behaviour) ----------------------
    try:
        vs = get_rag_pipeline().retriever.vector_store

        # 1. Fetch the chunk's metadata
        result = vs.collection.get(
            ids=[request.chunk_id],
            include=["documents", "metadatas"],
        )
        if not result or not result["ids"]:
            raise HTTPException(status_code=404, detail="Visual not found")

        meta = result["metadatas"][0] or {}
        element_type = meta.get("element_type", "figure")
        source_file = meta.get("source_file", "")
        page_number = meta.get("page_number", 0)
        image_path = meta.get("image_path", "")
        latex_source = meta.get("latex_source", "")
        original_description = meta.get("image_description", "")

        # 2. Retrieve nearby text context from the paper
        # Get a few chunks from the same page for grounding
        context_chunks = []
        try:
            all_results = vs.collection.get(
                where={"source_file": source_file},
                include=["documents", "metadatas"],
            )
            for i, doc in enumerate(all_results["documents"] or []):
                m = all_results["metadatas"][i] or {}
                if m.get("element_type") == "paragraph" and abs(m.get("page_number", 0) - page_number) <= 1:
                    context_chunks.append(doc[:600])
                if len(context_chunks) >= 5:
                    break
        except Exception as ce:
            logger.warning(f"Could not gather context chunks: {ce}")

        context_text = "\n\n".join(context_chunks) if context_chunks else "(no surrounding text available)"

        # 3. Build a tailored prompt based on visual type
        if element_type == "figure":
            base_prompt = (
                "You are analyzing a figure from a research paper. Provide a CLEAR, STRUCTURED explanation:\n\n"
                "1. **What it shows** — describe what the figure depicts (chart, diagram, flowchart, photo, plot, etc.)\n"
                "2. **Components & Labels** — identify every key element, label, axis, legend, arrow, box, or annotation\n"
                "3. **If it's a flowchart/diagram**: walk through the flow step by step, explaining each node and connection\n"
                "4. **If it's a graph/chart**: explain the axes, data points, trends, comparisons\n"
                "5. **Key insight** — what is the figure trying to communicate? What's the main takeaway?\n"
                "6. **Connection to paper** — how does this figure relate to the surrounding research?\n\n"
                "Be specific. Reference actual labels, numbers, and visual elements you can see. "
                "Use markdown formatting with headings and bullet points for clarity."
            )
        elif element_type == "table":
            base_prompt = (
                "You are analyzing a table from a research paper. Provide a CLEAR explanation:\n\n"
                "1. **What it shows** — the table's purpose\n"
                "2. **Columns & rows** — explain each column header and what the rows represent\n"
                "3. **Key data points** — highlight notable values, comparisons, or patterns\n"
                "4. **Best/worst performers** — if it's a benchmark, identify winners and losers\n"
                "5. **Key takeaway** — what conclusion does this table support?\n\n"
                "Reference specific numbers and column names. Use markdown formatting."
            )
        else:  # equation
            base_prompt = (
                "You are analyzing an equation from a research paper. Provide a CLEAR explanation:\n\n"
                "1. **What it computes** — the equation's purpose in plain English\n"
                "2. **Variable-by-variable breakdown** — define every symbol\n"
                "3. **How to read it** — walk through the math step by step\n"
                "4. **When it's used** — context within the research methodology\n"
                "5. **Significance** — why this equation matters\n\n"
                "Use markdown formatting with bullet points."
            )

        # Append paper context + user question if provided
        full_prompt = base_prompt + f"\n\n**Surrounding text from the paper (page {page_number}):**\n{context_text}\n"
        if original_description:
            full_prompt += f"\n**Original auto-generated description:**\n{original_description}\n"
        if request.user_question and request.user_question.strip():
            full_prompt += f"\n**Specific question from the user:** {request.user_question}\n"

        # 4. Send image to Groq's Llama 4 Vision (no more Gemini rate limits!)
        from src.generation.llm_client import LLMClient
        llm = LLMClient()
        explanation = ""

        if image_path and os.path.exists(image_path):
            if llm.enabled:
                try:
                    explanation = llm.generate_with_image(
                        prompt=full_prompt,
                        image_path=image_path,
                        temperature=0.3,
                        max_tokens=2000,
                    )
                except Exception as ve:
                    logger.error(f"Groq vision failed, falling back to Gemini: {ve}")
                    # Fallback to Gemini Vision
                    analyzer = VisionAnalyzer()
                    if analyzer.enabled:
                        explanation = analyzer.analyze(image_path, prompt=full_prompt)
                    else:
                        explanation = f"Vision analysis failed: {ve}"
            else:
                explanation = "Groq API key not set. Cannot analyze image."
        elif latex_source:
            # No image — use text-only Groq for equations
            explanation = llm.generate(
                full_prompt + f"\n\n**LaTeX source:** {latex_source}",
                temperature=0.2,
                max_tokens=1500,
            )
        else:
            explanation = "No image or LaTeX source available to analyze."

        # 5. Build citation referring to this visual
        citation = {
            "source_file": source_file,
            "page_number": page_number,
            "section": meta.get("section_heading", ""),
            "relevance_score": 1.0,
            "element_type": element_type,
        }
        if image_path and os.path.exists(image_path):
            citation["image_url"] = f"/images/{os.path.basename(image_path)}"
        if original_description:
            citation["image_description"] = original_description

        return {
            "answer": explanation,
            "citations": [citation],
            "question": f"Explain {element_type} on page {page_number}",
            "intent": "explain_visual",
            "chunks_used": 1 + len(context_chunks),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Explain visual failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommend", response_model=QueryResponse)
async def recommend_papers(request: RecommendRequest):
    """Recommend papers based on a research interest."""
    if not request.interest.strip():
        raise HTTPException(status_code=400, detail="Interest cannot be empty")
    if len(request.interest) > 2000:
        raise HTTPException(status_code=422, detail="Question must be 2000 characters or fewer.")
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
    if len(request.question) > 2000:
        raise HTTPException(status_code=422, detail="Question must be 2000 characters or fewer.")
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
# Export results as Markdown
# ---------------------------------------------------------------------------

class ExportRequest(BaseModel):
    title: str = "Research Results"
    answer: str
    citations: list[dict] = []
    question: str = ""


@router.post("/export")
async def export_results(request: ExportRequest):
    """Export answer and citations as a downloadable Markdown file."""
    from fastapi.responses import Response as FastAPIResponse

    lines = [f"# {request.title}\n"]
    if request.question:
        lines.append(f"**Question:** {request.question}\n")
    lines.append(f"\n## Answer\n\n{request.answer}\n")
    if request.citations:
        lines.append("\n## Sources\n")
        seen: set[tuple] = set()
        citation_index = 1
        for c in request.citations:
            src = c.get("source_file", "Unknown")
            page = c.get("page_number", "?")
            section = c.get("section", "")
            key = (src, page)
            if key in seen:
                continue
            seen.add(key)
            line = f"{citation_index}. **{src}**, Page {page}"
            if section:
                line += f" — {section}"
            lines.append(line)
            citation_index += 1

    content = "\n".join(lines)
    # Derive a safe filename from the title
    filename = re.sub(r'[^\w\-_]', '_', request.title)[:40] + ".md"
    return FastAPIResponse(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Humanizer — Detect AI content and humanize text
# ---------------------------------------------------------------------------

@router.post("/detect-ai", response_model=AIDetectionResponse)
async def detect_ai(request: TextAnalysisRequest):
    """
    Analyse text for AI-generated content markers.
    Returns: AI percentage (0-100), confidence (0-1), and explanation.
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    if len(request.text) > 2000:
        raise HTTPException(status_code=422, detail="Question must be 2000 characters or fewer.")

    try:
        logger.info(f"Detecting AI content in text ({len(request.text)} chars)")
        response = get_humanizer().detect_ai(request.text)
        return response
    except Exception as e:
        logger.error(f"AI detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/humanize", response_model=HumanizationResponse)
async def humanize_text(request: TextAnalysisRequest):
    """
    Humanize formal or AI-generated text to be more conversational.
    Returns: original text, humanized version, and summary of changes.
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    if len(request.text) > 2000:
        raise HTTPException(status_code=422, detail="Question must be 2000 characters or fewer.")

    try:
        logger.info(f"Humanizing text ({len(request.text)} chars)")
        response = get_humanizer().humanize(request.text)
        return response
    except Exception as e:
        logger.error(f"Humanization failed: {e}")
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
        "requires_additional_setup": True,
        "note": "Requires separate OpenAI credentials — not configured",
    },
    {
        "id": "openai/gpt-oss-20b",
        "label": "GPT-OSS 20B — Fast & capable",
        "family": "OpenAI",
        "best_for": "Quick Q&A with good reasoning when latency matters",
        "supports_reasoning_effort": True,
        "requires_additional_setup": True,
        "note": "Requires separate OpenAI credentials — not configured",
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
        "id": "groq/compound-mini",
        "label": "Groq Compound Mini — Fast chat (no agent/tools)",
        "family": "Groq",
        "best_for": "Fast chat and RAG responses; does NOT support agent or tool calling",
        "supports_reasoning_effort": False,
        "supports_agent": False,  # Fix 7: groq/compound-mini does not support tool/function calling
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
