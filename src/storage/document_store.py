"""
Document metadata store using SQLite.
Tracks ingested documents and their processing status.
"""

import sqlite3
import logging
import os
from src.config import settings, PROJECT_ROOT
from src.models.schemas import DocumentInfo

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(str(PROJECT_ROOT), "data", "documents.db")


class DocumentStore:
    """SQLite-backed document metadata store."""

    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT DEFAULT 'pdf',
                total_pages INTEGER DEFAULT 0,
                total_chunks INTEGER DEFAULT 0,
                ingested_at TEXT NOT NULL,
                status TEXT DEFAULT 'pending'
            )
        """)
        self.conn.commit()

    def add_document(self, doc: DocumentInfo):
        """Insert a new document record."""
        self.conn.execute(
            """INSERT OR REPLACE INTO documents
               (id, filename, file_path, file_type, total_pages, total_chunks, ingested_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (doc.id, doc.filename, doc.file_path, doc.file_type,
             doc.total_pages, doc.total_chunks, doc.ingested_at, doc.status),
        )
        self.conn.commit()

    def update_status(self, doc_id: str, status: str, total_chunks: int = 0, total_pages: int = 0):
        """Update the processing status of a document."""
        self.conn.execute(
            "UPDATE documents SET status = ?, total_chunks = ?, total_pages = ? WHERE id = ?",
            (status, total_chunks, total_pages, doc_id),
        )
        self.conn.commit()

    def get_document(self, doc_id: str) -> DocumentInfo | None:
        """Retrieve a document by ID."""
        row = self.conn.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if row:
            return DocumentInfo(**dict(row))
        return None

    def get_all_documents(self) -> list[DocumentInfo]:
        """Retrieve all documents."""
        rows = self.conn.execute(
            "SELECT * FROM documents ORDER BY ingested_at DESC"
        ).fetchall()
        return [DocumentInfo(**dict(row)) for row in rows]

    def delete_document(self, doc_id: str):
        """Delete a document record."""
        self.conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        self.conn.commit()
