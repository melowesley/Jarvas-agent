"""Testa logs estruturados v0.5.0."""
import json
import os
import time

from jarvas.managed import structured_log


def test_is_enabled_default(monkeypatch):
    monkeypatch.delenv("JARVAS_STRUCTURED_LOGS", raising=False)
    assert structured_log.is_enabled() is True


def test_is_disabled_via_env(monkeypatch):
    monkeypatch.setenv("JARVAS_STRUCTURED_LOGS", "0")
    assert structured_log.is_enabled() is False


def test_emit_writes_json_line(monkeypatch, capsys):
    monkeypatch.setenv("JARVAS_STRUCTURED_LOGS", "1")
    structured_log.emit(agent_name="hermes", tool_name="bash", duration_ms=42)
    err = capsys.readouterr().err.strip().splitlines()[-1]
    payload = json.loads(err)
    assert payload["agent_name"] == "hermes"
    assert payload["tool_name"] == "bash"
    assert payload["duration_ms"] == 42
    assert "ts" in payload


def test_emit_noop_when_disabled(monkeypatch, capsys):
    monkeypatch.setenv("JARVAS_STRUCTURED_LOGS", "0")
    structured_log.emit(agent_name="x")
    assert capsys.readouterr().err == ""


def test_timer_measures_duration():
    with structured_log.Timer() as t:
        time.sleep(0.01)
    assert t.duration_ms >= 10
