from unittest.mock import patch, MagicMock
from jarvas.context import SessionContext
from jarvas.orchestrator import process
import jarvas.orchestrator as _orch


def test_process_chat():
    ctx = SessionContext()
    mock = MagicMock(return_value="chat ok")
    with patch.dict(_orch._HANDLERS, {"CHAT": mock}):
        result = process("oi tudo bem?", ctx)
    assert result == "chat ok"
    mock.assert_called_once()


def test_process_pipeline():
    ctx = SessionContext()
    mock = MagicMock(return_value="pipeline ok")
    with patch.dict(_orch._HANDLERS, {"PIPELINE": mock}):
        result = process("escreva um script python", ctx)
    assert result == "pipeline ok"


def test_process_debate():
    ctx = SessionContext()
    mock = MagicMock(return_value="debate ok")
    with patch.dict(_orch._HANDLERS, {"DEBATE": mock}):
        result = process("debate sobre sql vs nosql", ctx)
    assert result == "debate ok"


def test_process_file_read():
    ctx = SessionContext()
    mock = MagicMock(return_value="leitura ok")
    with patch.dict(_orch._HANDLERS, {"FILE_READ": mock}):
        result = process("leia o arquivo main.py", ctx)
    assert result == "leitura ok"


def test_process_file_edit():
    ctx = SessionContext()
    mock = MagicMock(return_value="edicao ok")
    with patch.dict(_orch._HANDLERS, {"FILE_EDIT": mock}):
        result = process("edite o arquivo utils.py para snake_case", ctx)
    assert result == "edicao ok"


def test_process_set_project():
    ctx = SessionContext()
    mock = MagicMock(return_value="projeto ok")
    with patch.dict(_orch._HANDLERS, {"SET_PROJECT": mock}):
        result = process("trabalhar em #C:/projetos/ocr", ctx)
    assert result == "projeto ok"


def test_process_store_memory():
    ctx = SessionContext()
    mock = MagicMock(return_value="memoria ok")
    with patch.dict(_orch._HANDLERS, {"STORE_MEMORY": mock}):
        result = process("armazene as ultimas interacoes", ctx)
    assert result == "memoria ok"


def test_process_attach():
    ctx = SessionContext()
    mock = MagicMock(return_value="arquivo ok")
    with patch.dict(_orch._HANDLERS, {"ATTACH": mock}):
        result = process("analise o arquivo relatorio.pdf", ctx)
    assert result == "arquivo ok"


def test_process_search_web():
    ctx = SessionContext()
    mock = MagicMock(return_value="web ok")
    with patch.dict(_orch._HANDLERS, {"SEARCH_WEB": mock}):
        result = process("pesquise sobre pytesseract", ctx)
    assert result == "web ok"
