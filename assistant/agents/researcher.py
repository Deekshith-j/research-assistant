"""Research Agent: gathers evidence from the company documents.

Round 1 executes the Coordinator's search plan with the local hybrid retriever.
Round 2 (only when the Verifier asks for it) runs the Verifier's follow-up queries,
or, if it gave none, the standalone question on its own with a deeper cut-off, and
merges the new chunks with what was already found.

After each search the other chunks of the best-ranked documents are added
("sibling expansion"), because the answer is often in a neighbouring chunk that does
not repeat the search terms (evaluation finding R11, see docs/EVALUATION.md).

It is intentionally deterministic (no LLM): retrieval is reproducible, free and
easy to evaluate in isolation (see eval/run_retrieval_eval.py).
"""

from __future__ import annotations

from assistant.agents.state import TurnState
from assistant.config import settings
from assistant.knowledge.retriever import get_retriever

MAX_RESEARCH_ROUNDS = 2  # initial search + one follow-up search
MAX_EVIDENCE = 18        # upper bound after two rounds with sibling expansion
SIBLING_DOCS = 3         # expand the 3 best-ranked documents


def research(state: TurnState) -> dict:
    rounds = state.get("research_rounds", 0)
    retriever = get_retriever()

    if rounds == 0:
        # First round: the Coordinator's plan.
        queries = state.get("search_queries") or [state["message"]]
        k = settings.retrieval_top_k
        existing: list[dict] = []
    else:
        # Follow-up round requested by the Verifier. Without explicit queries, search the
        # standalone question alone: the planner's extra queries can crowd out the right chunk.
        queries = state.get("verdict", {}).get("missing_info_queries") or [state["standalone_question"]]
        k = settings.retrieval_top_k + 4
        existing = state.get("evidence", [])

    found = retriever.expand_siblings(retriever.multi_search(queries, k=k), max_docs=SIBLING_DOCS)

    # Merge: keep earlier evidence first, then add new chunks not seen before.
    seen = {e["chunk_id"] for e in existing}
    new = [sc.chunk.to_evidence(sc.score) for sc in found if sc.chunk.chunk_id not in seen]
    evidence = (existing + new)[:MAX_EVIDENCE]

    return {
        "evidence": evidence,
        "research_rounds": rounds + 1,
        "trace": [
            f"ResearchAgent round {rounds + 1}: queries={queries} -> "
            f"{[e['chunk_id'] for e in evidence]} ({len(new)} new)"
        ],
    }
