"""Testa que cada adapter produz AgentResult válido e delega pra função legada."""
from unittest.mock import patch

from jarvas.agents import AgentResult, get_agent
from jarvas.context import SessionContext


def test_hermes_adapter_delegates_to_hermes_chat():
    ctx = SessionContext()
    with patch("jarvas.hermes_client.chat", return_value=("oi", "modelo-x")) as mk:
        result = get_agent("hermes").run("oi?", ctx)
    mk.assert_called_once()
    assert isinstance(result, AgentResult)
    assert result.content == "oi"
    assert result.model == "modelo-x"
    assert result.agent_name == "hermes"


def test_gemini_analyst_adapter_delegates():
    ctx = SessionContext()
    with patch("jarvas.guard_gemini.chat", return_value="analise ok") as mk:
        result = get_agent("gemini_analyst").run("analise X", ctx)
    mk.assert_called_once_with("analise X")
    assert result.content == "analise ok"
    assert result.agent_name == "gemini_analyst"


def test_deepseek_coder_adapter_delegates():
    ctx = SessionContext()
    with patch("jarvas.guard_deepseek.chat", return_value="code ok") as mk:
        result = get_agent("deepseek_coder").run("code Y", ctx)
    mk.assert_called_once_with("code Y")
    assert result.content == "code ok"
    assert result.agent_name == "deepseek_coder"


def test_memory_miner_adapter_delegates():
    ctx = SessionContext()
    with patch("jarvas.memory_writer.store", return_value="stored") as mk:
        result = get_agent("memory_miner").run("armazene", ctx)
    mk.assert_called_once()
    assert result.content == "stored"
    assert result.agent_name == "memory_miner"


def test_file_editor_adapter_read_op():
    ctx = SessionContext()
    with patch("jarvas.file_editor.read_file", return_value="conteudo") as mk:
        result = get_agent("file_editor").run("leia o arquivo main.py", ctx)
    mk.assert_called_once()
    assert "main.py" in result.content
    assert "conteudo" in result.content
    assert result.metadata["op"] == "read"


def test_file_editor_adapter_edit_op():
    ctx = SessionContext()
    fake = {"path": "/tmp/foo.py", "diff": "---\n+++", "original": "a", "edited": "b"}
    with patch("jarvas.file_editor.edit_file", return_value=fake) as mk:
        result = get_agent("file_editor").run("edite utils.py para snake_case", ctx)
    mk.assert_called_once()
    assert "utils.py" not in result.content or "editado" in result.content.lower()
    assert result.metadata["op"] == "edit"


def test_autoescola_specialist_uses_hermes_with_curriculum():
    ctx = SessionContext()
    with patch("jarvas.hermes_client.chat", return_value=("aula 1", "m")) as mk:
        result = get_agent("autoescola_specialist").run("qual a aula 1?", ctx)
    mk.assert_called_once()
    prompt = mk.call_args[0][0]
    assert "curriculum" in prompt.lower() or "autoescola" in prompt.lower()
    assert result.agent_name == "autoescola_specialist"


def test_uiux_specialist_injects_role_as_system_prompt():
    ctx = SessionContext()
    with patch("jarvas.hermes_client.chat", return_value=("resp", "m")) as mk:
        result = get_agent("uiux_specialist").run("design um card", ctx)
    mk.assert_called_once()
    kwargs = mk.call_args.kwargs
    assert kwargs.get("system_prompt", "").startswith("Você é o especialista UI/UX")
    assert result.agent_name == "uiux_specialist"
