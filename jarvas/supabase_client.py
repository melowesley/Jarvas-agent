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
    """Persiste uma interação com o guarda (falha silenciosamente se RLS bloquear)."""
    try:
        _get_client().table("guard_logs").insert({
            "guard": guard,
            "input": input_text,
            "output": output_text,
        }).execute()
    except Exception as e:
        print(f"[warn] guard_log não salvo ({guard}): {e}")


def save_debate_log(topic: str, rounds: list[dict], consensus: str) -> None:
    """Persiste a transcrição de um debate (falha silenciosamente se RLS bloquear)."""
    try:
        _get_client().table("debate_logs").insert({
            "topic": topic,
            "rounds": rounds,
            "consensus": consensus,
        }).execute()
    except Exception as e:
        print(f"[warn] debate_log não salvo: {e}")


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


def save_pipeline_result(
    session_id: str,
    user_message: str,
    task_type: str,
    results: dict,
) -> None:
    """Persiste resultado completo do guard pipeline."""
    try:
        _get_client().table("pipeline_results").insert({
            "session_id": session_id,
            "user_message": user_message,
            "task_type": task_type,
            "hermes": results.get("hermes"),
            "gemini": results.get("gemini"),
            "deepseek": results.get("deepseek"),
            "sintese": results.get("sintese"),
        }).execute()
    except Exception as e:
        print(f"[warn] pipeline_result nao salvo: {e}")


def save_file_edit(
    session_id: str,
    file_path: str,
    instruction: str,
    original: str,
    edited: str,
    diff: str,
) -> None:
    """Persiste uma edicao de arquivo."""
    try:
        _get_client().table("file_edits").insert({
            "session_id": session_id,
            "file_path": file_path,
            "instruction": instruction,
            "original_content": original,
            "edited_content": edited,
            "diff": diff,
        }).execute()
    except Exception as e:
        print(f"[warn] file_edit nao salvo: {e}")


def save_attachment(
    session_id: str,
    file_name: str,
    file_type: str,
    extracted_content: str,
    analysis: str,
) -> None:
    """Persiste um anexo processado."""
    try:
        _get_client().table("attachments").insert({
            "session_id": session_id,
            "file_name": file_name,
            "file_type": file_type,
            "extracted_content": extracted_content,
            "analysis": analysis,
        }).execute()
    except Exception as e:
        print(f"[warn] attachment nao salvo: {e}")


def save_memory_log(
    session_id: str,
    wing: str,
    room: str,
    content: str,
    drawer_id: str | None,
) -> None:
    """Persiste um registro de memoria gravada no MemPalace."""
    try:
        _get_client().table("memory_logs").insert({
            "session_id": session_id,
            "wing": wing,
            "room": room,
            "content": content,
            "drawer_id": drawer_id,
        }).execute()
    except Exception as e:
        print(f"[warn] memory_log nao salvo: {e}")
