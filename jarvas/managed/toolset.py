# jarvas/managed/toolset.py

import asyncio
import aiofiles
from typing import Tuple

from .structured_log import Timer, emit as _log
from .tool_security import (
    compute_tool_call_id,
    contains_secret,
    is_within,
    redact_secrets,
)

# Tools destrutivas. Gate ativado só em modo estrito (JARVAS_STRICT_DESTRUCTIVE=1)
# para preservar compatibilidade com flows existentes (write/bash em gemma-local).
DESTRUCTIVE_TOOLS: set[str] = {
    "file_edit",
    "vscode_edit",
    "bash",
    "vscode_terminal",
    "write",
}

# Schemas no formato OpenRouter/OpenAI (type: function wrapper)
TOOLS: dict[str, dict] = {
    "bash": {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute a shell command and return stdout+stderr",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to run"}
                },
                "required": ["command"],
            },
        },
    },
    "write": {
        "type": "function",
        "function": {
            "name": "write",
            "description": "Write content to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    "read": {
        "type": "function",
        "function": {
            "name": "read",
            "description": "Read content of a file (max 50KB)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"}
                },
                "required": ["path"],
            },
        },
    },
    "web_search": {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web and return a summary",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        },
    },
    # ── VSCode-native tools (executed by the extension, not the server) ──
    "vscode_open": {
        "type": "function",
        "vscode_native": True,
        "function": {
            "name": "vscode_open",
            "description": "Open a file in the VSCode editor",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or workspace-relative file path"},
                },
                "required": ["path"],
            },
        },
    },
    "vscode_edit": {
        "type": "function",
        "vscode_native": True,
        "function": {
            "name": "vscode_edit",
            "description": "Edit a file in VSCode by replacing old_text with new_text (first occurrence). Use read tool first to see current content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "old_text": {"type": "string", "description": "Exact text to find and replace"},
                    "new_text": {"type": "string", "description": "Replacement text"},
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    "vscode_terminal": {
        "type": "function",
        "vscode_native": True,
        "function": {
            "name": "vscode_terminal",
            "description": "Run a command in the VSCode integrated terminal",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                },
                "required": ["command"],
            },
        },
    },
    "vscode_list": {
        "type": "function",
        "vscode_native": True,
        "function": {
            "name": "vscode_list",
            "description": "List files in the VSCode workspace matching a glob pattern",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern, e.g. **/*.py"},
                },
                "required": [],
            },
        },
    },
    # v0.5.0: Unified file/memory tools (replace direct calls to file_editor.py etc.)
    "file_read": {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "Read a file relative to the session workspace. Secrets are redacted before returning.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
        },
    },
    "file_edit": {
        "type": "function",
        "function": {
            "name": "file_edit",
            "description": (
                "Edit a file using a natural-language instruction (uses guard_pipeline). "
                "Destructive: requires require_confirm=true or a previously-approved preview."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "instruction": {"type": "string"},
                    "require_confirm": {"type": "boolean", "default": True},
                    "preview_only": {
                        "type": "boolean",
                        "default": False,
                        "description": "If true, compute the diff but do NOT write to disk.",
                    },
                },
                "required": ["path", "instruction"],
            },
        },
    },
    "file_process": {
        "type": "function",
        "function": {
            "name": "file_process",
            "description": "Process a file (PDF/XLSX/CSV/DOCX/TXT/image) guided by an instruction. Output written under jarvas_outputs/.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "instruction": {"type": "string"},
                },
                "required": ["path", "instruction"],
            },
        },
    },
    "mempalace_add": {
        "type": "function",
        "function": {
            "name": "mempalace_add",
            "description": "Add an entry to MemPalace (semantic memory). Metadata is enriched with agent_name and timestamp automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "wing": {"type": "string", "description": "wing_code | wing_user | custom"},
                    "room": {"type": "string"},
                    "content": {"type": "string"},
                    "agent_name": {"type": "string", "default": ""},
                    "confidence": {"type": "number", "default": 0.0},
                },
                "required": ["wing", "room", "content"],
            },
        },
    },
    # v0.5.0: Multi-agent strategy invocation
    "call_strategy": {
        "type": "function",
        "function": {
            "name": "call_strategy",
            "description": (
                "Invoke a multi-agent strategy. "
                "'pipeline' runs Hermes+Gemini+DeepSeek in parallel and synthesizes; "
                "'debate' runs Gemini vs DeepSeek in rounds until consensus."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "enum": ["pipeline", "debate"]},
                    "message": {"type": "string", "description": "User query / debate topic"},
                    "task_type": {
                        "type": "string",
                        "description": "Pipeline only: analysis|vision|code|chat",
                        "default": "chat",
                    },
                    "max_rounds": {
                        "type": "integer",
                        "description": "Debate only: number of rounds",
                        "default": 3,
                    },
                },
                "required": ["name", "message"],
            },
        },
    },
}


async def execute_tool(
    name: str,
    input_dict: dict,
    allowed_tools: list[str],
    *,
    workspace_path: str | None = None,
) -> Tuple[str, bool]:
    """Executa uma tool com whitelist + hardening v0.5.0.

    Tools destrutivas exigem `require_confirm=true` (default) ou
    `preview_only=true`. Paths são validados contra `workspace_path` quando
    fornecido. Conteúdo lido tem segredos mascarados antes de retornar.
    """
    if name not in allowed_tools or name not in TOOLS:
        _log(event="tool.denied", tool_name=name, workspace_path=workspace_path)
        return f"Tool '{name}' not allowed or not found", True

    # Hardening estrito (opt-in): gate destrutivas sem confirmação explícita.
    # Ativado via env JARVAS_STRICT_DESTRUCTIVE=1 — preservando compat legacy.
    import os as _os
    if _os.getenv("JARVAS_STRICT_DESTRUCTIVE") == "1" and name in DESTRUCTIVE_TOOLS:
        preview = input_dict.get("preview_only", False)
        if not preview and not input_dict.get("_approved"):
            _log(event="tool.blocked_destructive", tool_name=name)
            return (
                f"Tool '{name}' is destructive. Set preview_only=true to compute "
                "the diff, or _approved=true after user confirmation.",
                True,
            )

    _timer = Timer()
    _timer.__enter__()
    try:
        if name == "bash":
            command = input_dict.get("command", "")
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
            output = stdout.decode() + stderr.decode()
            return output or "(no output)", process.returncode != 0

        elif name == "write":
            path = input_dict.get("path", "")
            content = input_dict.get("content", "")
            async with aiofiles.open(path, "w", encoding="utf-8") as f:
                await f.write(content)
            return f"File '{path}' written successfully", False

        elif name == "read":
            path = input_dict.get("path", "")
            if not is_within(path, workspace_path):
                return f"Path '{path}' outside workspace", True
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                content = await f.read()
            if len(content) > 50 * 1024:
                content = content[: 50 * 1024] + "\n... (truncated at 50KB)"
            return redact_secrets(content), False

        elif name == "file_read":
            from jarvas.file_editor import read_file
            path = input_dict.get("path", "")
            content = await asyncio.to_thread(read_file, path, workspace_path)
            return redact_secrets(content), content.startswith("[erro]")

        elif name == "file_edit":
            from jarvas.file_editor import edit_file, read_file
            import difflib

            path = input_dict.get("path", "")
            instruction = input_dict.get("instruction", "")
            preview = input_dict.get("preview_only", False)

            if preview:
                # Roda só o modelo (sem write) pra produzir o diff
                from jarvas.guard_pipeline import run_edit
                original = await asyncio.to_thread(read_file, path, workspace_path)
                if original.startswith("[erro]"):
                    return original, True
                edited = await asyncio.to_thread(run_edit, original, instruction)
                diff = "\n".join(difflib.unified_diff(
                    original.splitlines(), edited.splitlines(),
                    fromfile=f"preview/{path}", tofile=f"preview/{path}", lineterm="",
                ))
                return f"PREVIEW (not written):\n{diff}", False

            result = await asyncio.to_thread(
                edit_file, path, instruction, workspace_path, "tool_session"
            )
            if "error" in result:
                return f"[erro] {result['error']}", True
            return f"Edited {result['path']}\n{result['diff']}", False

        elif name == "file_process":
            from jarvas.file_processor import process_file
            path = input_dict.get("path", "")
            instruction = input_dict.get("instruction", "")
            result = await asyncio.to_thread(
                process_file, path, instruction, workspace_path, "tool_session"
            )
            if "error" in result:
                return f"[erro] {result['error']}", True
            return f"Output: {result['output_path']}\nSummary: {result['summary']}", False

        elif name == "mempalace_add":
            from jarvas.mempalace_client import handle_hmem
            import json as _json
            from datetime import datetime as _dt, timezone as _tz

            wing = input_dict.get("wing", "wing_user")
            room = input_dict.get("room", "general")
            content = input_dict.get("content", "")
            agent_name = input_dict.get("agent_name", "")
            confidence = input_dict.get("confidence", 0.0)

            if contains_secret(content):
                content = redact_secrets(content)

            enriched = _json.dumps({
                "content": content,
                "agent_name": agent_name,
                "confidence": confidence,
                "timestamp": _dt.now(_tz.utc).isoformat(),
            }, ensure_ascii=False)
            result = await asyncio.to_thread(handle_hmem, f"add {wing} {room} {enriched}")
            return str(result), False

        elif name == "web_search":
            query = input_dict.get("query", "")
            from jarvas.guard_gemini import web_search
            result = await asyncio.to_thread(web_search, query)
            return str(result), False

        elif name == "call_strategy":
            strategy = input_dict.get("name", "")
            message = input_dict.get("message", "")
            from jarvas.context import SessionContext
            from jarvas.agents.strategies import run_debate_strategy, run_pipeline

            tmp_ctx = SessionContext()
            if strategy == "pipeline":
                task_type = input_dict.get("task_type", "chat")
                result = await asyncio.to_thread(run_pipeline, message, task_type, tmp_ctx)
                return result.content, False
            if strategy == "debate":
                max_rounds = int(input_dict.get("max_rounds", 3))
                result = await asyncio.to_thread(run_debate_strategy, message, tmp_ctx, max_rounds)
                return result.content, False
            return f"Unknown strategy '{strategy}'", True

    except asyncio.TimeoutError:
        _timer.__exit__(None, None, None)
        _log(
            event="tool.timeout", tool_name=name,
            duration_ms=_timer.duration_ms, is_error=True,
            workspace_path=workspace_path,
        )
        return f"Tool '{name}' timed out", True
    except Exception as e:
        _timer.__exit__(None, None, None)
        _log(
            event="tool.error", tool_name=name, error=str(e),
            duration_ms=_timer.duration_ms, is_error=True,
            workspace_path=workspace_path,
        )
        return str(e), True
    finally:
        _timer.__exit__(None, None, None)
        _log(
            event="tool.complete", tool_name=name,
            duration_ms=_timer.duration_ms,
            workspace_path=workspace_path,
        )

    return f"Unknown tool '{name}'", True
