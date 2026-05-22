"""
Document metadata store using SQLite.
Tracks ingested documents and their processing status.
"""

import sqlite3
import threading
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
        # Fix 8: serialize all write operations across threads
        self._lock = threading.Lock()
        self._create_table()

    def _create_table(self):
        with self._lock:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_type TEXT DEFAULT 'pdf',
                    total_pages INTEGER DEFAULT 0,
                    total_chunks INTEGER DEFAULT 0,
                    ingested_at TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    file_hash TEXT,
                    progress TEXT DEFAULT ''
                )
            """)
            # Add file_hash column to existing databases that pre-date this schema change
            try:
                self.conn.execute("ALTER TABLE documents ADD COLUMN file_hash TEXT")
            except sqlite3.OperationalError:
                pass  # column already exists
            # Add progress column to existing databases that pre-date this schema change
            try:
                self.conn.execute("ALTER TABLE documents ADD COLUMN progress TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass  # column already exists
            self.conn.commit()

    def add_document(self, doc: DocumentInfo):
        """Insert a new document record."""
        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO documents
                   (id, filename, file_path, file_type, total_pages, total_chunks,
                    ingested_at, status, file_hash, progress)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc.id, doc.filename, doc.file_path, doc.file_type,
                 doc.total_pages, doc.total_chunks, doc.ingested_at, doc.status,
                 doc.file_hash, doc.progress),
            )
            self.conn.commit()

    def get_by_hash(self, file_hash: str) -> "DocumentInfo | None":
        """Return the first document with the given SHA-256 hash, or None."""
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM documents WHERE file_hash = ? LIMIT 1", (file_hash,)
            ).fetchone()
        if row:
            data = dict(row)
            data.setdefault("progress", "")
            if data["progress"] is None:
                data["progress"] = ""
            return DocumentInfo(**data)
        return None

    def update_status(self, doc_id: str, status: str, total_chunks: int = 0, total_pages: int = 0):
        """Update the processing status of a document."""
        with self._lock:
            self.conn.execute(
                "UPDATE documents SET status = ?, total_chunks = ?, total_pages = ? WHERE id = ?",
                (status, total_chunks, total_pages, doc_id),
            )
            self.conn.commit()

    def update_progress(self, doc_id: str, progress: str):
        """Update the progress message for a document currently being ingested."""
        with self._lock:
            self.conn.execute(
                "UPDATE documents SET progress = ? WHERE id = ?",
                (progress, doc_id),
            )
            self.conn.commit()

    def get_document(self, doc_id: str) -> DocumentInfo | None:
        """Retrieve a document by ID."""
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
        if row:
            data = dict(row)
            data.setdefault("progress", "")
            if data["progress"] is None:
                data["progress"] = ""
            return DocumentInfo(**data)
        return None

    def get_all_documents(self) -> list[DocumentInfo]:
        """Retrieve all documents."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM documents ORDER BY ingested_at DESC"
            ).fetchall()
        result = []
        for row in rows:
            data = dict(row)
            data.setdefault("progress", "")
            if data["progress"] is None:
                data["progress"] = ""
            result.append(DocumentInfo(**data))
        return result

    def delete_document(self, doc_id: str):
        """Delete a document record."""
        with self._lock:
            self.conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            self.conn.commit()
