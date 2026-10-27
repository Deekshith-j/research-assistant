"""SQLite persistence for sessions, messages and long-term memories.

Isolation design: callers never get a "global" store. They call
`Store().for_user(user_id)` and receive a `UserStore` whose every SQL statement
is filtered by that user_id. There is no method that accepts another user's id,
so one user's private context cannot leak into another user's session.

Tables
  sessions       one row per conversation
  messages       chat transcript (redacted text only)
  memories       long-term facts about the user; corrections keep a 'superseded' trail
  memory_events  audit log of add / correct / forget (forgotten content is NOT kept)
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from assistant.config import settings
from assistant.memory.policy import check_memory

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    title       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id     TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    meta        TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memories (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    kind            TEXT NOT NULL,
    content         TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('active', 'superseded')),
    supersedes      TEXT,
    source_session  TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL,
    memory_id   TEXT,
    action      TEXT NOT NULL,
    detail      TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, user_id);
CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id, status);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Memory:
    id: str
    kind: str
    content: str
    status: str
    supersedes: str | None
    created_at: str
    updated_at: str


@dataclass
class Message:
    role: str
    content: str
    meta: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""


@dataclass
class Session:
    id: str
    title: str
    created_at: str
    updated_at: str


class MemoryRejected(ValueError):
    """Raised when a proposed memory violates the storage policy."""


class Store:
    """Owns the database file and schema. Use `for_user()` to do anything useful."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path or settings.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Short-lived connection per operation: safe with Streamlit's threads."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def for_user(self, user_id: str) -> "UserStore":
        if not user_id or not user_id.strip():
            raise ValueError("user_id is required")
        return UserStore(self, user_id.strip())


class UserStore:
    """All reads/writes for exactly one user. Every query is scoped by `self.user_id`."""

    def __init__(self, store: Store, user_id: str) -> None:
        self._store = store
        self.user_id = user_id

    # ================================================================ sessions
    def create_session(self, title: str = "New conversation") -> Session:
        sid, now = uuid.uuid4().hex[:12], _now()
        with self._store.connect() as c:
            c.execute(
                "INSERT INTO sessions (id, user_id, title, created_at, updated_at) VALUES (?,?,?,?,?)",
                (sid, self.user_id, title, now, now),
            )
        return Session(sid, title, now, now)

    def list_sessions(self) -> list[Session]:
        with self._store.connect() as c:
            rows = c.execute(
                "SELECT id, title, created_at, updated_at FROM sessions WHERE user_id=? ORDER BY updated_at DESC",
                (self.user_id,),
            ).fetchall()
        return [Session(**dict(r)) for r in rows]

    def owns_session(self, session_id: str) -> bool:
        with self._store.connect() as c:
            row = c.execute(
                "SELECT 1 FROM sessions WHERE id=? AND user_id=?", (session_id, self.user_id)
            ).fetchone()
        return row is not None

    def rename_session(self, session_id: str, title: str) -> None:
        with self._store.connect() as c:
            c.execute(
                "UPDATE sessions SET title=? WHERE id=? AND user_id=?", (title[:80], session_id, self.user_id)
            )

    def delete_session(self, session_id: str) -> None:
        """Delete a conversation and its transcript (messages cascade)."""
        with self._store.connect() as c:
            c.execute("DELETE FROM sessions WHERE id=? AND user_id=?", (session_id, self.user_id))

    # ================================================================ messages
    def add_message(self, session_id: str, role: str, content: str, meta: dict | None = None) -> None:
        if not self.owns_session(session_id):
            raise PermissionError("session does not belong to this user")
        now = _now()
        with self._store.connect() as c:
            c.execute(
                "INSERT INTO messages (session_id, user_id, role, content, meta, created_at) VALUES (?,?,?,?,?,?)",
                (session_id, self.user_id, role, content, json.dumps(meta or {}), now),
            )
            c.execute("UPDATE sessions SET updated_at=? WHERE id=? AND user_id=?", (now, session_id, self.user_id))

    def get_messages(self, session_id: str, limit: int | None = None) -> list[Message]:
        """Messages of one session in chronological order (optionally only the last `limit`)."""
        sql = (
            "SELECT role, content, meta, created_at FROM messages "
            "WHERE session_id=? AND user_id=? ORDER BY id DESC"
        )
        params: tuple = (session_id, self.user_id)
        if limit:
            sql += " LIMIT ?"
            params += (limit,)
        with self._store.connect() as c:
            rows = c.execute(sql, params).fetchall()
        return [Message(r["role"], r["content"], json.loads(r["meta"]), r["created_at"]) for r in reversed(rows)]

    # ================================================================ memories
    def list_memories(self, include_superseded: bool = False) -> list[Memory]:
        sql = "SELECT id, kind, content, status, supersedes, created_at, updated_at FROM memories WHERE user_id=?"
        if not include_superseded:
            sql += " AND status='active'"
        sql += " ORDER BY updated_at DESC"
        with self._store.connect() as c:
            rows = c.execute(sql, (self.user_id,)).fetchall()
        return [Memory(**dict(r)) for r in rows]

    def get_memory(self, memory_id: str) -> Memory | None:
        with self._store.connect() as c:
            r = c.execute(
                "SELECT id, kind, content, status, supersedes, created_at, updated_at "
                "FROM memories WHERE id=? AND user_id=?",
                (memory_id, self.user_id),
            ).fetchone()
        return Memory(**dict(r)) if r else None

    def add_memory(self, kind: str, content: str, source_session: str | None = None) -> Memory:
        """Store a new memory after the policy check. Exact duplicates are not stored twice."""
        allowed, reason = check_memory(kind, content)
        if not allowed:
            raise MemoryRejected(reason)
        content = content.strip()
        for m in self.list_memories():
            if m.content.lower() == content.lower():
                return m  # already remembered
        return self._insert_memory(kind, content, supersedes=None, source_session=source_session)

    def correct_memory(self, memory_id: str, new_content: str, source_session: str | None = None) -> Memory:
        """Replace a memory with corrected content.

        The old row is kept as 'superseded' (so the user can see what changed in the
        memory inspector) and is never shown to the agents again.
        """
        old = self.get_memory(memory_id)
        if old is None or old.status != "active":
            raise KeyError(f"no active memory {memory_id}")
        allowed, reason = check_memory(old.kind, new_content)
        if not allowed:
            raise MemoryRejected(reason)
        with self._store.connect() as c:
            c.execute(
                "UPDATE memories SET status='superseded', updated_at=? WHERE id=? AND user_id=?",
                (_now(), memory_id, self.user_id),
            )
        return self._insert_memory(old.kind, new_content.strip(), supersedes=memory_id, source_session=source_session)

    def forget_memory(self, memory_id: str) -> bool:
        """Hard-delete a memory *and* its correction history. Nothing of its content is kept."""
        chain = self._history_chain(memory_id)
        if not chain:
            return False
        params = [(mid, self.user_id) for mid in chain]
        with self._store.connect() as c:
            c.executemany("DELETE FROM memories WHERE id=? AND user_id=?", params)
            # Scrub the audit trail too, otherwise the "add" event would still hold the text.
            c.executemany("UPDATE memory_events SET detail=NULL WHERE memory_id=? AND user_id=?", params)
        self._log("forget", memory_id, detail=None)
        return True

    def forget_all(self) -> int:
        """Delete every memory of this user (the "forget everything about me" request)."""
        with self._store.connect() as c:
            n = c.execute("DELETE FROM memories WHERE user_id=?", (self.user_id,)).rowcount
            c.execute("UPDATE memory_events SET detail=NULL WHERE user_id=?", (self.user_id,))
        self._log("forget_all", None, detail=f"{n} memories")
        return n

    def memory_events(self, limit: int = 50) -> list[dict]:
        with self._store.connect() as c:
            rows = c.execute(
                "SELECT memory_id, action, detail, created_at FROM memory_events "
                "WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (self.user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ---------------------------------------------------------------- helpers
    def _insert_memory(self, kind: str, content: str, supersedes: str | None, source_session: str | None) -> Memory:
        mid, now = "m_" + uuid.uuid4().hex[:8], _now()
        with self._store.connect() as c:
            c.execute(
                "INSERT INTO memories (id, user_id, kind, content, status, supersedes, source_session, created_at, updated_at) "
                "VALUES (?,?,?,?, 'active', ?,?,?,?)",
                (mid, self.user_id, kind, content, supersedes, source_session, now, now),
            )
        self._log("correct" if supersedes else "add", mid, detail=content)
        return Memory(mid, kind, content, "active", supersedes, now, now)

    def _history_chain(self, memory_id: str) -> list[str]:
        """The memory id plus every older version it superseded (walks the `supersedes` links)."""
        chain: list[str] = []
        current: str | None = memory_id
        while current and current not in chain:
            m = self.get_memory(current)
            if m is None:
                break
            chain.append(m.id)
            current = m.supersedes
        return chain

    def _log(self, action: str, memory_id: str | None, detail: str | None) -> None:
        with self._store.connect() as c:
            c.execute(
                "INSERT INTO memory_events (user_id, memory_id, action, detail, created_at) VALUES (?,?,?,?,?)",
                (self.user_id, memory_id, action, detail, _now()),
            )
