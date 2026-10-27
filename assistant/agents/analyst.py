"""Analyst Agent: writes a grounded, cited answer from the retrieved evidence."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from assistant.agents import prompts
from assistant.agents.context import format_evidence, format_history, format_memories
from assistant.agents.state import TurnState
from assistant.agents.verifier import normalize_citations
from assistant.llm import LLMUnavailableError, structured_call


class Claim(BaseModel):
    statement: str
    chunk_ids: list[str] = Field(default_factory=list)


class Draft(BaseModel):
    status: Literal["answered", "partial", "insufficient_evidence", "conflict"]
    answer: str = Field(description="Markdown answer with inline [chunk_id] citations.")
    claims: list[Claim] = Field(default_factory=list)


def analyse(state: TurnState) -> dict:
    runs = state.get("revision_rounds", 0)
    verdict = state.get("verdict")

    # On a second pass, give the Analyst the Verifier's concrete feedback.
    feedback = ""
    if verdict and verdict.get("verdict") != "pass":
        issues = verdict.get("issues", []) + [f"Unsupported: {c}" for c in verdict.get("unsupported_claims", [])]
        feedback = "\n\nREVIEWER FEEDBACK (fix all of these):\n" + "\n".join(f"- {i}" for i in issues)

    prompt = (
        f"QUESTION (standalone): {state.get('standalone_question') or state['message']}\n"
        f"ORIGINAL MESSAGE: {state['message']}\n\n"
        f"USER CONTEXT - personalisation only, NOT evidence:\n{format_memories(state.get('memories', []))}\n\n"
        f"RECENT CONVERSATION - NOT evidence:\n{format_history(state.get('history', [])[-4:])}\n\n"
        f"EVIDENCE:\n{format_evidence(state.get('evidence', []))}"
        f"{feedback}"
    )
    try:
        draft = structured_call(Draft, prompts.ANALYST, prompt, tier="main", run_name="AnalystAgent.draft")
    except LLMUnavailableError as exc:
        return {
            "draft": _offline_draft(state),
            "revision_rounds": runs + 1,
            "trace": [f"AnalystAgent: LLM unavailable ({exc}); returning top passages instead of an answer"],
        }

    draft.answer = normalize_citations(draft.answer)  # one citation format for UI, verifier and eval
    return {
        "draft": draft.model_dump(),
        "revision_rounds": runs + 1,
        "trace": [
            f"AnalystAgent (pass {runs + 1}): status={draft.status}, "
            f"{len(draft.claims)} claims, cites={sorted({c for cl in draft.claims for c in cl.chunk_ids})}"
        ],
    }


def _offline_draft(state: TurnState) -> dict:
    """Degraded answer when the model is down: show the best passages, clearly labelled."""
    top = state.get("evidence", [])[:3]
    lines = [
        "_The language model is unavailable right now (rate limit or outage), so I can't write a "
        "verified answer. These are the most relevant document passages:_",
        *[f"- **[{e['chunk_id']}] {e['title']}** ({e['published']}): {e['text']}" for e in top],
    ]
    return {"status": "error", "answer": "\n".join(lines), "claims": []}
