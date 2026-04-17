"""v0.5.0: orchestrator.process() delega ao Supervisor multi-agente.

Os mocks passam a patchar as funções que o Supervisor invoca em cada caminho
(registry.get_agent, strategies, adapters). O contrato público de
`process(mensagem, ctx) -> str` continua idêntico ao v0.4.x.
"""
from unittest.mock import MagicMock, patch

from jarvas.agents.base import AgentResult
from jarvas.context import SessionContext
from jarvas.orchestrator import process


def _fake_agent(content: str) -> MagicMock:
    agent = MagicMock()
    agent.run.return_value = AgentResult(content=content, model="m", agent_name="x")
    return agent


def test_process_chat():
    ctx = SessionContext()
    with patch("jarvas.agents.supervisor.get_agent", return_value=_fake_agent("chat ok")), \
         patch("jarvas.agents.supervisor.save_message", create=True, new=MagicMock()), \
         patch("jarvas.router.detect_task_type", return_value="chat"):
        result = process("oi tudo bem?", ctx)
    assert result == "chat ok"


def test_process_pipeline():
    ctx = SessionContext()
    fake = AgentResult(content="pipeline ok", model="m", agent_name="hermes")
    with patch("jarvas.agents.supervisor.run_pipeline", return_value=fake):
        result = process("escreva um script python", ctx)
    assert result == "pipeline ok"


def test_process_debate():
    ctx = SessionContext()
    fake = AgentResult(content="debate ok", model="m", agent_name="hermes")
    with patch("jarvas.agents.supervisor.run_debate_strategy", return_value=fake):
        result = process("debate sobre sql vs nosql", ctx)
    assert result == "debate ok"


def test_process_file_read():
    ctx = SessionContext()
    with patch("jarvas.file_editor.read_file", return_value="conteudo"):
        result = process("leia o arquivo main.py", ctx)
    assert "main.py" in result
    assert "conteudo" in result


def test_process_file_edit():
    ctx = SessionContext()
    with patch(
        "jarvas.file_editor.edit_file",
        return_value={"path": "utils.py", "diff": "- old\n+ new"},
    ):
        result = process("edite o arquivo utils.py para snake_case", ctx)
    assert "utils.py" in result
    assert "diff" in result


def test_process_set_project():
    ctx = SessionContext()
    result = process("trabalhar em #C:/projetos/ocr", ctx)
    assert "C:/projetos/ocr" in result
    assert ctx.project_path == "C:/projetos/ocr"


def test_process_store_memory():
    ctx = SessionContext()
    with patch(
        "jarvas.agents.supervisor.get_agent",
        return_value=_fake_agent("memoria ok"),
    ):
        result = process("armazene as ultimas interacoes", ctx)
    assert result == "memoria ok"


def test_process_attach():
    ctx = SessionContext()
    with patch(
        "jarvas.file_processor.process_file",
        return_value={"output_path": "/tmp/out.md", "summary": "pdf lido"},
    ):
        result = process("analise o arquivo relatorio.pdf", ctx)
    assert "out.md" in result
    assert "pdf lido" in result


def test_process_search_web():
    ctx = SessionContext()
    with patch("jarvas.guard_gemini.web_search", return_value="web ok"):
        result = process("pesquise sobre pytesseract", ctx)
    assert result == "web ok"
