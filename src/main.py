"""
FastAPI application entry point.
"""

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

# Create data directories
ensure_directories()

# Initialize FastAPI app
app = FastAPI(
    title="Multimodal AI Research Assistant",
    description="RAG-powered research paper analysis with multimodal understanding",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
