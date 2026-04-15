from unittest.mock import patch, MagicMock
from jarvas.context import SessionContext
from jarvas.guard_pipeline import run, run_edit


def _mock_hermes(msg, historico=None, modelo=None):
    return (f"hermes:{msg[:20]}", "mock-model")


def _mock_gemini(msg):
    return f"gemini:{msg[:20]}"


def _mock_deepseek(msg):
    return f"deepseek:{msg[:20]}"


@patch("jarvas.guard_pipeline.save_pipeline_result")
@patch("jarvas.guard_pipeline.hermes_chat", side_effect=_mock_hermes)
@patch("jarvas.guard_pipeline.gemini_chat", side_effect=_mock_gemini)
@patch("jarvas.guard_pipeline.deepseek_chat", side_effect=_mock_deepseek)
def test_run_returns_four_keys(mock_ds, mock_g, mock_h, mock_save):
    ctx = SessionContext()
    result = run("como funciona um loop?", "code", ctx)
    assert "hermes" in result
    assert "gemini" in result
    assert "deepseek" in result
    assert "sintese" in result


@patch("jarvas.guard_pipeline.save_pipeline_result")
@patch("jarvas.guard_pipeline.hermes_chat", side_effect=_mock_hermes)
@patch("jarvas.guard_pipeline.gemini_chat", side_effect=_mock_gemini)
@patch("jarvas.guard_pipeline.deepseek_chat", side_effect=_mock_deepseek)
def test_run_saves_to_context(mock_ds, mock_g, mock_h, mock_save):
    ctx = SessionContext()
    run("analise esse codigo", "analysis", ctx)
    assert ctx.last_pipeline_result is not None
    assert "sintese" in ctx.last_pipeline_result


@patch("jarvas.guard_pipeline.save_pipeline_result")
@patch("jarvas.guard_pipeline.hermes_chat", side_effect=_mock_hermes)
@patch("jarvas.guard_pipeline.gemini_chat", side_effect=_mock_gemini)
@patch("jarvas.guard_pipeline.deepseek_chat", side_effect=_mock_deepseek)
def test_run_calls_save(mock_ds, mock_g, mock_h, mock_save):
    ctx = SessionContext()
    run("codigo python", "code", ctx)
    mock_save.assert_called_once()


@patch("jarvas.guard_pipeline.hermes_chat")
def test_run_edit_strips_markdown(mock_h):
    mock_h.return_value = ("```python\ndef foo():\n    pass\n```", "model")
    result = run_edit("def foo(): pass", "adicione docstring")
    assert result == "def foo():\n    pass"


@patch("jarvas.guard_pipeline.hermes_chat")
def test_run_edit_returns_plain_code(mock_h):
    mock_h.return_value = ("def foo():\n    \"\"\"docstring\"\"\"\n    pass", "model")
    result = run_edit("def foo(): pass", "adicione docstring")
    assert "docstring" in result
