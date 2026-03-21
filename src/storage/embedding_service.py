"""
Embedding service using sentence-transformers.
Generates dense vector embeddings for text content.
"""

import logging
from sentence_transformers import SentenceTransformer
from src.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generates embeddings using a local sentence-transformer model."""

    _instance = None
    _model = None

    def __new__(cls):
        """Singleton pattern to avoid loading the model multiple times."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._model is None:
            logger.info(f"Loading embedding model: {settings.embedding_model}")
            self.__class__._model = SentenceTransformer(settings.embedding_model)
            logger.info("Embedding model loaded successfully")

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text string."""
        embedding = self._model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        embeddings = self._model.encode(texts, normalize_embeddings=True, batch_size=32)
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return self._model.get_sentence_embedding_dimension()
