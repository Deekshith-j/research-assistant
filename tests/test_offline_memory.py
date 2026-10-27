"""Memory stays dependable when the LLM provider is down (found by the acceptance test:
with both models rate-limited, "what do you remember about me?" used to return
unrelated document passages)."""

import pytest

from assistant.agents import analyst, coordinator, memory_agent, responder, verifier
from assistant.agents.intent import memory_intent
from assistant.llm import LLMUnavailableError
from assistant.memory.store import Store
from assistant.service import AssistantService


@pytest.mark.parametrize("text, expected", [
    ("What do you remember about me?", "list"),
    ("Forget everything you know about me.", "forget_all"),
    ("Please delete all my memories", "forget_all"),
    ("Remember that I work in the Dublin office.", "command"),
    ("Forget my answer-style preference.", "command"),
    ("Correction: my customers moved to the Team plan.", "command"),
    ("I'm on the Team plan, how long is retention?", None),        # a question -> research
    ("Do you remember the AQL timeout in 2.2?", None),             # about docs, not about me
])
def test_memory_intent_rules(text, expected):
    assert memory_intent(text) == expected


@pytest.fixture
def offline(tmp_path, monkeypatch):
    """Service whose every LLM call fails, as during an outage or exhausted quota."""
    def down(*_args, **_kwargs):
        raise LLMUnavailableError("simulated outage")
    for module in (coordinator, memory_agent, analyst, verifier, responder):
        monkeypatch.setattr(module, "structured_call", down)
    svc = AssistantService(Store(tmp_path / "offline.db"))
    user = svc.user("alice")
    return svc, user, user.create_session().id


def test_list_memories_without_llm(offline):
    svc, user, sid = offline
    user.add_memory("profile", "Supports Launch-plan customers")
    r = svc.ask("alice", sid, "What do you remember about me?")
    assert r.status == "memory"
    assert "Supports Launch-plan customers" in r.answer


def test_forget_everything_without_llm(offline):
    svc, user, sid = offline
    user.add_memory("profile", "Supports Launch-plan customers")
    r = svc.ask("alice", sid, "Forget everything you know about me.")
    assert user.list_memories() == []
    assert "Forgot everything" in r.answer


def test_other_memory_requests_change_nothing_and_say_so(offline):
    svc, user, sid = offline
    r = svc.ask("alice", sid, "Remember that I work in the Dublin office.")
    assert r.status == "memory"
    assert user.list_memories() == []
    assert "nothing was changed" in r.answer


def test_incomplete_memory_operations_are_invalid():
    # Acceptance-test regression: a "correct" without the new text silently lost the correction.
    from pydantic import ValidationError

    from assistant.agents.memory_agent import MemoryOp
    with pytest.raises(ValidationError):
        MemoryOp(action="correct", memory_id="m_1", content=None, reason="r")
    with pytest.raises(ValidationError):
        MemoryOp(action="add", kind="profile", content="  ", reason="r")
    with pytest.raises(ValidationError):
        MemoryOp(action="forget", reason="r")
    assert MemoryOp(action="correct", memory_id="m_1", content="Supports Team customers", reason="r")
