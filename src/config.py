"""
Multimodal AI Research Assistant
Configuration management using pydantic-settings.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # Gemini (used for vision tasks only)
    gemini_api_key: str = ""

    # Groq (used for text generation)
    groq_api_key: str = ""

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"

    # ChromaDB
    chroma_persist_dir: str = str(PROJECT_ROOT / "data" / "chroma_db")

    # File storage
    upload_dir: str = str(PROJECT_ROOT / "data" / "uploads")
    images_dir: str = str(PROJECT_ROOT / "data" / "images")

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "info"

    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 50

    # Retrieval
    top_k: int = 10
    similarity_threshold: float = 0.3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


def ensure_directories():
    """Create required data directories if they don't exist."""
    dirs = [
        settings.chroma_persist_dir,
        settings.upload_dir,
        settings.images_dir,
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
