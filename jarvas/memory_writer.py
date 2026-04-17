"""Extrai insights do historico e grava no MemPalace + Supabase."""
from __future__ import annotations
import json
from pathlib import Path

from jarvas.hermes_client import chat as hermes_chat
from jarvas.mempalace_client import handle_hmem
from jarvas.supabase_client import save_memory_log
from jarvas.context import SessionContext


def extract_insights_from_history(session_history: list[dict]) -> dict:
    """
    Extrai insights reais do histórico da sessão atual.
    session_history = lista de {"role": "user"|"assistant", "content": "..."}
    """
    empty = {"acertos": [], "erros": [], "decisoes": [], "padroes": []}

    if not session_history or len(session_history) < 2:
        return empty

    historico_texto = "\n".join([
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in session_history[-10:]  # últimas 10 mensagens
    ])

    prompt = f"""Analise este histórico de conversa e extraia insights estruturados.

HISTÓRICO:
{historico_texto}

Retorne SOMENTE um JSON válido neste formato, sem explicações:
{{
  "acertos": ["o que funcionou bem nesta sessão"],
  "erros": ["problemas encontrados e como foram resolvidos"],
  "decisoes": ["decisões técnicas tomadas"],
  "padroes": ["padrões de uso ou preferências identificadas"]
}}

Se não houver informação suficiente para uma categoria, deixe a lista vazia.
Seja específico e objetivo. Não invente informações que não estão no histórico."""

    from jarvas.model_registry import resolve_with_fallback
    model = resolve_with_fallback("gemini")  # rápido e barato para extração

    try:
        resp, _ = hermes_chat(prompt, modelo=model)
        # Limpar possível markdown
        resp = resp.strip()
        if resp.startswith("```"):
            resp = resp.split("```")[1]
            if resp.startswith("json"):
                resp = resp[4:]
        return json.loads(resp.strip())
    except Exception as e:
        print(f"[warn] Falha ao extrair insights: {e}")
        return empty


def store(session_ctx: SessionContext, scope: int = 5) -> str:
    """Analisa historico recente e grava insights no MemPalace."""
    msgs = session_ctx.historico[-scope:]
    dados = extract_insights_from_history(msgs)

    # Enriquecer com resultados de pipeline/debate se existirem
    if session_ctx.last_pipeline_result:
        sintese = session_ctx.last_pipeline_result.get("sintese", "")[:500]
        if sintese:
            dados.setdefault("decisoes", []).append(f"[pipeline] {sintese}")
    if session_ctx.last_debate_result:
        consenso = session_ctx.last_debate_result.get("consensus", "")[:500]
        if consenso:
            dados.setdefault("padroes", []).append(f"[debate] {consenso}")

    wing = "wing_code" if session_ctx.project_path else "wing_user"
    if session_ctx.project_path:
        room = Path(session_ctx.project_path).name.lower().replace(" ", "-")
    else:
        room = "general"

    content = json.dumps(dados, ensure_ascii=False)
    result = handle_hmem(f"add {wing} {room} {content}")

    drawer_id = None
    try:
        r = json.loads(result.split("\n", 1)[-1])
        drawer_id = r.get("id")
    except Exception:
        pass

    save_memory_log(session_ctx.session_id, wing, room, content, drawer_id)
    return result
