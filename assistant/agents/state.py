"""Shared state passed between the agents in the LangGraph workflow.

Each agent reads what it needs from `TurnState` and returns only the keys it
changes. LangGraph merges those partial updates into the state.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class TurnState(TypedDict, total=False):
    # ---- inputs (filled by the service before the graph runs) ----
    user_id: str
    session_id: str
    message: str                      # the user's message, already secret-redacted
    history: list[dict[str, str]]     # recent turns [{role, content}] of this session
    memories: list[dict[str, str]]    # recalled user memories [{id, kind, content}] - NOT evidence

    # ---- Memory Agent ----
    memory_ops: list[dict[str, Any]]  # operations it applied/rejected, shown in UI + trace
    memory_list_requested: bool       # user asked "what do you remember about me?"

    # ---- Coordinator (planner / router) ----
    route: str                        # "research" | "memory" | "chat"
    standalone_question: str          # follow-up rewritten so it makes sense on its own
    search_queries: list[str]

    # ---- Research Agent ----
    evidence: list[dict[str, Any]]    # retrieved corpus chunks with metadata and score
    research_rounds: int

    # ---- Analyst Agent ----
    draft: dict[str, Any]             # {status, answer, claims[{statement, chunk_ids}]}
    revision_rounds: int

    # ---- Verifier Agent ----
    verdict: dict[str, Any]           # {verdict, issues, unsupported_claims, missing_info_queries}

    # ---- final output ----
    final_answer: str
    answer_status: str                # answered | partial | insufficient_evidence | conflict | memory | chat | error
    citations: list[dict[str, str]]   # [{chunk_id, title, published}]
    warnings: list[str]

    # Human-readable log of every decision. `operator.add` lets parallel agents append safely.
    trace: Annotated[list[str], operator.add]
