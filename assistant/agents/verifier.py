"""Verifier Agent: checks the Analyst's draft before it reaches the user.

Two layers:
  1. Deterministic checks (cannot be talked out of): every cited chunk id must be
     one of the retrieved evidence chunks, and an "answered" draft must cite something.
  2. LLM review: are the claims actually stated by the cited chunks, is anything
     superseded presented as current, are gaps admitted?
The verdict decides the next step: pass -> finalize, revise -> Analyst again,
retrieve_more -> Research Agent with new queries (see graph.py for loop limits).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from assistant.agents import prompts
from assistant.agents.context import format_evidence
from assistant.agents.researcher import MAX_RESEARCH_ROUNDS
from assistant.agents.state import TurnState
from assistant.llm import LLMUnavailableError, structured_call

_BRACKET = re.compile(r"\[([^\[\]]+)\]")
_CHUNK_ID = re.compile(r"^[a-z0-9\-]+:\d+$")


class Verdict(BaseModel):
    verdict: Literal["pass", "revise", "retrieve_more"]
    issues: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    missing_info_queries: list[str] = Field(default_factory=list)


def normalize_citations(answer: str) -> str:
    """Rewrite full-width brackets to ASCII: gpt-oss models often cite as '【pricing:0】' (eval finding)."""
    return answer.replace("【", "[").replace("】", "]")


def extract_citations(answer: str) -> list[str]:
    """All chunk ids cited inline, e.g. '[pricing:1]' or '[pricing:1, sla:0]' (order kept, no dupes)."""
    ids: list[str] = []
    for group in _BRACKET.findall(normalize_citations(answer)):
        for part in re.split(r"[,;]\s*", group):
            part = part.strip()
            if _CHUNK_ID.match(part) and part not in ids:
                ids.append(part)
    return ids


def deterministic_issues(draft: dict, evidence_ids: set[str]) -> list[str]:
    """Rule-based problems with the draft's citations."""
    inline = set(extract_citations(draft.get("answer", "")))
    cited = inline | {cid for claim in draft.get("claims", []) for cid in claim.get("chunk_ids", [])}
    issues = [f"Cited id [{cid}] is not in the retrieved evidence." for cid in sorted(cited - evidence_ids)]
    # Only inline [chunk_id] citations reach the user's Sources list, so the claims list alone is not enough
    # (evaluation finding R16: the model wrote "- handbook:1" without brackets).
    if draft.get("status") in ("answered", "partial") and not (inline & evidence_ids):
        issues.append("The answer text has no inline citation. Cite every fact as [chunk_id], e.g. [pricing:0].")
    return issues


def verify(state: TurnState) -> dict:
    draft = state.get("draft", {})
    evidence = state.get("evidence", [])

    if draft.get("status") == "error":  # offline fallback, nothing to verify
        return {"verdict": {"verdict": "pass", "issues": []}, "trace": ["VerifierAgent: skipped (no LLM draft)"]}

    rule_issues = deterministic_issues(draft, {e["chunk_id"] for e in evidence})

    claims = "\n".join(f"- {c['statement']} -> {c.get('chunk_ids', [])}" for c in draft.get("claims", []))
    prompt = (
        f"QUESTION: {state.get('standalone_question') or state['message']}\n\n"
        f"EVIDENCE:\n{format_evidence(evidence)}\n\n"
        f"DRAFT STATUS: {draft.get('status')}\nDRAFT ANSWER:\n{draft.get('answer')}\n\nCLAIMS:\n{claims or '(none)'}"
    )
    try:
        verdict = structured_call(Verdict, prompts.VERIFIER, prompt, tier="main", run_name="VerifierAgent.check")
        result = verdict.model_dump()
    except LLMUnavailableError as exc:
        # Can't run the LLM check: rely on the deterministic one and warn the user.
        result = {"verdict": "revise" if rule_issues else "pass", "issues": [],
                  "unsupported_claims": [], "missing_info_queries": [],
                  "warning": f"Answer could not be independently verified ({type(exc).__name__})."}

    # Deterministic problems always force at least a revision.
    if rule_issues:
        result["issues"] = rule_issues + result.get("issues", [])
        if result["verdict"] == "pass":
            result["verdict"] = "revise"

    # "Second look" rule: never accept "not documented" after only one search.
    # Evaluation finding M03: the right chunk was retrievable but crowded out in round 1.
    if (result["verdict"] == "pass"
            and draft.get("status") in ("insufficient_evidence", "partial")
            and state.get("research_rounds", 0) < MAX_RESEARCH_ROUNDS):
        result["verdict"] = "retrieve_more"
        result["issues"] = result.get("issues", []) + [
            "The draft reports missing information; a broader search was run. Re-check whether the "
            "new evidence answers the question before saying it is not documented."
        ]

    return {
        "verdict": result,
        "trace": [
            f"VerifierAgent: verdict={result['verdict']} | issues={result.get('issues', [])} | "
            f"unsupported={result.get('unsupported_claims', [])} | more_queries={result.get('missing_info_queries', [])}"
        ],
    }
