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
    chunk_size: int = 800
    chunk_overlap: int = 150

    # Retrieval
    top_k: int = 10
    # ChromaDB cosine distance: distance = 1 - cosine_similarity,
    # so similarity = 1.0 - distance (not distance / 2).
    # Threshold of 0.45 requires at least moderate semantic overlap.
    similarity_threshold: float = 0.45

    # LLM generation defaults (overridable per request from the UI)
    # qwen/qwen3-32b is confirmed to work with Groq native tool calling.
    # llama-3.3-70b-versatile has known issues with tool calling on Groq.
    llm_model: str = "qwen/qwen3-32b"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 2048
    llm_top_p: float = 1.0
    llm_frequency_penalty: float = 0.0
    llm_presence_penalty: float = 0.0
    llm_reasoning_effort: str = "medium"  # low | medium | high (reasoning models only)

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
