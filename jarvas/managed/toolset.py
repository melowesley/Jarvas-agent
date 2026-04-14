# jarvas/managed/toolset.py

import asyncio
import aiofiles
from typing import Tuple

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
}


async def execute_tool(name: str, input_dict: dict, allowed_tools: list[str]) -> Tuple[str, bool]:
    if name not in allowed_tools or name not in TOOLS:
        return f"Tool '{name}' not allowed or not found", True

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
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                content = await f.read()
            if len(content) > 50 * 1024:
                content = content[: 50 * 1024] + "\n... (truncated at 50KB)"
            return content, False

        elif name == "web_search":
            query = input_dict.get("query", "")
            from jarvas.guard_gemini import web_search
            result = await asyncio.to_thread(web_search, query)
            return str(result), False

    except asyncio.TimeoutError:
        return f"Tool '{name}' timed out", True
    except Exception as e:
        return str(e), True

    return f"Unknown tool '{name}'", True
