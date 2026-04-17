"""Supervisor do Jarvas v0.5.0.

Dispatcher único — substitui o dict `_HANDLERS` legado. Para cada Intent,
resolve o agent correto (ou estratégia multi-agent) e retorna a resposta
no mesmo formato textual que os handlers antigos expunham.
"""
from __future__ import annotations

import re

from jarvas.agents.base import AgentResult
from jarvas.agents.registry import get_agent
from jarvas.agents.strategies import run_debate_strategy, run_pipeline
from jarvas.context import SessionContext
from jarvas.intent_parser import Intent


def route(intent: Intent, ctx: SessionContext) -> str:
    """Dispatcher único. Retorna string igual à saída dos handlers antigos."""
    t = intent.type

    if t == "CHAT":
        return _run_chat(intent, ctx)
    if t == "PIPELINE":
        return run_pipeline(intent.raw, intent.args["task_type"], ctx).content
    if t == "DEBATE":
        topic = intent.args.get("topic", intent.raw)
        return run_debate_strategy(topic, ctx).content
    if t == "FILE_READ":
        return _run_file_agent(intent, ctx, op="read")
    if t == "FILE_EDIT":
        return _run_file_agent(intent, ctx, op="edit")
    if t in ("ATTACH", "OCR"):
        return _run_file_agent(intent, ctx, op="process")
    if t == "SET_PROJECT":
        return _run_set_project(intent, ctx)
    if t == "STORE_MEMORY":
        return get_agent("memory_miner").run(intent.raw, ctx).content
    if t == "SEARCH_WEB":
        return _run_web_search(intent, ctx)

    # Fallback: tratar como CHAT
    return _run_chat(intent, ctx)


# ── Handlers que replicam efeitos colaterais dos antigos ─────────────────

def _run_chat(intent: Intent, ctx: SessionContext) -> str:
    """Replica `handle_chat`: atualiza histórico e salva em Supabase."""
    from jarvas.router import detect_task_type
    from jarvas.supabase_client import save_message

    result: AgentResult = get_agent("hermes").run(intent.raw, ctx)
    ctx.historico.append({"role": "user", "content": intent.raw})
    ctx.historico.append({"role": "assistant", "content": result.content})
    try:
        tipo = detect_task_type(intent.raw)
        save_message(ctx.session_id, "user", intent.raw, task_type=tipo)
        save_message(
            ctx.session_id, "assistant", result.content,
            model=result.model, task_type=tipo,
        )
    except Exception:
        pass
    return result.content


def _run_file_agent(intent: Intent, ctx: SessionContext, op: str) -> str:
    """Wrapper do file_editor adapter preservando formato de saída dos handlers."""
    # Handlers antigos montavam payloads diferentes por op; o adapter já
    # detecta pelo conteúdo da mensagem. Apenas passamos a instrução adequada.
    if op == "read":
        m = re.search(r'[\w./\\:-]+\.\w+', intent.raw)
        path = m.group(0) if m else intent.raw
        from jarvas.file_editor import read_file
        content = read_file(path, ctx.project_path)
        return f"**Arquivo:** `{path}`\n\n```\n{content}\n```"
    if op == "edit":
        m = re.search(r'[\w./\\:-]+\.\w+', intent.raw)
        path = m.group(0) if m else ""
        if not path:
            return "[erro] Nao encontrei o nome do arquivo na mensagem."
        from jarvas.file_editor import edit_file
        result = edit_file(
            path,
            intent.args.get("instruction", intent.raw),
            ctx.project_path,
            ctx.session_id,
        )
        if "error" in result:
            return f"[erro] {result['error']}"
        return f"**Arquivo editado:** `{result['path']}`\n\n```diff\n{result['diff']}\n```"
    # process (ATTACH/OCR)
    from jarvas.file_processor import process_file
    path = intent.args.get("path", "")
    result = process_file(path, intent.raw, ctx.project_path, ctx.session_id)
    if "error" in result:
        return f"[erro] {result['error']}"
    return (
        f"**Arquivo processado:** `{result['output_path']}`\n\n"
        f"**Resumo:** {result['summary']}"
    )


def _run_set_project(intent: Intent, ctx: SessionContext) -> str:
    path = intent.args["path"]
    ctx.project_path = path
    return f"Projeto definido: `{path}`"


def _run_web_search(intent: Intent, ctx: SessionContext) -> str:
    """SEARCH_WEB vai direto pro web_search do Gemini (sem camada de chat)."""
    from jarvas.guard_gemini import web_search

    query = intent.args.get("query", intent.raw)
    return web_search(query)
