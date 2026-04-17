# jarvas/managed/runtime.py

import asyncio
import json
import os
import uuid
import warnings

import httpx

with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai

from .store import (
    get_agent, get_session, get_skill, get_env,
    set_session_status, get_or_create_queue, create_session,
    reconstruct_history, enqueue,
    register_pending_tool, pop_pending_tool_result,
)
from .models import AgentRecord, SessionCreate
from .toolset import execute_tool, TOOLS

GEMINI_PREFIXES = ("gemini", "google/")
OLLAMA_PREFIXES = ("ollama/", "gemma", "llama", "mistral", "phi")
MAX_DEPTH = 3
MAX_CYCLES = 10
VSCODE_TOOL_TIMEOUT = int(os.getenv("VSCODE_TOOL_TIMEOUT", "60"))


# ── Model dispatch ───────────────────────────────────────────────────

def _is_gemini(model: str) -> bool:
    return any(model.lower().startswith(p) for p in GEMINI_PREFIXES)

def _is_ollama(model: str) -> bool:
    return any(model.lower().startswith(p) for p in OLLAMA_PREFIXES)


def _flatten_tool_args(args: dict) -> dict:
    """Normaliza argumentos de tool_call.
    Alguns modelos Ollama retornam {"path": {"type":"string","value":"x"}}
    em vez de {"path": "x"}. Esta função extrai o valor correto.
    """
    result = {}
    for k, v in args.items():
        if isinstance(v, dict) and "value" in v:
            result[k] = v["value"]
        else:
            result[k] = v
    return result


def _normalize_openrouter_response(raw: dict) -> dict:
    """Extrai content e tool_calls do formato OpenRouter/OpenAI."""
    msg = raw["choices"][0]["message"]
    tool_calls = []
    for tc in msg.get("tool_calls") or []:
        raw_input = json.loads(tc["function"]["arguments"])
        tool_calls.append({
            "id": tc["id"],
            "name": tc["function"]["name"],
            "input": _flatten_tool_args(raw_input),
        })
    return {
        "content": msg.get("content") or "",
        "tool_calls": tool_calls,
    }


async def _call_openrouter_async(model: str, messages: list, tools: list, api_key: str) -> dict:
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload: dict = {"model": model, "messages": messages, "stream": False}
    if tools:
        payload["tools"] = tools
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
    return _normalize_openrouter_response(response.json())


def _openai_messages_to_gemini(messages: list) -> tuple[str, list]:
    """Converte histórico OpenAI → system_instruction + contents Gemini."""
    system_parts = []
    contents = []
    for msg in messages:
        role = msg.get("role")
        if role == "system":
            system_parts.append(msg["content"])
        elif role == "user":
            contents.append(genai.types.ContentDict(role="user", parts=[msg["content"]]))
        elif role == "assistant":
            text = msg.get("content") or ""
            parts = [text] if text else []
            for tc in msg.get("tool_calls") or []:
                parts.append(genai.protos.Part(
                    function_call=genai.protos.FunctionCall(
                        name=tc["function"]["name"],
                        args=json.loads(tc["function"]["arguments"]),
                    )
                ))
            contents.append(genai.types.ContentDict(role="model", parts=parts))
        elif role == "tool":
            contents.append(genai.types.ContentDict(
                role="user",
                parts=[genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=msg.get("name", "tool"),
                        response={"output": msg["content"]},
                    )
                )],
            ))
    return "\n".join(system_parts), contents


def _openai_tools_to_gemini(tools: list) -> list:
    """Converte schemas OpenAI → FunctionDeclaration Gemini."""
    declarations = []
    for t in tools:
        fn = t.get("function", {})
        declarations.append(genai.protos.FunctionDeclaration(
            name=fn["name"],
            description=fn.get("description", ""),
            parameters=fn.get("parameters", {}),
        ))
    return [genai.types.Tool(function_declarations=declarations)] if declarations else []


def _call_gemini_sync(model: str, messages: list, tools: list, api_key: str) -> dict:
    genai.configure(api_key=api_key)
    model_name = model.replace("google/", "").replace("google-", "")
    system_instruction, contents = _openai_messages_to_gemini(messages)
    gemini_tools = _openai_tools_to_gemini(tools)

    kwargs: dict = {}
    if system_instruction:
        kwargs["system_instruction"] = system_instruction
    if gemini_tools:
        kwargs["tools"] = gemini_tools

    model_instance = genai.GenerativeModel(model_name=model_name, **kwargs)
    response = model_instance.generate_content(contents)

    # Normalize to internal format
    tool_calls = []
    content = ""
    for part in response.candidates[0].content.parts:
        if part.function_call.name:
            fc = part.function_call
            tool_calls.append({
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": fc.name,
                "input": dict(fc.args),
            })
        elif part.text:
            content += part.text

    return {"content": content, "tool_calls": tool_calls}


async def _call_gemini_async(model: str, messages: list, tools: list, api_key: str) -> dict:
    return await asyncio.to_thread(_call_gemini_sync, model, messages, tools, api_key)


async def _call_ollama_async(model: str, messages: list, tools: list) -> dict:
    """Chama Ollama via endpoint OpenAI-compatible (suporta tool_calls desde Ollama 0.3+).
    Se o modelo não suportar tool calling (400), retenta sem tools."""
    model_name = model.removeprefix("ollama/")
    payload: dict = {"model": model_name, "messages": messages, "stream": False}
    if tools:
        payload["tools"] = tools
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            "http://localhost:11434/v1/chat/completions",
            json=payload,
        )
        if response.status_code == 400 and tools:
            # Modelo não suporta tool calling — retenta sem tools (modo texto puro)
            payload.pop("tools")
            response = await client.post(
                "http://localhost:11434/v1/chat/completions",
                json=payload,
            )
        response.raise_for_status()
    return _normalize_openrouter_response(response.json())


async def _dispatch_model(model: str, messages: list, tools: list, agent: AgentRecord) -> dict:
    if _is_gemini(model):
        api_key = os.getenv("GEMINI_API_KEY", "")
        return await _call_gemini_async(model, messages, tools, api_key)
    elif _is_ollama(model):
        return await _call_ollama_async(model, messages, tools)
    else:
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        return await _call_openrouter_async(model, messages, tools, api_key)


# ── Tool schemas ─────────────────────────────────────────────────────

def _build_call_agent_schema(callable_agents: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": "call_agent",
            "description": "Invoca um sub-agente especializado para resolver uma tarefa",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "enum": callable_agents,
                        "description": "ID do agente a invocar",
                    },
                    "message": {
                        "type": "string",
                        "description": "Mensagem/tarefa para o sub-agente",
                    },
                },
                "required": ["agent_id", "message"],
            },
        },
    }


# ── Callable agent ───────────────────────────────────────────────────

async def invoke_callable_agent(input_dict: dict, parent_session_id: str, depth: int = 0) -> tuple[str, bool]:
    sub_agent_id = input_dict.get("agent_id", "")
    message = input_dict.get("message", "")

    if not get_agent(sub_agent_id):
        return f"[Erro: agent_id '{sub_agent_id}' não encontrado]", True

    sub_session = create_session(SessionCreate(agent_id=sub_agent_id))
    sub_queue = get_or_create_queue(sub_session.id)
    await run_agent_loop(sub_session.id, message, sub_queue, depth=depth)

    from .store import get_events
    events = get_events(sub_session.id)
    final = next((e["content"] for e in events if e.get("type") == "agent.message"), "")
    error = any(e.get("type") == "session.error" for e in events)
    return final or "[Sub-agente não retornou resposta]", error


# ── Main agent loop ──────────────────────────────────────────────────

async def run_agent_loop(
    session_id: str,
    user_message: str,
    queue: asyncio.Queue,
    depth: int = 0,
) -> None:
    if depth > MAX_DEPTH:
        await enqueue(queue, session_id, "session.error",
                      {"message": f"Max agent recursion depth ({MAX_DEPTH}) exceeded"})
        set_session_status(session_id, "error")
        return

    session = get_session(session_id)
    if not session:
        return
    agent = get_agent(session.agent_id)
    if not agent:
        return

    # Build system prompt with skills
    skill_blocks = []
    for sr in agent.skills:
        skill = get_skill(sr.skill_id)
        if skill:
            skill_blocks.append(f"## Skill: {skill.name}\n{skill.content}")
    full_system = agent.system_prompt
    if skill_blocks:
        full_system += "\n\n---\n" + "\n\n".join(skill_blocks)

    # Inject workspace path if session was created from VSCode
    if session.workspace_path:
        full_system += (
            f"\n\n---\n## VSCode Workspace\n"
            f"The user is working in the VSCode workspace at: `{session.workspace_path}`\n"
            f"Use this path as the base for all file operations (read, write, bash, vscode_edit, vscode_list)."
        )

    # Determine allowed tools from environment or agent config
    env_id = session.environment_id
    env = get_env(env_id) if env_id else None
    allowed_tools = (env.allowed_tools if env else None) or agent.tools

    # Build messages: system + history + new user message
    messages: list[dict] = []
    if full_system:
        messages.append({"role": "system", "content": full_system})
    messages.extend(reconstruct_history(session_id))
    messages.append({"role": "user", "content": user_message})

    # Persist user message
    await enqueue(queue, session_id, "user.message", {"content": user_message})

    # Build tool schemas
    tool_schemas = [TOOLS[t] for t in allowed_tools if t in TOOLS]
    if agent.callable_agents:
        tool_schemas.append(_build_call_agent_schema(agent.callable_agents))

    set_session_status(session_id, "running")

    cycles = 0
    while cycles < MAX_CYCLES:
        cycles += 1

        try:
            response = await _dispatch_model(agent.model, messages, tool_schemas, agent)
        except Exception as e:
            await enqueue(queue, session_id, "session.error", {"message": str(e)})
            set_session_status(session_id, "error")
            return

        tool_calls = response.get("tool_calls", [])

        if not tool_calls:
            content = response.get("content", "")
            await enqueue(queue, session_id, "agent.message",
                          {"content": content, "model": agent.model})
            break

        # Append assistant message with tool_calls to history
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["input"]),
                    },
                }
                for tc in tool_calls
            ],
        })

        for tc in tool_calls:
            is_vscode_tool = tc["name"].startswith("vscode_")

            await enqueue(queue, session_id, "agent.tool_use", {
                "tool_name": tc["name"],
                "tool_input": tc["input"],
                "tool_call_id": tc["id"],
                "awaiting_callback": is_vscode_tool,
            })

            if is_vscode_tool:
                # Pause loop — extensão VSCode executa a tool e chama POST /tool_result
                event = register_pending_tool(tc["id"])
                try:
                    await asyncio.wait_for(event.wait(), timeout=VSCODE_TOOL_TIMEOUT)
                    result = pop_pending_tool_result(tc["id"])
                    output, is_error = result if result else ("No result received from VSCode", True)
                except asyncio.TimeoutError:
                    pop_pending_tool_result(tc["id"])
                    output, is_error = "Timeout: VSCode extension did not respond in time", True
                    await enqueue(queue, session_id, "agent.tool_timeout", {
                        "tool_call_id": tc["id"],
                        "tool_name": tc["name"],
                    })
            elif tc["name"] == "call_agent":
                output, is_error = await invoke_callable_agent(tc["input"], session_id, depth=depth + 1)
            else:
                output, is_error = await execute_tool(tc["name"], tc["input"], allowed_tools)

            await enqueue(queue, session_id, "agent.tool_result", {
                "tool_name": tc["name"],
                "tool_call_id": tc["id"],
                "output": output,
                "is_error": is_error,
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": output,
            })
    else:
        await enqueue(queue, session_id, "session.error",
                      {"message": f"Max tool-use cycles ({MAX_CYCLES}) reached without final response"})
        set_session_status(session_id, "error")
        return

    set_session_status(session_id, "idle")
    # Mineração em background — não bloqueia a resposta ao usuário
    asyncio.create_task(_mine_session_async(session_id))
    await enqueue(queue, session_id, "session.status_idle", {})


async def _mine_session_async(session_id: str) -> None:
    """Minera padrões de progresso da sessão encerrada e salva no MemPalace."""
    try:
        from .store import get_events
        from jarvas.miners.conversation_miner import mine

        events = get_events(session_id)
        messages = [
            {
                "role": "user" if e["type"] == "user.message" else "assistant",
                "content": e.get("content", ""),
            }
            for e in events
            if e["type"] in ("user.message", "agent.message")
        ]
        if len(messages) >= 4:
            await asyncio.to_thread(mine, messages, session_id)
    except Exception:
        pass
