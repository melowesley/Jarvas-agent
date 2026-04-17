"""Testa o endpoint /v1/sessions/{id}/dump (v0.5.0 observability)."""
from fastapi.testclient import TestClient

from jarvas.api import app
from jarvas.managed import store as _store
from jarvas.managed.models import AgentCreate, SessionCreate


def _fresh_client():
    _store._agents.clear()
    _store._versions.clear()
    _store._sessions.clear()
    _store._events.clear()
    return TestClient(app)


def test_dump_not_found():
    client = _fresh_client()
    r = client.get("/v1/sessions/fake-id/dump")
    assert r.status_code == 404


def test_dump_returns_session_and_agent():
    client = _fresh_client()
    agent = _store.create_agent(AgentCreate(name="dumper", model="m"))
    session = _store.create_session(SessionCreate(agent_id=agent.id, title="t"))
    _store.append_event(session.id, {
        "type": "agent.tool_use",
        "tool_call_id": "call_x",
        "tool_name": "bash",
        "tool_input": {"command": "ls"},
        "timestamp": "2026-04-17T00:00:00Z",
    })
    _store.append_event(session.id, {
        "type": "agent.tool_result",
        "tool_call_id": "call_x",
        "output": "x",
        "timestamp": "2026-04-17T00:00:01Z",
    })
    _store.append_event(session.id, {
        "type": "agent.delegation",
        "from": "hermes",
        "to": "gemini_analyst",
        "depth": 1,
        "timestamp": "2026-04-17T00:00:02Z",
    })

    r = client.get(f"/v1/sessions/{session.id}/dump")
    assert r.status_code == 200
    data = r.json()
    assert data["session"]["id"] == session.id
    assert data["agent"]["name"] == "dumper"
    assert data["events_count"] == 3
    assert len(data["tool_calls"]) == 1
    assert data["tool_calls"][0]["tool_name"] == "bash"
    assert len(data["delegations"]) == 1
    assert data["delegations"][0]["to"] == "gemini_analyst"
