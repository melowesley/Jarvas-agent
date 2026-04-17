"""Entry point do Jarvas v0.5.0 — Supervisor + Handlers.

`process()` tenta rotear via Supervisor multi-agente (`jarvas.agents.supervisor.route`).
Se o Supervisor não estiver disponível ou em modo fallback, usa os handlers
individuais implementados abaixo. Os handlers preservam funcionalidades de:
- Pronoun resolution
- Intent classification
- File operations
- Web search, debates, pipeline, etc.
"""
from __future__ import annotations
import os
import re

from jarvas.context import SessionContext
from jarvas.intent_parser import parse


def process(mensagem: str, session_ctx: SessionContext) -> str:
    """Classifica a mensagem e executa o agent correto via Supervisor (com fallback)."""
    try:
        # Tenta rota via Supervisor primeiro (v0.5.0 final)
        from jarvas.agents import supervisor
        intent = parse(mensagem, session_ctx.project_path)
        return supervisor.route(intent, session_ctx)
    except (ImportError, AttributeError, Exception) as e:
        # Fallback para handlers individuais se Supervisor não estiver disponível
        return _process_with_handlers(mensagem, session_ctx)


def _process_with_handlers(mensagem: str, session_ctx: SessionContext) -> str:
    """Fallback: despacha Intents para handlers individuais (preserva suas funções)."""
    from jarvas.intent_classifier import classify
    from jarvas.session import get_session

    session = get_session()
    mensagem = _resolve_pronouns(mensagem, session)
    intent_type, params = classify(mensagem)

    if intent_type == "LIST_FILES":
        from jarvas.intents.list_files import handle_list_files
        return handle_list_files()

    if intent_type == "RESUME_SESSION":
        return _handle_resume_session(params.get("description", mensagem), session_ctx)

    if intent_type == "SLASH_COMMAND":
        from jarvas.commands import dispatch
        cmd_str = params["command"]
        if params["args"]:
            cmd_str += " " + params["args"]
        return dispatch(cmd_str, session_ctx.historico) or ""

    if intent_type == "SET_PROJECT":
        return handle_set_project(params["path"], session_ctx)

    if intent_type == "STORE_MEMORY":
        return _handle_store_memory(session_ctx)

    if intent_type == "DEBATE":
        return _handle_debate(params.get("topic", mensagem), session_ctx)

    if intent_type == "SEARCH_WEB":
        return _handle_search_web(params.get("query", mensagem))

    if intent_type in ("ATTACH", "OCR"):
        filename = params.get("filename", "")
        return _handle_file_process(filename, mensagem, session_ctx)

    if intent_type == "FILE_EDIT":
        filename = params.get("filename", "")
        result = _handle_file_edit(filename, mensagem, session_ctx)
        if not result.startswith("[erro]"):
            session.last_file_edited = filename
        return result

    if intent_type == "FILE_READ":
        filename = params.get("filename", "")
        result = _handle_file_read(filename, session_ctx)
        if not result.startswith("[erro]"):
            session.last_file_read = filename
        return result

    if intent_type == "PIPELINE":
        return _handle_pipeline(mensagem, session_ctx)

    # CHAT — fallback (também cobre SLASH_COMMAND que escapar)
    return _handle_chat(mensagem, session_ctx)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

_PRONOME_RE = re.compile(
    r'\b(nele|nela|ele|ela|isso|esse arquivo|aquela pasta|aquele diret|ambos arquivos é possivél?|aquele arquivo|o mesmo|a mesma|se fosse possível me explicar, como funcionaria?|esse mesmo)\b',
    re.IGNORECASE,
)


def _resolve_pronouns(mensagem: str, session) -> str:
    """Substitui pronomes pelo último arquivo lido/editado."""
    if not _PRONOME_RE.search(mensagem):
        return mensagem
    last = session.last_file_read or session.last_file_edited
    if not last:
        return mensagem
    return _PRONOME_RE.sub(os.path.basename(last), mensagem)


def _find_implicit_file_content(mensagem: str, session) -> str | None:
    """Lê conteúdo do arquivo do projeto implicitamente mencionado na mensagem."""
    if not session.has_project():
        return None
    from pathlib import Path
    words = set(re.findall(r'\b\w{4,}\b', mensagem.lower()))
    for f in os.listdir(session.project_path):
        stem = Path(f).stem.lower()
        if stem in words or any(w in stem for w in words if len(w) >= 4):
            full = os.path.join(session.project_path, f)
            try:
                return open(full, encoding="utf-8").read()
            except Exception:
                return None
    return None


# ─────────────────────────────────────────────────────────────────────────────
# HANDLERS (suas funções implementadas)
# ─────────────────────────────────────────────────────────────────────────────

def _handle_chat(mensagem: str, ctx) -> str:
    from jarvas.hermes_client import chat as hermes_chat, build_system_prompt
    from jarvas.supabase_client import save_message
    from jarvas.router import detect_task_type
    from jarvas.session import get_session

    session = get_session()
    sistema = build_system_prompt()
    file_content = _find_implicit_file_content(mensagem, session)
    if file_content:
        sistema += f"\n\nCONTEÚDO DO ARQUIVO (para contexto):\n```\n{file_content[:3000]}\n```"

    resposta, modelo = hermes_chat(mensagem, historico=ctx.historico, system_prompt=sistema)
    ctx.historico.append({"role": "user", "content": mensagem})
    ctx.historico.append({"role": "assistant", "content": resposta})
    try:
        tipo = detect_task_type(mensagem)
        save_message(ctx.session_id, "user", mensagem, task_type=tipo)
        save_message(ctx.session_id, "assistant", resposta, model=modelo, task_type=tipo)
    except Exception:
        pass
    return resposta


def _handle_pipeline(mensagem: str, ctx) -> str:
    from jarvas.guard_pipeline import run
    from jarvas.router import detect_task_type

    task_type = detect_task_type(mensagem)
    if task_type == "chat":
        task_type = "analysis"

    result = run(mensagem, task_type, ctx)
    ctx.last_pipeline_result = result
    ctx.historico.append({"role": "user", "content": mensagem})
    ctx.historico.append({"role": "assistant", "content": result["sintese"]})
    return result["sintese"]


def _handle_debate(topic: str, ctx) -> str:
    from jarvas.debate import run_debate, format_debate_result

    resultado = run_debate(topic)
    ctx.last_debate_result = resultado
    ctx.historico.append({"role": "user", "content": topic})
    ctx.historico.append({"role": "assistant", "content": resultado["consensus"]})
    return format_debate_result(resultado)


def _handle_file_read(filename: str, ctx) -> str:
    from jarvas.file_editor import read_file
    from jarvas.session import get_session

    session = get_session()
    resolved = session.find_file(filename) if session.has_project() else None
    path = resolved or filename

    content = read_file(path, ctx.project_path)
    display_name = os.path.basename(path)
    return f"**Arquivo:** `{display_name}`\n\n```\n{content.strip()}\n```"


def _handle_file_edit(filename: str, instruction: str, ctx) -> str:
    from jarvas.file_editor import edit_file
    from jarvas.session import get_session

    session = get_session()
    resolved = session.find_file(filename) if session.has_project() else None
    path = resolved or filename

    if not path:
        return "[erro] Não encontrei o nome do arquivo na mensagem."

    result = edit_file(path, instruction, ctx.project_path, ctx.session_id)
    if "error" in result:
        return f"[erro] {result['error']}"

    display_name = os.path.basename(result["path"])
    return f"**Arquivo editado:** `{display_name}`\n\n```diff\n{result['diff']}\n```"


def handle_set_project(path: str, ctx) -> str:
    path = os.path.normpath(path.strip())

    if os.path.isfile(path):
        return (
            f"[erro] '{path}' é um arquivo, não uma pasta.\n"
            f"         Use o caminho da pasta do projeto, ex: #C:\\meu-projeto"
        )

    if not os.path.isdir(path):
        # Tentar variação traço ↔ underline
        alt = path.replace("-", "_") if "-" in path else path.replace("_", "-")
        if os.path.isdir(alt):
            path = alt
        else:
            return (
                f"[erro] Pasta '{path}' não encontrada.\n"
                f"         Verifique o caminho e tente novamente."
            )

    ctx.project_path = path
    from jarvas.session import get_session
    get_session().project_path = path  # sync singleton
    files = ", ".join(sorted(os.listdir(path))) or "pasta vazia"
    return f"Projeto definido: `{path}`\nArquivos encontrados: {files}"


def _handle_store_memory(ctx) -> str:
    from jarvas.memory_writer import store
    return store(ctx, scope=5)


def _handle_file_process(filename: str, instruction: str, ctx) -> str:
    from jarvas.file_processor import process_file

    result = process_file(filename, instruction, ctx.project_path, ctx.session_id)
    if "error" in result:
        return f"[erro] {result['error']}"
    return (
        f"**Arquivo processado:** `{result['output_path']}`\n\n"
        f"**Resumo:** {result['summary']}"
    )


def _handle_search_web(query: str) -> str:
    from jarvas.guard_gemini import web_search
    return web_search(query)


def _handle_resume_session(description: str, ctx) -> str:
    """Responde com base no contexto da sessão atual."""
    from jarvas.hermes_client import chat as hermes_chat
    from jarvas.session import get_session

    session = get_session()
    summary = session.context_summary()

    prompt = (
        f"O usuário quer retomar ou referir-se a algo anterior. "
        f"Contexto disponível:\n{summary}\n\n"
        f"Mensagem do usuário: {description}\n\n"
        "Responda com base no contexto. Se não houver informação suficiente, diga isso claramente ou busque outra alterna, voce é o orquestrador e isso faz de voce é o cérebro por trás de todo o sistema, voce comanda e gerencia os arquivos, analisa como está o ambiente Jarvas e detecta erros e os corrige automaticamente. Todo erro ou acerto que voce obtiver no ambiente do Jarvas,voce os enviará para o mempalace, ou delegar um agente para isso, voce é capas de perceber o que o usuário que ou pretende com cada interação. Dialogue com os agentes disponíveis no ambiente Jarvas para entrarem num consenso. Voce é mestre em desenvolvimento e aprende junto comigo. E meu nome é Wesley, seu desenvolvedor."
    )
    resposta, _ = hermes_chat(prompt, historico=ctx.historico)
    ctx.historico.append({"role": "user", "content": description})
    ctx.historico.append({"role": "assistant", "content": resposta})
    return resposta
