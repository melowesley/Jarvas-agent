"""Despacha Intents para handlers. Ponto central do Jarvas 0.4.0."""
from __future__ import annotations
import re

from jarvas.intent_parser import parse, Intent
from jarvas.context import SessionContext


def process(mensagem: str, session_ctx: SessionContext) -> str:
    """Classifica a mensagem e executa o handler correto."""
    intent = parse(mensagem, session_ctx.project_path)
    handler = _HANDLERS.get(intent.type, handle_chat)
    return handler(intent, session_ctx)


# --- Handlers ----------------------------------------------------------------

def handle_chat(intent: Intent, ctx: SessionContext) -> str:
    from jarvas.hermes_client import chat as hermes_chat
    from jarvas.supabase_client import save_message
    from jarvas.router import detect_task_type

    resposta, modelo = hermes_chat(intent.raw, historico=ctx.historico)
    ctx.historico.append({"role": "user", "content": intent.raw})
    ctx.historico.append({"role": "assistant", "content": resposta})
    try:
        tipo = detect_task_type(intent.raw)
        save_message(ctx.session_id, "user", intent.raw, task_type=tipo)
        save_message(ctx.session_id, "assistant", resposta, model=modelo, task_type=tipo)
    except Exception:
        pass
    return resposta


def handle_pipeline(intent: Intent, ctx: SessionContext) -> str:
    from jarvas.guard_pipeline import run

    result = run(intent.raw, intent.args["task_type"], ctx)
    ctx.historico.append({"role": "user", "content": intent.raw})
    ctx.historico.append({"role": "assistant", "content": result["sintese"]})
    return result["sintese"]


def handle_debate(intent: Intent, ctx: SessionContext) -> str:
    from jarvas.debate import run_debate, format_debate_result

    topic = intent.args.get("topic", intent.raw)
    resultado = run_debate(topic)
    ctx.last_debate_result = resultado
    ctx.historico.append({"role": "user", "content": intent.raw})
    ctx.historico.append({"role": "assistant", "content": resultado["consensus"]})
    return format_debate_result(resultado)


def handle_file_read(intent: Intent, ctx: SessionContext) -> str:
    from jarvas.file_editor import read_file

    m = re.search(r'[\w./\\:-]+\.\w+', intent.raw)
    path = m.group(0) if m else intent.raw
    content = read_file(path, ctx.project_path)
    return f"**Arquivo:** `{path}`\n\n```\n{content}\n```"


def handle_file_edit(intent: Intent, ctx: SessionContext) -> str:
    from jarvas.file_editor import edit_file

    m = re.search(r'[\w./\\:-]+\.\w+', intent.raw)
    path = m.group(0) if m else ""
    if not path:
        return "[erro] Nao encontrei o nome do arquivo na mensagem."
    result = edit_file(path, intent.args["instruction"], ctx.project_path, ctx.session_id)
    if "error" in result:
        return f"[erro] {result['error']}"
    return f"**Arquivo editado:** `{result['path']}`\n\n```diff\n{result['diff']}\n```"


def handle_set_project(intent: Intent, ctx: SessionContext) -> str:
    path = intent.args["path"]
    ctx.project_path = path
    return f"Projeto definido: `{path}`"


def handle_store_memory(intent: Intent, ctx: SessionContext) -> str:
    from jarvas.memory_writer import store

    scope = intent.args.get("scope", 5)
    return store(ctx, scope=scope)


def handle_file_process(intent: Intent, ctx: SessionContext) -> str:
    from jarvas.file_processor import process_file

    path = intent.args.get("path", "")
    result = process_file(path, intent.raw, ctx.project_path, ctx.session_id)
    if "error" in result:
        return f"[erro] {result['error']}"
    return (
        f"**Arquivo processado:** `{result['output_path']}`\n\n"
        f"**Resumo:** {result['summary']}"
    )


def handle_search_web(intent: Intent, ctx: SessionContext) -> str:
    from jarvas.guard_gemini import web_search

    query = intent.args.get("query", intent.raw)
    return web_search(query)


_HANDLERS = {
    "CHAT":         handle_chat,
    "PIPELINE":     handle_pipeline,
    "DEBATE":       handle_debate,
    "FILE_READ":    handle_file_read,
    "FILE_EDIT":    handle_file_edit,
    "SET_PROJECT":  handle_set_project,
    "STORE_MEMORY": handle_store_memory,
    "ATTACH":       handle_file_process,
    "OCR":          handle_file_process,
    "SEARCH_WEB":   handle_search_web,
}
