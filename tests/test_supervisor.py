"""Testa o Supervisor — roteamento de Intent → agent."""
from unittest.mock import patch

from jarvas.agents.supervisor import route
from jarvas.context import SessionContext
from jarvas.intent_parser import Intent


def test_route_chat_delegates_to_hermes_agent():
    ctx = SessionContext()
    intent = Intent(type="CHAT", raw="oi", args={})
    with patch("jarvas.hermes_client.chat", return_value=("resp", "m")) as mk, \
         patch("jarvas.supabase_client.save_message"):
        out = route(intent, ctx)
    mk.assert_called_once()
    assert out == "resp"
    assert ctx.historico[-1] == {"role": "assistant", "content": "resp"}


def test_route_pipeline_invokes_strategy():
    ctx = SessionContext()
    intent = Intent(type="PIPELINE", raw="code", args={"task_type": "code"})
    fake = {"sintese": "s", "hermes": "h", "gemini": "g", "deepseek": "d"}
    with patch("jarvas.guard_pipeline.run", return_value=fake) as mk:
        out = route(intent, ctx)
    mk.assert_called_once()
    assert out == "s"


def test_route_debate_invokes_strategy():
    ctx = SessionContext()
    intent = Intent(type="DEBATE", raw="debate X", args={"topic": "X"})
    fake = {"topic": "X", "rounds": [], "consensus": "c"}
    with patch("jarvas.debate.run_debate", return_value=fake):
        out = route(intent, ctx)
    assert "Consenso" in out or "consensus" in out.lower() or "c" in out
    assert ctx.last_debate_result == fake


def test_route_file_read():
    ctx = SessionContext()
    intent = Intent(type="FILE_READ", raw="leia main.py", args={})
    with patch("jarvas.file_editor.read_file", return_value="CONTENT") as mk:
        out = route(intent, ctx)
    mk.assert_called_once()
    assert "main.py" in out
    assert "CONTENT" in out


def test_route_file_edit():
    ctx = SessionContext()
    intent = Intent(type="FILE_EDIT", raw="edite utils.py", args={"instruction": "fix"})
    fake = {"path": "/x/utils.py", "diff": "---", "original": "a", "edited": "b"}
    with patch("jarvas.file_editor.edit_file", return_value=fake):
        out = route(intent, ctx)
    assert "utils.py" in out
    assert "diff" in out


def test_route_set_project_mutates_ctx():
    ctx = SessionContext()
    intent = Intent(type="SET_PROJECT", raw="#/tmp/p", args={"path": "/tmp/p"})
    out = route(intent, ctx)
    assert ctx.project_path == "/tmp/p"
    assert "/tmp/p" in out


def test_route_store_memory_uses_miner():
    ctx = SessionContext()
    intent = Intent(type="STORE_MEMORY", raw="armazene", args={"scope": 5})
    with patch("jarvas.memory_writer.store", return_value="stored") as mk:
        out = route(intent, ctx)
    mk.assert_called_once()
    assert out == "stored"


def test_route_search_web():
    ctx = SessionContext()
    intent = Intent(type="SEARCH_WEB", raw="pesquise py", args={"query": "py"})
    with patch("jarvas.guard_gemini.web_search", return_value="found") as mk:
        out = route(intent, ctx)
    mk.assert_called_once_with("py")
    assert out == "found"


def test_route_attach_process():
    ctx = SessionContext()
    intent = Intent(type="ATTACH", raw="processe relatorio.pdf", args={"path": "relatorio.pdf", "file_type": "pdf"})
    fake = {"output_path": "/tmp/out.txt", "summary": "resumo", "file_type": ".pdf"}
    with patch("jarvas.file_processor.process_file", return_value=fake):
        out = route(intent, ctx)
    assert "resumo" in out
