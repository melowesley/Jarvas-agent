"""Smoke: insert + select round-trip no Supabase."""
import uuid

import pytest


@pytest.mark.usefixtures("require_supabase")
def test_supabase_roundtrip():
    from jarvas.supabase_client import save_message, load_history

    session_id = f"smoke-{uuid.uuid4().hex[:8]}"
    save_message(session_id, "user", "ping smoke", task_type="chat")
    history = load_history(session_id, limit=10)

    assert any(m.get("content") == "ping smoke" for m in history), (
        f"insert ok mas select não retornou a mensagem: {history}"
    )
