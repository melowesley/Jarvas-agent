"""Testa registry/contrato dos agents do Jarvas v0.5.0."""
from jarvas.agents import AgentProtocol, AgentResult, get_agent, list_agents


def test_defaults_registered():
    names = list_agents()
    esperados = {
        "hermes",
        "gemini_analyst",
        "deepseek_coder",
        "memory_miner",
        "file_editor",
        "autoescola_specialist",
        "uiux_specialist",
    }
    assert esperados.issubset(set(names))


def test_all_agents_satisfy_protocol():
    for name in list_agents():
        a = get_agent(name)
        assert isinstance(a, AgentProtocol), f"{name} não satisfaz AgentProtocol"
        assert a.name == name
        assert a.role
        assert isinstance(a.tools, list)
        assert a.memory_scope in ("session", "project", "global")


def test_get_agent_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        get_agent("desconhecido_xyz")


def test_agent_result_pydantic_schema():
    r = AgentResult(content="ok", model="m", agent_name="hermes")
    dump = r.model_dump()
    assert dump["content"] == "ok"
    assert dump["tool_calls"] == []
    assert dump["cost_usd"] == 0.0
    assert dump["confidence"] is None


def test_hermes_can_delegate_to_specialists():
    a = get_agent("hermes")
    assert "gemini_analyst" in a.can_delegate_to
    assert "deepseek_coder" in a.can_delegate_to
    assert "file_editor" in a.can_delegate_to
