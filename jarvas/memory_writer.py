"""Extrai insights do historico e grava no MemPalace + Supabase."""
from __future__ import annotations
import json
from pathlib import Path

from jarvas.hermes_client import chat as hermes_chat
from jarvas.mempalace_client import handle_hmem
from jarvas.supabase_client import save_memory_log
from jarvas.context import SessionContext


def store(session_ctx: SessionContext, scope: int = 5) -> str:
    """Analisa historico recente e grava insights no MemPalace."""
    msgs = session_ctx.historico[-scope:]

    extra = ""
    if session_ctx.last_pipeline_result:
        extra += f"\nUltimo pipeline -- sintese: {session_ctx.last_pipeline_result.get('sintese', '')[:500]}"
    if session_ctx.last_debate_result:
        extra += f"\nUltimo debate -- consenso: {session_ctx.last_debate_result.get('consensus', '')[:500]}"

    prompt = (
        'Analise essas interacoes e extraia em JSON puro (sem markdown):\n'
        '{"acertos": [...], "erros": [...], "decisoes": [...], "padroes": [...]}\n\n'
        f"Interacoes:\n{json.dumps(msgs, ensure_ascii=False, indent=2)}\n{extra}"
    )

    resp, _ = hermes_chat(prompt)

    try:
        dados = json.loads(resp.strip())
    except Exception:
        dados = {"raw": resp}

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
