"""Application service: the single entry point used by the UI and the evaluation.

`AssistantService.ask()` runs one conversation turn:
  1. redact secrets from the user's message (before anything is stored or traced)
  2. load this session's recent history
  3. run the agent graph with a per-user store injected
  4. save the redacted user message and the answer to the session transcript
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from assistant.config import settings
from assistant.graph import build_graph
from assistant.memory.store import Store, UserStore
from assistant.redaction import redact


@dataclass
class TurnResult:
    answer: str
    status: str
    citations: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    memory_ops: list[dict[str, Any]] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    redacted: list[str] = field(default_factory=list)  # kinds of secrets removed from the input
    latency_s: float = 0.0


class AssistantService:
    def __init__(self, store: Store | None = None) -> None:
        self.store = store or Store()
        self.graph = build_graph()

    def user(self, user_id: str) -> UserStore:
        return self.store.for_user(user_id)

    def ask(self, user_id: str, session_id: str, message: str) -> TurnResult:
        user = self.user(user_id)
        if not user.owns_session(session_id):
            raise PermissionError("Unknown session for this user.")

        # 1. Secrets never go further than this line.
        clean = redact(message)

        # 2. Recent history of THIS session only (follow-up questions).
        history = [
            {"role": m.role, "content": m.content}
            for m in user.get_messages(session_id, limit=settings.history_turns)
        ]

        # 3. Run the agents. Metadata/tags make runs searchable in LangSmith.
        #    The user id is a synthetic demo id (alice/bob/...), so it is safe to trace.
        started = time.perf_counter()
        state = self.graph.invoke(
            {"user_id": user_id, "session_id": session_id, "message": clean.text,
             "history": history, "trace": []},
            config={
                "configurable": {"user_store": user},
                "run_name": "assistant_turn",
                "tags": ["asterline-assistant"],
                "metadata": {"user_id": user_id, "session_id": session_id},
            },
        )
        latency = time.perf_counter() - started

        warnings = list(state.get("warnings", []))
        if clean.had_secrets:
            warnings.insert(0, "A secret-looking value was removed from your message before processing. "
                               "Never paste real keys or passwords.")

        result = TurnResult(
            answer=state.get("final_answer", "Sorry, something went wrong."),
            status=state.get("answer_status", "error"),
            citations=state.get("citations", []),
            warnings=warnings,
            memory_ops=state.get("memory_ops", []),
            trace=state.get("trace", []),
            evidence_ids=[e["chunk_id"] for e in state.get("evidence", [])],
            redacted=clean.found,
            latency_s=round(latency, 2),
        )

        # 4. Persist the turn (redacted text only). The first question names the session.
        if not user.get_messages(session_id, limit=1):
            user.rename_session(session_id, clean.text[:60])
        user.add_message(session_id, "user", clean.text)
        user.add_message(session_id, "assistant", result.answer, meta={
            "status": result.status, "citations": result.citations, "warnings": result.warnings,
            "trace": result.trace, "memory_ops": result.memory_ops,
        })
        return result
