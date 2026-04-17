"""Testa o hardening do toolset unificado v0.5.0."""
import asyncio
import os
from unittest.mock import patch

import pytest

from jarvas.managed.tool_security import (
    compute_tool_call_id,
    contains_secret,
    is_within,
    redact_secrets,
)
from jarvas.managed.toolset import DESTRUCTIVE_TOOLS, TOOLS, execute_tool


# ── tool_security helpers ─────────────────────────────────────────

def test_contains_secret_detects_api_key():
    assert contains_secret("API_KEY=abc123")
    assert contains_secret("token: sk-xyz")
    assert contains_secret("password=hunter2")


def test_contains_secret_ignores_normal_text():
    assert not contains_secret("apenas um texto normal")
    assert not contains_secret("def foo(): return 1")


def test_redact_secrets_masks_value_keeps_key():
    out = redact_secrets("API_KEY=sk-123\nfoo")
    assert "sk-123" not in out
    assert "API_KEY" in out
    assert "foo" in out


def test_compute_tool_call_id_deterministic():
    a = compute_tool_call_id("s1", 0, "bash", {"command": "ls"})
    b = compute_tool_call_id("s1", 0, "bash", {"command": "ls"})
    c = compute_tool_call_id("s1", 0, "bash", {"command": "rm"})
    assert a == b
    assert a != c
    assert a.startswith("call_")


def test_is_within_accepts_inside_path(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("x")
    assert is_within(str(f), str(tmp_path))


def test_is_within_rejects_outside_path(tmp_path):
    assert not is_within("/etc/passwd", str(tmp_path))


def test_is_within_accepts_any_when_no_workspace():
    assert is_within("/etc/passwd", None)


# ── TOOLS registry ─────────────────────────────────────────────────

def test_new_tools_registered():
    for name in ("file_read", "file_edit", "file_process", "mempalace_add", "call_strategy"):
        assert name in TOOLS


def test_destructive_set_covers_file_edit():
    assert "file_edit" in DESTRUCTIVE_TOOLS
    assert "vscode_edit" in DESTRUCTIVE_TOOLS
    assert "bash" in DESTRUCTIVE_TOOLS


# ── Destructive gate (opt-in) ──────────────────────────────────────

def test_destructive_gate_off_by_default():
    os.environ.pop("JARVAS_STRICT_DESTRUCTIVE", None)
    out, err = asyncio.run(execute_tool(
        "file_edit",
        {"path": "/tmp/x", "instruction": "fix", "preview_only": True},
        allowed_tools=["file_edit"],
    ))
    # preview branch does not require approval; should try to read the file
    assert "outside workspace" in out or "preview" in out.lower() or err


def test_destructive_gate_on_requires_approval():
    os.environ["JARVAS_STRICT_DESTRUCTIVE"] = "1"
    try:
        out, err = asyncio.run(execute_tool(
            "file_edit",
            {"path": "/tmp/x", "instruction": "fix"},
            allowed_tools=["file_edit"],
        ))
        assert err is True
        assert "destructive" in out.lower() or "approved" in out.lower()
    finally:
        os.environ.pop("JARVAS_STRICT_DESTRUCTIVE", None)


def test_destructive_gate_allows_preview_only():
    os.environ["JARVAS_STRICT_DESTRUCTIVE"] = "1"
    try:
        fake_orig = "original content"
        fake_edit = "edited content"
        with patch("jarvas.file_editor.read_file", return_value=fake_orig), \
             patch("jarvas.guard_pipeline.run_edit", return_value=fake_edit):
            out, err = asyncio.run(execute_tool(
                "file_edit",
                {"path": "/tmp/x.py", "instruction": "fix", "preview_only": True},
                allowed_tools=["file_edit"],
            ))
        assert err is False
        assert "PREVIEW" in out
    finally:
        os.environ.pop("JARVAS_STRICT_DESTRUCTIVE", None)


def test_destructive_gate_allows_approved():
    os.environ["JARVAS_STRICT_DESTRUCTIVE"] = "1"
    try:
        with patch("jarvas.file_editor.edit_file", return_value={
            "path": "/tmp/x.py", "diff": "---", "original": "a", "edited": "b",
        }):
            out, err = asyncio.run(execute_tool(
                "file_edit",
                {"path": "/tmp/x.py", "instruction": "fix", "_approved": True},
                allowed_tools=["file_edit"],
            ))
        assert err is False
        assert "Edited" in out
    finally:
        os.environ.pop("JARVAS_STRICT_DESTRUCTIVE", None)


# ── file_read masks secrets ───────────────────────────────────────

def test_file_read_redacts_secrets():
    with patch(
        "jarvas.file_editor.read_file",
        return_value="config:\nAPI_KEY=sk-secret-123\ndone",
    ):
        out, err = asyncio.run(execute_tool(
            "file_read",
            {"path": "cfg.txt"},
            allowed_tools=["file_read"],
        ))
    assert err is False
    assert "sk-secret-123" not in out
    assert "API_KEY" in out


def test_read_enforces_workspace():
    out, err = asyncio.run(execute_tool(
        "read",
        {"path": "/etc/passwd"},
        allowed_tools=["read"],
        workspace_path="/tmp/workspace",
    ))
    assert err is True
    assert "outside workspace" in out


# ── mempalace_add enriches metadata ────────────────────────────────

def test_mempalace_add_enriches_metadata():
    captured = {}

    def fake_hmem(cmd):
        captured["cmd"] = cmd
        return "ok"

    with patch("jarvas.mempalace_client.handle_hmem", side_effect=fake_hmem):
        out, err = asyncio.run(execute_tool(
            "mempalace_add",
            {"wing": "wing_code", "room": "proj", "content": "aprendi X",
             "agent_name": "hermes", "confidence": 0.85},
            allowed_tools=["mempalace_add"],
        ))
    assert err is False
    assert "agent_name" in captured["cmd"]
    assert "hermes" in captured["cmd"]
    assert "timestamp" in captured["cmd"]
    assert "confidence" in captured["cmd"]
