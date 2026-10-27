"""Coordinator Agent: routes the message and plans the research.

It turns a possibly context-dependent follow-up ("and on Team?") into a standalone
question plus a few search queries for the Research Agent.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from assistant.agents import prompts
from assistant.agents.context import format_history, format_memories
from assistant.agents.intent import memory_intent
from assistant.agents.state import TurnState
from assistant.llm import LLMUnavailableError, structured_call


class Plan(BaseModel):
    route: Literal["research", "memory", "chat"]
    standalone_question: str
    search_queries: list[str] = Field(default_factory=list, description="1-4 search queries")
    reasoning: str = Field(description="One sentence explaining the route and plan.")


def plan_turn(state: TurnState) -> dict:
    prompt = (
        f"USER CONTEXT (personal memory, not evidence):\n{format_memories(state.get('memories', []))}\n\n"
        f"RECENT CONVERSATION:\n{format_history(state.get('history', []))}\n\n"
        f"NEW USER MESSAGE:\n{state['message']}"
    )
    try:
        plan = structured_call(Plan, prompts.COORDINATOR, prompt, tier="fast", run_name="Coordinator.plan")
    except LLMUnavailableError as exc:
        # Without the LLM: clear memory requests still go to the memory route (rule-based),
        # everything else is treated as research with the raw message.
        route = "memory" if memory_intent(state["message"]) else "research"
        return {
            "route": route,
            "standalone_question": state["message"],
            "search_queries": [state["message"]],
            "trace": [f"Coordinator: LLM unavailable ({exc}); rule-based route={route}"],
        }

    # Always search with the standalone question too, and cap the number of queries.
    queries = list(dict.fromkeys([plan.standalone_question, *plan.search_queries]))[:5]
    return {
        "route": plan.route,
        "standalone_question": plan.standalone_question,
        "search_queries": queries,
        "trace": [
            f"Coordinator: route={plan.route} | question='{plan.standalone_question}' | "
            f"queries={queries} | why: {plan.reasoning}"
        ],
    }
