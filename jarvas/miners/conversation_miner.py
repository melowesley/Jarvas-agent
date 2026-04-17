"""Orquestra mineração de conversas — Gemini para diálogo, DeepSeek para código."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

_CODE_RE = re.compile(r'```[\w]*\n.*?```', re.DOTALL)


def mine(messages: list[dict], session_id: str = "") -> None:
    """
    Filtra, minera e salva no MemPalace. Chamado em background thread.
    Ignora sessões com menos de 4 mensagens.
    """
    if len(messages) < 4:
        return

    from jarvas.guard_gemini import mine_conversation
    from jarvas.mempalace_client import handle_hmem

    ts = datetime.now(timezone.utc).isoformat()
    label = f"sid={session_id[:8]} ts={ts}"

    # Gemini minera o diálogo
    try:
        result = mine_conversation(messages)
        if result:
            meta = _enriched_meta(
                session_id, ts, result.get("confidence", 0),
                agent_name="gemini_analyst",
                payload=result,
            )
            payload = {**result, **meta}
            handle_hmem(
                f"add jarvas learnings {label}: {json.dumps(payload, ensure_ascii=False)}"
            )
    except Exception:
        pass

    # DeepSeek minera código (quando presente)
    has_code = any(_CODE_RE.search(m.get("content", "")) for m in messages)
    if has_code:
        try:
            from jarvas.guard_deepseek import mine_code

            code_result = mine_code(messages)
            if code_result:
                meta = _enriched_meta(
                    session_id, ts, code_result.get("confidence", 0),
                    agent_name="deepseek_coder",
                    payload=code_result,
                )
                payload = {**code_result, **meta}
                handle_hmem(
                    f"add jarvas code {label}: {json.dumps(payload, ensure_ascii=False)}"
                )
        except Exception:
            pass


def _enriched_meta(
    session_id: str,
    ts: str,
    confidence: float,
    *,
    agent_name: str,
    payload: dict,
) -> dict:
    """v0.5.0: metadata rica pro MemPalace.

    Adiciona `agent_name`, `delegation_path` e `hash_conteudo` (dedupe)
    ao lado de `session_id`, `timestamp`, `confidence`.
    """
    import hashlib
    content_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "session_id": session_id,
        "timestamp": ts,
        "confidence": confidence,
        "agent_name": agent_name,
        "delegation_path": [agent_name],
        "hash_conteudo": content_hash,
    }
