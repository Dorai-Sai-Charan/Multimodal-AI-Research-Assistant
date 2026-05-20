"""
Core data models and schemas for the application.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import uuid
from pydantic import BaseModel


@dataclass
class ChunkMetadata:
    """Rich metadata attached to each chunk."""

    source_file: str  # original filename
    page_number: int = 0
    section_heading: str = ""
    chunk_index: int = 0
    element_type: str = "paragraph"  # paragraph | table | figure | equation | handwritten
    table_data: Optional[dict] = None
    latex_source: Optional[str] = None
    image_path: Optional[str] = None
    image_description: Optional[str] = None
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class Chunk:
    """
    A single indexed chunk of content.
    This is the fundamental unit stored in the vector database.
    """

    content: str  # the text content or description
    content_type: str  # "text" | "table" | "equation" | "figure" | "handwritten"
    metadata: ChunkMetadata
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    embedding: Optional[list[float]] = None

    def to_dict(self) -> dict:
        """Serialize chunk for storage."""
        return {
            "id": self.id,
            "content": self.content,
            "content_type": self.content_type,
            "metadata": {
                "source_file": self.metadata.source_file,
                "page_number": self.metadata.page_number,
                "section_heading": self.metadata.section_heading,
                "chunk_index": self.metadata.chunk_index,
                "element_type": self.metadata.element_type,
                "confidence": self.metadata.confidence,
                "created_at": self.metadata.created_at,
                "image_path": self.metadata.image_path,
                "image_description": self.metadata.image_description,
                "latex_source": self.metadata.latex_source,
                "table_data": self.metadata.table_data,
            },
        }


@dataclass
class ExtractedElement:
    """
    A raw element extracted from a document before chunking.
    Represents a section of text, a table, an image, etc.
    """

    content: str
    element_type: str  # "text" | "table" | "figure" | "equation"
    page_number: int
    section_heading: str = ""
    table_data: Optional[dict] = None
    image_path: Optional[str] = None
    confidence: float = 1.0


@dataclass
class DocumentInfo:
    """Metadata about an ingested document."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    filename: str = ""
    file_path: str = ""
    file_type: str = "pdf"
    total_pages: int = 0
    total_chunks: int = 0
    ingested_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "pending"  # pending | processing | completed | failed
    file_hash: Optional[str] = None  # SHA-256 hex digest for duplicate detection


@dataclass
class QueryResult:
    """A single retrieval result with relevance score."""

    chunk: Chunk
    score: float
    rank: int


@dataclass
class GenerationResponse:
    """Final response from the system."""

    answer: str
    citations: list[dict] = field(default_factory=list)
    question: str = ""  # renamed from 'query' for consistency with request field naming
    intent: str = "question_answering"
    chunks_used: int = 0


@dataclass
class AgentStep:
    """A single reasoning step in the ReAct agent loop."""

    step_number: int
    thought: str
    action: str
    action_input: dict
    observation: str = ""


@dataclass
class AgentResponse:
    """Response from the agentic reasoning system, including full reasoning trace."""

    answer: str
    reasoning_steps: list = field(default_factory=list)  # list[AgentStep]
    citations: list[dict] = field(default_factory=list)
    question: str = ""  # renamed from 'query' for consistency with request field naming
    intent: str = "question_answering"
    chunks_used: int = 0
    total_steps: int = 0


# ============================================================================
# Humanizer Feature — Pydantic Models for API
# ============================================================================

class TextAnalysisRequest(BaseModel):
    """Request to analyse text (detect AI or humanize)."""
    text: str


class AIDetectionResponse(BaseModel):
    """Response from AI detection analysis."""
    ai_percentage: float  # 0-100
    confidence: float  # 0-1
    explanation: str
    metrics: Optional[dict] = None
    heuristic_score: Optional[float] = None
    roberta_score: Optional[float] = None


class HumanizationResponse(BaseModel):
    """Response from text humanization."""
    original_text: str
    humanized_text: str
    changes_made: str
    original_score: Optional[float] = None
    new_score: Optional[float] = None
    metrics_before: Optional[dict] = None
    metrics_after: Optional[dict] = None
    passes_used: Optional[int] = None
    target_reached: Optional[bool] = None
