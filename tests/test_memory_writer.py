import json
from unittest.mock import patch, MagicMock
from jarvas.context import SessionContext
from jarvas.memory_writer import store


def _mock_hermes_json(prompt, historico=None, modelo=None):
    payload = json.dumps({
        "acertos": ["uso de snake_case"],
        "erros": ["variavel nao definida"],
        "decisoes": ["usar openpyxl"],
        "padroes": ["sempre validar entrada"],
    })
    return (payload, "mock-model")


@patch("jarvas.memory_writer.save_memory_log")
@patch("jarvas.memory_writer.handle_hmem", return_value='{"id": "drawer-abc"}')
@patch("jarvas.memory_writer.hermes_chat", side_effect=_mock_hermes_json)
def test_store_calls_hmem_add(mock_h, mock_hmem, mock_save):
    ctx = SessionContext(project_path="C:/projetos/ocr")
    ctx.historico = [
        {"role": "user", "content": "como faco X?"},
        {"role": "assistant", "content": "faca Y"},
    ]
    result = store(ctx, scope=5)
    mock_hmem.assert_called_once()
    args = mock_hmem.call_args[0][0]
    assert args.startswith("add wing_code")


@patch("jarvas.memory_writer.save_memory_log")
@patch("jarvas.memory_writer.handle_hmem", return_value='{"id": "drawer-xyz"}')
@patch("jarvas.memory_writer.hermes_chat", side_effect=_mock_hermes_json)
def test_store_uses_general_room_without_project(mock_h, mock_hmem, mock_save):
    ctx = SessionContext()
    ctx.historico = [{"role": "user", "content": "oi"}]
    store(ctx)
    args = mock_hmem.call_args[0][0]
    assert "wing_user" in args
    assert "general" in args


@patch("jarvas.memory_writer.save_memory_log")
@patch("jarvas.memory_writer.handle_hmem", return_value='{"id": "d1"}')
@patch("jarvas.memory_writer.hermes_chat", side_effect=_mock_hermes_json)
def test_store_calls_save_memory_log(mock_h, mock_hmem, mock_save):
    ctx = SessionContext()
    ctx.historico = [{"role": "user", "content": "teste"}]
    store(ctx)
    mock_save.assert_called_once()


@patch("jarvas.memory_writer.save_memory_log")
@patch("jarvas.memory_writer.handle_hmem", return_value="texto sem json")
@patch("jarvas.memory_writer.hermes_chat")
def test_store_handles_bad_json_from_hermes(mock_h, mock_hmem, mock_save):
    mock_h.return_value = ("isso nao e json valido", "model")
    ctx = SessionContext()
    ctx.historico = [{"role": "user", "content": "x"}]
    result = store(ctx)  # nao deve lancar excecao
    assert result is not None
