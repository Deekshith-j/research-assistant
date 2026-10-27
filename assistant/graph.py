"""LangGraph workflow that connects the agents.

    START
      |
    recall_memories            (Memory Agent - load user context)
      |            \
    update_memories  plan      (Memory Agent and Coordinator run in parallel)
      |            /
    dispatch  --route-->  finalize_memory | finalize_chat
      |
    research -> analyse -> verify --pass-->  finalize_research
        ^          ^         |
        |          +-revise--+          (at most one extra Analyst pass)
        +---retrieve_more----+          (at most one extra research round)

Every node shows up as a named span in LangSmith, so a question can be followed
step by step through the trace.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from assistant.agents.analyst import analyse
from assistant.agents.coordinator import plan_turn
from assistant.agents.memory_agent import recall_memories, update_memories
from assistant.agents.researcher import MAX_RESEARCH_ROUNDS, research
from assistant.agents.responder import finalize_chat, finalize_memory, finalize_research
from assistant.agents.state import TurnState
from assistant.agents.verifier import verify

MAX_ANALYST_PASSES = 2   # first draft + one revision


def _dispatch(state: TurnState) -> dict:
    """Join point after the parallel Memory Agent / Coordinator step (no state change)."""
    return {}


def _route_after_dispatch(state: TurnState) -> str:
    return {"memory": "finalize_memory", "chat": "finalize_chat"}.get(state.get("route", "research"), "research")


def _route_after_verify(state: TurnState) -> str:
    """Decide whether the answer is ready or needs another Analyst / Research pass."""
    verdict = state.get("verdict", {}).get("verdict", "pass")
    if verdict == "pass" or state.get("revision_rounds", 0) >= MAX_ANALYST_PASSES:
        return "finalize_research"
    if verdict == "retrieve_more" and state.get("research_rounds", 0) < MAX_RESEARCH_ROUNDS:
        return "research"
    return "analyse"


@lru_cache(maxsize=1)
def build_graph():
    g = StateGraph(TurnState)

    # Nodes (one per agent step). The node names are what you see in LangSmith.
    g.add_node("recall_memories", recall_memories)
    g.add_node("update_memories", update_memories)
    g.add_node("plan", plan_turn)
    g.add_node("dispatch", _dispatch)
    g.add_node("research", research)
    g.add_node("analyse", analyse)
    g.add_node("verify", verify)
    g.add_node("finalize_research", finalize_research)
    g.add_node("finalize_memory", finalize_memory)
    g.add_node("finalize_chat", finalize_chat)

    # Edges
    g.add_edge(START, "recall_memories")
    g.add_edge("recall_memories", "update_memories")  # fan-out: these two run in parallel
    g.add_edge("recall_memories", "plan")
    g.add_edge(["update_memories", "plan"], "dispatch")  # fan-in: wait for both
    g.add_conditional_edges("dispatch", _route_after_dispatch,
                            ["research", "finalize_memory", "finalize_chat"])
    g.add_edge("research", "analyse")
    g.add_edge("analyse", "verify")
    g.add_conditional_edges("verify", _route_after_verify, ["finalize_research", "analyse", "research"])
    for end_node in ("finalize_research", "finalize_memory", "finalize_chat"):
        g.add_edge(end_node, END)

    return g.compile()
