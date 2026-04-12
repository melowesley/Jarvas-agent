# jarvas/supabase_client.py
"""Operações de leitura e escrita no Supabase para persistência do Jarvas."""

import os
from functools import lru_cache
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


@lru_cache(maxsize=1)
def _get_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL e SUPABASE_KEY devem estar definidos no .env")
    return create_client(url, key)


def save_message(
    session_id: str,
    role: str,
    content: str,
    model: str | None = None,
    task_type: str | None = None,
) -> None:
    """Persiste uma troca de conversa no Supabase."""
    _get_client().table("conversations").insert({
        "session_id": session_id,
        "role": role,
        "content": content,
        "model": model,
        "task_type": task_type,
    }).execute()


def load_history(session_id: str, limit: int = 20) -> list[dict]:
    """Carrega o histórico recente de uma sessão."""
    result = (
        _get_client()
        .table("conversations")
        .select("role, content")
        .eq("session_id", session_id)
        .order("created_at")
        .limit(limit)
        .execute()
    )
    return result.data or []


def save_guard_log(guard: str, input_text: str, output_text: str) -> None:
    """Persiste uma interação com o guarda."""
    _get_client().table("guard_logs").insert({
        "guard": guard,
        "input": input_text,
        "output": output_text,
    }).execute()


def save_debate_log(topic: str, rounds: list[dict], consensus: str) -> None:
    """Persiste a transcrição de um debate."""
    _get_client().table("debate_logs").insert({
        "topic": topic,
        "rounds": rounds,
        "consensus": consensus,
    }).execute()


def load_session_by_time(data_str: str, hora_str: str) -> list[dict]:
    """Carrega o contexto de sessão mais próximo da data+hora informada.

    Exemplos: data_str='ontem', hora_str='15h'
    """
    from datetime import datetime, timedelta

    agora = datetime.now()
    if data_str.lower() == "ontem":
        base = agora - timedelta(days=1)
    elif data_str.lower() == "hoje":
        base = agora
    else:
        try:
            base = datetime.strptime(data_str, "%Y-%m-%d")
        except ValueError:
            base = agora - timedelta(days=1)

    hora = int(hora_str.replace("h", "").replace(":", "").zfill(4)[:2])
    alvo = base.replace(hour=hora, minute=0, second=0, microsecond=0)
    alvo_iso = alvo.isoformat()

    result = (
        _get_client()
        .table("session_contexts")
        .select("history")
        .lte("created_at", alvo_iso)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]["history"]
    return []
