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

app = FastAPI(title="Jarvas API", version="0.3.0", lifespan=lifespan)
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
    return {"status": "ok", "version": "0.1.0"}


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


@app.post("/chat")
async def chat(req: ChatRequest):
    """Chat principal com roteamento automático de modelos."""
    import asyncio as _asyncio
    from jarvas.hermes_client import chat as hermes_chat
    from jarvas.router import detect_task_type

    tipo = detect_task_type(req.mensagem)
    resposta, modelo = hermes_chat(
        req.mensagem,
        historico=req.historico or None,
        modelo=req.modelo or None,
    )

    # Mineração em background após cada turno (≥4 msgs acumuladas)
    historico_atualizado = (req.historico or []) + [
        {"role": "user", "content": req.mensagem},
        {"role": "assistant", "content": resposta},
    ]
    if len(historico_atualizado) >= 4:
        from jarvas.miners.conversation_miner import mine
        _asyncio.create_task(_asyncio.to_thread(mine, historico_atualizado))

    return {
        "resposta": resposta,
        "modelo": modelo,
        "tipo": tipo,
    }


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
