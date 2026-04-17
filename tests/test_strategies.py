"""Testa Pipeline e Debate como estratégias invocáveis via call_strategy."""
import asyncio
from unittest.mock import patch

from jarvas.agents.strategies import run_debate_strategy, run_pipeline
from jarvas.context import SessionContext
from jarvas.managed.toolset import TOOLS, execute_tool


def test_pipeline_strategy_wraps_guard_pipeline():
    ctx = SessionContext()
    fake = {"sintese": "SINTESE", "hermes": "h", "gemini": "g", "deepseek": "d"}
    with patch("jarvas.guard_pipeline.run", return_value=fake):
        result = run_pipeline("faça X", "chat", ctx)
    assert result.content == "SINTESE"
    assert result.agent_name == "pipeline_strategy"
    assert ctx.historico[-1]["content"] == "SINTESE"


def test_debate_strategy_wraps_debate():
    ctx = SessionContext()
    fake = {"topic": "X", "rounds": [], "consensus": "CONS"}
    with patch("jarvas.debate.run_debate", return_value=fake):
        result = run_debate_strategy("X", ctx)
    assert "CONS" in result.content
    assert ctx.last_debate_result == fake


def test_call_strategy_is_registered():
    assert "call_strategy" in TOOLS
    fn = TOOLS["call_strategy"]["function"]
    assert fn["name"] == "call_strategy"
    props = fn["parameters"]["properties"]
    assert "name" in props and "message" in props


def test_execute_tool_pipeline():
    fake = {"sintese": "S", "hermes": "h", "gemini": "g", "deepseek": "d"}
    with patch("jarvas.guard_pipeline.run", return_value=fake):
        out, err = asyncio.run(execute_tool(
            "call_strategy",
            {"name": "pipeline", "message": "X", "task_type": "chat"},
            allowed_tools=["call_strategy"],
        ))
    assert err is False
    assert out == "S"


def test_execute_tool_debate():
    fake = {"topic": "T", "rounds": [], "consensus": "C"}
    with patch("jarvas.debate.run_debate", return_value=fake):
        out, err = asyncio.run(execute_tool(
            "call_strategy",
            {"name": "debate", "message": "T", "max_rounds": 1},
            allowed_tools=["call_strategy"],
        ))
    assert err is False
    assert "C" in out


def test_execute_tool_unknown_strategy():
    out, err = asyncio.run(execute_tool(
        "call_strategy",
        {"name": "ghost", "message": "x"},
        allowed_tools=["call_strategy"],
    ))
    assert err is True
    assert "Unknown strategy" in out


def test_execute_tool_denied_without_allowlist():
    out, err = asyncio.run(execute_tool(
        "call_strategy",
        {"name": "pipeline", "message": "x"},
        allowed_tools=["read"],
    ))
    assert err is True
    assert "not allowed" in out.lower()
