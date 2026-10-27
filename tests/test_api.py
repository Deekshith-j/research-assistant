"""REST API: memory management, policy errors and user isolation (no LLM calls)."""

import pytest
from fastapi.testclient import TestClient

from assistant.api import create_app
from assistant.memory.store import Store
from assistant.service import AssistantService


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(AssistantService(Store(tmp_path / "api.db"))))


def test_unknown_user_is_rejected(client):
    assert client.get("/api/users/mallory/sessions").status_code == 404


def test_memory_crud(client):
    r = client.post("/api/users/alice/memories", json={"kind": "profile", "content": "Supports EU customers"})
    assert r.status_code == 201
    mid = r.json()["id"]

    r = client.patch(f"/api/users/alice/memories/{mid}", json={"content": "Supports US customers"})
    assert r.status_code == 200 and r.json()["supersedes"] == mid

    active = client.get("/api/users/alice/memories").json()
    assert [m["content"] for m in active] == ["Supports US customers"]

    assert client.delete(f"/api/users/alice/memories/{active[0]['id']}").status_code == 204
    assert client.get("/api/users/alice/memories?include_superseded=true").json() == []


def test_policy_rejection_returns_422(client):
    r = client.post("/api/users/alice/memories", json={"kind": "profile", "content": "password: hunter2hunter2"})
    assert r.status_code == 422


def test_users_cannot_see_each_others_data(client):
    client.post("/api/users/alice/memories", json={"kind": "profile", "content": "Works with Globex"})
    sid = client.post("/api/users/alice/sessions").json()["id"]

    assert client.get("/api/users/bob/memories").json() == []
    assert client.get("/api/users/bob/sessions").json() == []
    # Bob can neither read, write to, nor delete Alice's conversation.
    assert client.get(f"/api/users/bob/sessions/{sid}/messages").status_code == 404
    assert client.post(f"/api/users/bob/sessions/{sid}/messages", json={"text": "hi"}).status_code == 404
    assert client.delete(f"/api/users/bob/sessions/{sid}").status_code == 404
