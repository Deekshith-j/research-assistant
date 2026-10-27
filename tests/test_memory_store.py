"""Memory store: isolation between users, corrections, forgetting and the storage policy."""

import pytest

from assistant.memory.store import MemoryRejected, Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "test.db")


def test_users_are_isolated(store):
    alice, bob = store.for_user("alice"), store.for_user("bob")
    alice.add_memory("profile", "Supports Team-plan customers")
    s = alice.create_session()

    assert bob.list_memories() == []
    assert bob.list_sessions() == []
    assert not bob.owns_session(s.id)
    with pytest.raises(PermissionError):
        bob.add_message(s.id, "user", "hello")  # cannot write into Alice's session
    assert bob.get_messages(s.id) == []         # cannot read it either


def test_bob_cannot_forget_or_correct_alices_memory(store):
    alice, bob = store.for_user("alice"), store.for_user("bob")
    mem = alice.add_memory("profile", "Works in the Pune office")
    assert bob.forget_memory(mem.id) is False
    with pytest.raises(KeyError):
        bob.correct_memory(mem.id, "hacked")
    assert alice.get_memory(mem.id).content == "Works in the Pune office"


def test_correction_supersedes_old_memory(store):
    u = store.for_user("alice")
    old = u.add_memory("profile", "Supports Team-plan customers")
    new = u.correct_memory(old.id, "Supports Enterprise customers")

    active = u.list_memories()
    assert [m.content for m in active] == ["Supports Enterprise customers"]
    assert new.supersedes == old.id
    assert u.get_memory(old.id).status == "superseded"


def test_forget_removes_history_and_scrubs_audit_log(store):
    u = store.for_user("alice")
    old = u.add_memory("work_context", "Investigating Northwind duplicate rows")
    new = u.correct_memory(old.id, "Investigating Northwind export failures")
    assert u.forget_memory(new.id)

    assert u.list_memories(include_superseded=True) == []  # whole correction chain is gone
    assert all("Northwind" not in (e["detail"] or "") for e in u.memory_events())


def test_forget_all(store):
    u = store.for_user("alice")
    u.add_memory("profile", "Support engineer")
    u.add_memory("preference", "Prefers bullet points")
    assert u.forget_all() == 2
    assert u.list_memories() == []


@pytest.mark.parametrize("content", [
    "My ingestion key is gsk_abcdefghijklmnopqrstuvwxyz123456",
    "password: hunter2hunter2",
    "Is on medical leave for surgery next week",
])
def test_policy_rejects_secrets_and_sensitive_data(store, content):
    with pytest.raises(MemoryRejected):
        store.for_user("alice").add_memory("profile", content)


def test_duplicate_memories_are_not_stored_twice(store):
    u = store.for_user("alice")
    a = u.add_memory("preference", "Prefers short answers")
    b = u.add_memory("preference", "prefers short answers")
    assert a.id == b.id and len(u.list_memories()) == 1
