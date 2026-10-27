"""Helpers that turn state into prompt text.

Keeping formatting here guarantees every agent sees memory and evidence in the
same, clearly separated sections ("USER CONTEXT - not evidence" vs "EVIDENCE").
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from assistant.memory.store import UserStore


def user_store(config: RunnableConfig) -> UserStore:
    """The per-user store injected by the service via `config["configurable"]`.

    Agents never build their own store, so they can only touch the current user's data.
    """
    return config["configurable"]["user_store"]


def format_history(history: list[dict[str, str]], max_chars: int = 600) -> str:
    """Recent turns, each truncated so long answers don't flood the prompt."""
    if not history:
        return "(no earlier messages in this conversation)"
    lines = []
    for turn in history:
        text = turn["content"].replace("\n", " ")
        if len(text) > max_chars:
            text = text[:max_chars] + " ..."
        lines.append(f"{turn['role'].upper()}: {text}")
    return "\n".join(lines)


def format_memories(memories: list[dict[str, str]], with_ids: bool = False) -> str:
    """User memories as a bullet list (ids only shown to the Memory Agent, which needs them)."""
    if not memories:
        return "(nothing remembered about this user)"
    if with_ids:
        return "\n".join(f"- id={m['id']} [{m['kind']}] {m['content']}" for m in memories)
    return "\n".join(f"- [{m['kind']}] {m['content']}" for m in memories)


def format_evidence(evidence: list[dict[str, Any]]) -> str:
    """Evidence chunks, grouped by document and ordered by date so changes over time are easy to see."""
    if not evidence:
        return "(no evidence retrieved)"
    ordered = sorted(evidence, key=lambda e: (e["published"], e["doc_id"], e["chunk_id"]))
    return "\n\n".join(
        f"[{e['chunk_id']}] {e['title']} | category={e['category']} | published={e['published']} | "
        f"doc_version={e['version']}\n{e['text']}"
        for e in ordered
    )
