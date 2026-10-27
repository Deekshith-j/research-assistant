"""Final step: turns the agents' work into the message the user sees.

* research route -> verified draft + source list + any warnings
* memory route   -> confirmation of what was remembered / corrected / forgotten (or a list)
* chat route     -> short small-talk reply (no company facts)
In every route, memory changes made this turn are reported, so memory is never silent.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from assistant.agents import prompts
from assistant.agents.context import format_history, user_store
from assistant.agents.state import TurnState
from assistant.agents.verifier import extract_citations
from assistant.llm import LLMUnavailableError, structured_call


class ChatReply(BaseModel):
    reply: str


def describe_memory_ops(ops: list[dict]) -> list[str]:
    """Human-readable lines for each memory operation of this turn."""
    lines = []
    for op in ops:
        if op["action"] == "unavailable":
            lines.append("I couldn't process this memory request because the language model is unavailable "
                         "right now, so nothing was changed. You can view, edit or delete memories in the Memory tab.")
        elif op["status"] == "rejected":
            lines.append(f"Not remembered ({op.get('detail')}).")
        elif op["action"] == "add":
            lines.append(f"Remembered: \"{op['content']}\"")
        elif op["action"] == "correct":
            lines.append(f"Updated memory: \"{op.get('previous')}\" -> \"{op['content']}\"")
        elif op["action"] == "forget":
            lines.append(f"Forgotten one {op.get('kind') or ''} memory (deleted permanently).")
        elif op["action"] == "forget_all":
            lines.append(f"Forgot everything I remembered about you ({op.get('detail')}).")
    return lines


def finalize_research(state: TurnState) -> dict:
    draft = state.get("draft", {})
    verdict = state.get("verdict", {})
    evidence = {e["chunk_id"]: e for e in state.get("evidence", [])}

    # Sources = cited ids that really are in the evidence (invalid ids never become sources).
    cited = [cid for cid in extract_citations(draft.get("answer", "")) if cid in evidence]
    citations = [
        {"chunk_id": cid, "title": evidence[cid]["title"], "published": evidence[cid]["published"]}
        for cid in cited
    ]

    warnings: list[str] = []
    if verdict.get("verdict") not in (None, "pass"):
        warnings.append("The reviewer could not fully verify this answer: " + "; ".join(verdict.get("issues", [])[:3]))
    if verdict.get("warning"):
        warnings.append(verdict["warning"])

    answer = draft.get("answer", "")
    if (notes := describe_memory_ops(state.get("memory_ops", []))):
        answer += "\n\n---\n_Memory: " + " ".join(notes) + "_"

    return {
        "final_answer": answer,
        "answer_status": draft.get("status", "error"),
        "citations": citations,
        "warnings": warnings,
        "trace": [f"Responder: status={draft.get('status')}, sources={cited}, warnings={len(warnings)}"],
    }


def finalize_memory(state: TurnState, config: RunnableConfig) -> dict:
    lines = describe_memory_ops(state.get("memory_ops", []))
    if state.get("memory_list_requested"):
        memories = user_store(config).list_memories()
        lines.append(
            "Here is what I remember about you:\n" + "\n".join(f"- ({m.kind}) {m.content}" for m in memories)
            if memories else "I don't have anything remembered about you."
        )
        lines.append("You can also review, edit or delete these in the **Memory** tab.")
    if not lines:
        lines = ["I didn't find anything to remember or forget in that message."]
    return {
        "final_answer": "\n\n".join(lines),
        "answer_status": "memory",
        "citations": [],
        "trace": ["Responder: memory confirmation"],
    }


def finalize_chat(state: TurnState) -> dict:
    prompt = f"RECENT CONVERSATION:\n{format_history(state.get('history', [])[-4:])}\n\nUSER: {state['message']}"
    try:
        reply = structured_call(ChatReply, prompts.CHAT, prompt, tier="fast", run_name="Responder.chat").reply
    except LLMUnavailableError:
        reply = "Hi! Ask me anything about Asterline's documentation and I'll answer with citations."
    if (notes := describe_memory_ops(state.get("memory_ops", []))):
        reply += "\n\n---\n_Memory: " + " ".join(notes) + "_"
    return {"final_answer": reply, "answer_status": "chat", "citations": [], "trace": ["Responder: chat reply"]}
