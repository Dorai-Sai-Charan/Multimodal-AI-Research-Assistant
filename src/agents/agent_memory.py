"""Persistent agent memory backed by SQLite.

Stores key findings from agent runs and retrieves relevant past context
to inject into future prompts, enabling cross-session learning.
"""

import sqlite3
import threading
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class AgentMemory:
    """
    Lightweight cross-session memory for the ResearchAgent.

    Each agent run can store 1-3 key facts as short strings.  On subsequent
    runs, relevant memories are retrieved via simple keyword matching and
    prepended to the agent's context so the model is aware of past findings.

    Thread-safe: all SQLite writes are protected by a lock.
    """

    DB_PATH = "data/agent_memory.db"

    def __init__(self):
        try:
            Path("data").mkdir(exist_ok=True)
            self._lock = threading.Lock()
            self.conn = sqlite3.connect(self.DB_PATH, check_same_thread=False)
            self._create_table()
            logger.info("AgentMemory initialised at %s", self.DB_PATH)
        except Exception as exc:
            logger.error("AgentMemory: failed to initialise SQLite DB: %s", exc)
            self.conn = None  # type: ignore[assignment]

    def _create_table(self) -> None:
        if self.conn is None:
            return
        with self._lock:
            try:
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT,
                        key_fact TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                self.conn.commit()
            except Exception as exc:
                logger.error("AgentMemory: failed to create table: %s", exc)

    def store(self, session_id: str, key_fact: str) -> None:
        """Store a key finding from an agent run."""
        if self.conn is None:
            return
        with self._lock:
            try:
                self.conn.execute(
                    "INSERT INTO memories (session_id, key_fact) VALUES (?, ?)",
                    (session_id, key_fact),
                )
                self.conn.commit()
                logger.debug("AgentMemory: stored fact for session '%s'", session_id[:30])
            except Exception as exc:
                logger.error("AgentMemory: failed to store fact: %s", exc)

    def retrieve_relevant(self, query: str, limit: int = 5) -> list[str]:
        """Retrieve relevant past memories using simple keyword matching."""
        if self.conn is None:
            return []
        with self._lock:
            try:
                words = [w.lower() for w in query.split() if len(w) > 4]
                if not words:
                    cursor = self.conn.execute(
                        "SELECT key_fact FROM memories ORDER BY created_at DESC LIMIT ?",
                        (limit,),
                    )
                else:
                    placeholders = " OR ".join(
                        ["LOWER(key_fact) LIKE ?" for _ in words]
                    )
                    params: list = [f"%{w}%" for w in words] + [limit]
                    cursor = self.conn.execute(
                        f"SELECT DISTINCT key_fact FROM memories "  # noqa: S608
                        f"WHERE {placeholders} ORDER BY created_at DESC LIMIT ?",
                        params,
                    )
                return [row[0] for row in cursor.fetchall()]
            except Exception as exc:
                logger.error("AgentMemory: failed to retrieve memories: %s", exc)
                return []

    def get_summary(self, limit: int = 10) -> str:
        """Return a formatted summary of recent memories for prompt injection."""
        facts = self.retrieve_relevant("", limit)
        if not facts:
            return ""
        return "Past research context:\n" + "\n".join(f"- {f}" for f in facts)
