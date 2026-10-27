"""REST API for the React frontend (FastAPI).

The API is a thin layer over `AssistantService` and the per-user store; no agent
logic lives here. It also serves the built frontend (`frontend/dist`), so the whole
app runs from one process and one command (`python run.py`).

Every route is nested under /api/users/{user_id}/... and resolves the data through
`Store.for_user(user_id)`, so user isolation is the same as everywhere else.
The user id comes from the demo user selector (no real authentication, see README).
"""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from assistant.config import PROJECT_ROOT
from assistant.knowledge.corpus import chunks_by_id
from assistant.llm import llm_available
from assistant.memory.store import MemoryRejected, UserStore
from assistant.service import AssistantService

# Synthetic demo users (the assignment asks for synthetic user data only).
DEMO_USERS = {
    "alice": {"name": "Alice", "role": "Support engineer"},
    "bob": {"name": "Bob", "role": "Solutions architect"},
    "carol": {"name": "Carol", "role": "Engineering manager"},
}

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


# --------------------------------------------------------------------------- request bodies
class AskBody(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class MemoryBody(BaseModel):
    kind: Literal["profile", "preference", "work_context"]
    content: str = Field(min_length=1)


class CorrectBody(BaseModel):
    content: str = Field(min_length=1)


def create_app(service: AssistantService | None = None) -> FastAPI:
    """Build the app. Tests pass their own service (with a temporary database)."""
    svc = service or AssistantService()
    app = FastAPI(title="Asterline Research Assistant API")

    # ----------------------------------------------------------------- helpers
    def user(user_id: str) -> UserStore:
        """Resolve a demo user to their scoped store (404 for unknown users)."""
        if user_id not in DEMO_USERS:
            raise HTTPException(404, "Unknown user")
        return svc.user(user_id)

    def own_session(u: UserStore, session_id: str) -> None:
        """Another user's session looks exactly like a missing one (no information leak)."""
        if not u.owns_session(session_id):
            raise HTTPException(404, "Conversation not found")

    # ----------------------------------------------------------------- status
    @app.get("/api/status")
    def status() -> dict:
        tracing = os.getenv("LANGSMITH_TRACING", "").lower() == "true" and bool(os.getenv("LANGSMITH_API_KEY"))
        return {"llm": llm_available(), "tracing": tracing,
                "project": os.getenv("LANGSMITH_PROJECT", "default")}

    @app.get("/api/users")
    def users() -> list[dict]:
        return [{"id": uid, **info} for uid, info in DEMO_USERS.items()]

    # ----------------------------------------------------------------- source passages
    @app.get("/api/chunks/{chunk_id}")
    def chunk(chunk_id: str) -> dict:
        """The exact corpus passage behind a citation, so users can verify answers.

        Company documents are shared knowledge (not user data), so this route is not per-user.
        """
        found = chunks_by_id().get(chunk_id)
        if found is None:
            raise HTTPException(404, "Unknown chunk id")
        return {**asdict(found), "published": found.published_iso}

    # ----------------------------------------------------------------- conversations
    @app.get("/api/users/{user_id}/sessions")
    def list_sessions(user_id: str) -> list[dict]:
        return [asdict(s) for s in user(user_id).list_sessions()]

    @app.post("/api/users/{user_id}/sessions", status_code=201)
    def create_session(user_id: str) -> dict:
        return asdict(user(user_id).create_session())

    @app.delete("/api/users/{user_id}/sessions/{session_id}", status_code=204)
    def delete_session(user_id: str, session_id: str) -> None:
        u = user(user_id)
        own_session(u, session_id)
        u.delete_session(session_id)

    @app.get("/api/users/{user_id}/sessions/{session_id}/messages")
    def messages(user_id: str, session_id: str) -> list[dict]:
        u = user(user_id)
        own_session(u, session_id)
        return [asdict(m) for m in u.get_messages(session_id)]

    @app.post("/api/users/{user_id}/sessions/{session_id}/messages")
    def ask(user_id: str, session_id: str, body: AskBody) -> dict:
        """Run one conversation turn through the agents (takes ~10-30 s)."""
        u = user(user_id)
        own_session(u, session_id)
        return asdict(svc.ask(user_id, session_id, body.text))

    # ----------------------------------------------------------------- memory inspector
    @app.get("/api/users/{user_id}/memories")
    def list_memories(user_id: str, include_superseded: bool = False) -> list[dict]:
        return [asdict(m) for m in user(user_id).list_memories(include_superseded=include_superseded)]

    @app.post("/api/users/{user_id}/memories", status_code=201)
    def add_memory(user_id: str, body: MemoryBody) -> dict:
        try:
            return asdict(user(user_id).add_memory(body.kind, body.content))
        except MemoryRejected as exc:  # policy gate: secrets, sensitive data, ...
            raise HTTPException(422, f"Not saved: {exc}") from exc

    @app.patch("/api/users/{user_id}/memories/{memory_id}")
    def correct_memory(user_id: str, memory_id: str, body: CorrectBody) -> dict:
        try:
            return asdict(user(user_id).correct_memory(memory_id, body.content))
        except KeyError as exc:
            raise HTTPException(404, "Memory not found") from exc
        except MemoryRejected as exc:
            raise HTTPException(422, f"Not saved: {exc}") from exc

    @app.delete("/api/users/{user_id}/memories/{memory_id}", status_code=204)
    def forget_memory(user_id: str, memory_id: str) -> None:
        if not user(user_id).forget_memory(memory_id):
            raise HTTPException(404, "Memory not found")

    @app.delete("/api/users/{user_id}/memories")
    def forget_all(user_id: str) -> dict:
        return {"deleted": user(user_id).forget_all()}

    @app.get("/api/users/{user_id}/memory-events")
    def memory_events(user_id: str) -> list[dict]:
        return user(user_id).memory_events()

    # ----------------------------------------------------------------- frontend
    # Serve the built React app; any non-API path returns index.html (single-page app).
    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            file = (FRONTEND_DIST / path).resolve()
            if path and file.is_file() and FRONTEND_DIST.resolve() in file.parents:
                return FileResponse(file)  # e.g. favicon.svg
            return FileResponse(FRONTEND_DIST / "index.html")

    return app
