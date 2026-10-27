"""Memory Agent: recalls what is known about the user and maintains that memory.

Two graph nodes live here:
  * `recall_memories`  (deterministic) - loads the user's active memories, most relevant first.
  * `update_memories`  (LLM)           - proposes add / correct / forget operations for the new
                                         message; the code validates and applies them.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from assistant.agents import prompts
from assistant.agents.context import format_history, format_memories, user_store
from assistant.agents.state import TurnState
from assistant.config import settings
from assistant.knowledge.retriever import get_retriever
from assistant.llm import LLMUnavailableError, structured_call
from assistant.memory.store import MemoryRejected


# --------------------------------------------------------------------------- schemas
class MemoryOp(BaseModel):
    action: Literal["add", "correct", "forget"]
    kind: Literal["profile", "preference", "work_context"] | None = Field(
        default=None, description="Required for add."
    )
    content: str | None = Field(default=None, description="New memory text for add/correct.")
    memory_id: str | None = Field(default=None, description="Target memory id for correct/forget.")
    reason: str = Field(description="One short sentence: why this operation.")


class MemoryDecision(BaseModel):
    operations: list[MemoryOp] = Field(default_factory=list)
    forget_all: bool = False
    list_requested: bool = False


# --------------------------------------------------------------------------- recall
def recall_memories(state: TurnState, config: RunnableConfig) -> dict:
    """Load active memories for this user, ranked by relevance to the message.

    Preferences are always included (they shape every answer). Other memories are
    ranked by embedding similarity and capped, so a long memory list can't flood prompts.
    """
    memories = [
        {"id": m.id, "kind": m.kind, "content": m.content}
        for m in user_store(config).list_memories()
    ]
    cap = settings.max_memories_in_context
    if len(memories) > cap:
        prefs = [m for m in memories if m["kind"] == "preference"]
        others = [m for m in memories if m["kind"] != "preference"]
        retriever = get_retriever()
        q = np.array(retriever.embed_query(state["message"]))
        vecs = np.array(retriever.embed_passages([m["content"] for m in others]))
        order = np.argsort(-(vecs @ q))  # bge vectors are normalised -> dot product = cosine
        memories = prefs + [others[i] for i in order][: max(cap - len(prefs), 0)]

    return {
        "memories": memories,
        "trace": [f"MemoryAgent.recall: {len(memories)} memories loaded as user context (not evidence)"],
    }


# --------------------------------------------------------------------------- update
def update_memories(state: TurnState, config: RunnableConfig) -> dict:
    """Ask the LLM which memory operations the message implies, then apply them safely."""
    store = user_store(config)
    prompt = (
        f"EXISTING MEMORIES:\n{format_memories(state.get('memories', []), with_ids=True)}\n\n"
        f"RECENT CONVERSATION:\n{format_history(state.get('history', [])[-4:])}\n\n"
        f"NEW USER MESSAGE:\n{state['message']}"
    )
    try:
        decision = structured_call(
            MemoryDecision, prompts.MEMORY_AGENT, prompt, tier="fast", run_name="MemoryAgent.decide"
        )
    except LLMUnavailableError as exc:
        # Memory is best-effort: a provider failure must not block answering the question.
        return {"memory_ops": [], "trace": [f"MemoryAgent.update: skipped (LLM unavailable: {exc})"]}

    known_ids = {m["id"] for m in state.get("memories", [])} | {m.id for m in store.list_memories()}
    applied: list[dict] = []

    if decision.forget_all:
        n = store.forget_all()
        applied.append({"action": "forget_all", "status": "applied", "detail": f"{n} memories deleted"})

    for op in decision.operations if not decision.forget_all else []:
        record = {"action": op.action, "kind": op.kind, "content": op.content,
                  "memory_id": op.memory_id, "reason": op.reason}
        try:
            if op.action == "add":
                mem = store.add_memory(op.kind or "work_context", op.content or "", state.get("session_id"))
                record.update(status="applied", memory_id=mem.id, content=mem.content)
            elif op.action == "correct":
                if op.memory_id not in known_ids:
                    raise KeyError(f"unknown memory id {op.memory_id}")
                old = store.get_memory(op.memory_id)
                mem = store.correct_memory(op.memory_id, op.content or "", state.get("session_id"))
                record.update(status="applied", memory_id=mem.id, previous=old.content if old else None)
            elif op.action == "forget":
                if op.memory_id not in known_ids:
                    raise KeyError(f"unknown memory id {op.memory_id}")
                old = store.get_memory(op.memory_id)
                store.forget_memory(op.memory_id)
                # Keep only the kind: echoing the text would copy it into the saved transcript.
                record.update(status="applied", content=None, kind=old.kind if old else op.kind)
        except (MemoryRejected, KeyError, ValueError) as exc:
            # Policy rejections (secrets, sensitive data) are expected: record them, don't fail.
            record.update(status="rejected", detail=str(exc))
        applied.append(record)

    summary = ", ".join(f"{a['action']}:{a['status']}" for a in applied) or "no changes"
    return {
        "memory_ops": applied,
        "memory_list_requested": decision.list_requested,
        "trace": [f"MemoryAgent.update: {summary}"],
    }
