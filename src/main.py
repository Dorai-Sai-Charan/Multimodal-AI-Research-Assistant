"""
FastAPI application entry point.
"""

import sys
import sqlite3
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from src.api.routes import router
from src.config import settings, ensure_directories

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Create data directories
ensure_directories()


def _run_startup_checks() -> None:
    """
    Perform startup health checks and data reconciliation before the server
    begins accepting requests.

    Fix 10 — DB health check: verify the SQLite database is writable.
    Fix 9  — Stuck docs: reset any 'processing' documents to 'failed'.
    Fix 11 — ChromaDB reconciliation: mark 'completed' docs with 0 chunks as 'failed'.
    """
    from src.storage.document_store import DocumentStore, DB_PATH
    from src.storage.vector_store import VectorStore

    # Fix 10: verify SQLite is writable before accepting requests
    try:
        _probe_conn = sqlite3.connect(DB_PATH)
        _probe_conn.execute("PRAGMA user_version = 1")
        _probe_conn.close()
    except sqlite3.OperationalError as exc:
        logger.critical(
            f"SQLite database is not writable at {DB_PATH}: {exc}. "
            "Refusing to start with a broken database."
        )
        sys.exit(1)

    doc_store = DocumentStore()

    # Fix 9: reset stuck 'processing' documents to 'failed'
    all_docs = doc_store.get_all_documents()
    for doc in all_docs:
        if doc.status == "processing":
            logger.warning(
                f"Recovering stuck document '{doc.filename}' ({doc.id}): "
                "marking as 'failed' (was 'processing' at startup)."
            )
            doc_store.update_status(doc.id, "failed")

    # Fix 11: reconcile ChromaDB — completed docs with 0 chunks are broken
    try:
        vector_store = VectorStore()
        all_docs = doc_store.get_all_documents()  # re-fetch after status updates
        for doc in all_docs:
            if doc.status != "completed":
                continue
            try:
                result = vector_store.collection.get(
                    where={"source_file": doc.filename},
                    include=[],
                )
                chunk_count = len(result["ids"]) if result and result.get("ids") else 0
                if chunk_count == 0:
                    logger.warning(
                        f"ChromaDB reconciliation: document '{doc.filename}' ({doc.id}) "
                        "has status='completed' but 0 chunks in ChromaDB — marking as 'failed'."
                    )
                    doc_store.update_status(doc.id, "failed")
            except Exception as chroma_exc:
                logger.warning(
                    f"Could not check ChromaDB chunks for '{doc.filename}': {chroma_exc}"
                )
    except Exception as vs_exc:
        logger.warning(f"ChromaDB reconciliation skipped (ChromaDB unavailable): {vs_exc}")


_run_startup_checks()

# Initialize FastAPI app
app = FastAPI(
    title="Multimodal AI Research Assistant",
    description="RAG-powered research paper analysis with multimodal understanding",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve extracted images as static files (accessible via the Next.js proxy at /api/images/*)
import os as _os
_images_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "data", "images")
_os.makedirs(_images_dir, exist_ok=True)
app.mount("/api/images", StaticFiles(directory=_images_dir), name="images")

# Include API routes
app.include_router(router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )
