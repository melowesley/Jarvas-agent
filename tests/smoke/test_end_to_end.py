"""Smoke end-to-end: supervisor.route() com Intent CHAT real."""
import uuid

import pytest


@pytest.mark.usefixtures("require_openrouter")
def test_supervisor_chat_end_to_end():
    from jarvas.agents import supervisor
    from jarvas.context import SessionContext
    from jarvas.intent_parser import Intent

    ctx = SessionContext(session_id=f"smoke-{uuid.uuid4().hex[:8]}", historico=[])
    intent = Intent(type="CHAT", raw="Diga apenas OK", args={})

    resposta = supervisor.route(intent, ctx)

    assert isinstance(resposta, str) and resposta.strip()
    assert len(ctx.historico) == 2, "supervisor deveria atualizar histórico (user+assistant)"
