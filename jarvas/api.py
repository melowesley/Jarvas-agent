"""API REST do Jarvas — expõe chat, guardas e debate via HTTP."""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os

from jarvas.managed.startup import seed_preset_agents
from jarvas.managed.router import managed_router
from jarvas.routes.autoescola_router import autoescola_router

@asynccontextmanager
async def lifespan(app):
    seed_preset_agents()
    yield

app = FastAPI(title="Jarvas API", version="0.5.0", lifespan=lifespan)
app.include_router(managed_router)
app.include_router(autoescola_router)

# Serve arquivos estáticos (chat UI)
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


# ─── Schemas ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    mensagem: str
    historico: list[dict] = []
    modelo: str | None = None


class GuardRequest(BaseModel):
    mensagem: str


class DebateRequest(BaseModel):
    topico: str
    rodadas: int = 3


class FileReadRequest(BaseModel):
    path: str


class FileEditRequest(BaseModel):
    path: str
    instruction: str


class MemoryRequest(BaseModel):
    scope: int = 5


class FileProcessRequest(BaseModel):
    path: str
    instruction: str


class ProjectRequest(BaseModel):
    path: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def chat_ui():
    """Serve o chat UI."""
    html_path = os.path.join(_static_dir, "chat.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return HTMLResponse("<h1>Jarvas API</h1><p>static/chat.html não encontrado.</p>")


@app.get("/autoescola", response_class=HTMLResponse)
async def autoescola_ui():
    """Serve a página da Autoescola Jarvas."""
    html_path = os.path.join(_static_dir, "autoescola.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return HTMLResponse("<h1>Autoescola Jarvas</h1><p>static/autoescola.html não encontrado.</p>")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.5.0"}


@app.get("/status")
async def status():
    """Verifica quais backends estão disponíveis."""
    import httpx
    import os

    result: dict = {}

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get("http://localhost:11434/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            result["ollama"] = {"ok": True, "models": models}
    except Exception:
        result["ollama"] = {"ok": False, "models": []}

    # Gemini
    gemini_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
    result["gemini"] = {"ok": bool(gemini_key)}

    # DeepSeek / OpenRouter
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    result["openrouter"] = {"ok": bool(openrouter_key)}

    return result


from jarvas.context import SessionContext as _SessionContext

# Sessao web compartilhada (uma por processo)
_web_ctx = _SessionContext()


@app.post("/chat")
async def chat(req: ChatRequest):
    """Chat principal -- roteado pelo orchestrator."""
    import asyncio as _asyncio
    from jarvas.orchestrator import process as orchestrator_process

    _web_ctx.historico = req.historico or []
    resposta = orchestrator_process(req.mensagem, _web_ctx)

    if len(_web_ctx.historico) >= 4:
        from jarvas.miners.conversation_miner import mine
        _asyncio.create_task(_asyncio.to_thread(mine, _web_ctx.historico))

    return {"resposta": resposta, "session_id": _web_ctx.session_id}


@app.post("/g")
async def guarda_gemini(req: GuardRequest):
    """Chat direto com o Guarda Gemini."""
    from jarvas.guard_gemini import chat as gemini_chat

    resposta = gemini_chat(req.mensagem)
    return {"resposta": resposta, "guarda": "gemini"}


@app.post("/g/web")
async def guarda_gemini_web(req: GuardRequest):
    """Busca web via Guarda Gemini."""
    from jarvas.guard_gemini import web_search

    resposta = web_search(req.mensagem)
    return {"resposta": resposta, "guarda": "gemini", "modo": "web"}


@app.post("/d")
async def guarda_deepseek(req: GuardRequest):
    """Chat direto com o Guarda DeepSeek."""
    from jarvas.guard_deepseek import chat as deepseek_chat

    resposta = deepseek_chat(req.mensagem)
    return {"resposta": resposta, "guarda": "deepseek"}


@app.post("/d/web")
async def guarda_deepseek_web(req: GuardRequest):
    """Busca web via Guarda DeepSeek."""
    from jarvas.guard_deepseek import web_search

    resposta = web_search(req.mensagem)
    return {"resposta": resposta, "guarda": "deepseek", "modo": "web"}


@app.post("/debate")
async def debate(req: DebateRequest):
    """Debate multi-agente entre Gemini e DeepSeek."""
    from jarvas.debate import run_debate

    resultado = run_debate(req.topico, max_rounds=req.rodadas)
    return resultado


@app.post("/pipeline")
async def pipeline(req: ChatRequest):
    """Guard pipeline completo: Hermes + Gemini + DeepSeek + sintese."""
    from jarvas.guard_pipeline import run
    from jarvas.router import detect_task_type
    task_type = detect_task_type(req.mensagem)
    result = run(req.mensagem, task_type, _web_ctx)
    return result


@app.post("/file/read")
async def file_read(req: FileReadRequest):
    """Le arquivo do projeto."""
    from jarvas.file_editor import read_file
    content = read_file(req.path, _web_ctx.project_path)
    return {"content": content, "path": req.path}


@app.post("/file/edit")
async def file_edit(req: FileEditRequest):
    """Edita arquivo no disco."""
    from jarvas.file_editor import edit_file
    result = edit_file(req.path, req.instruction, _web_ctx.project_path, _web_ctx.session_id)
    return result


@app.post("/memory/store")
async def memory_store(req: MemoryRequest):
    """Grava insights no MemPalace."""
    from jarvas.memory_writer import store
    result = store(_web_ctx, scope=req.scope)
    return {"result": result}


@app.post("/attach")
async def attach(req: FileProcessRequest):
    """Processa anexo guiado por instrucao."""
    from jarvas.file_processor import process_file
    result = process_file(req.path, req.instruction, _web_ctx.project_path, _web_ctx.session_id)
    return result


@app.post("/context/project")
async def set_project(req: ProjectRequest):
    """Define o projeto atual da sessao web."""
    _web_ctx.project_path = req.path
    return {"project_path": req.path}


@app.get("/context")
async def get_context():
    """Retorna estado atual da sessao web."""
    return {
        "session_id": _web_ctx.session_id,
        "project_path": _web_ctx.project_path,
        "historico_count": len(_web_ctx.historico),
    }
