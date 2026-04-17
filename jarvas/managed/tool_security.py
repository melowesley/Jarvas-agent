"""Helpers de segurança e tipagem para o registry unificado de tools (v0.5.0).

Reúne em um único lugar:
- Regex de detecção de credenciais (reusa o padrão de `guard_deepseek`)
- Mascaramento de segredos em conteúdo lido
- `tool_call_id` determinístico (hash) para idempotência de retries
- Validação de path dentro do workspace (anti path traversal)
- Schemas Pydantic de input/output ricos (message/details/artifacts)

Ver `docs/PLANO-v0.5.0-MULTIAGENTE.md` §7 — hardening.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

_SENSITIVE_RE = re.compile(
    r'(api[_-]?key|token|secret|password|bearer|sk-|AIza)\s*[=:]\s*\S+',
    re.IGNORECASE,
)


def contains_secret(text: str) -> bool:
    return bool(_SENSITIVE_RE.search(text or ""))


def redact_secrets(text: str) -> str:
    """Mascara valores de credenciais detectadas, preservando a chave."""
    if not text:
        return text
    return _SENSITIVE_RE.sub(lambda m: f"{m.group(0).split('=')[0].split(':')[0]}=***", text)


def compute_tool_call_id(session_id: str, turn: int, name: str, input_dict: dict) -> str:
    """Hash determinístico da chamada — retries com mesmo (session, turn, name, input) = mesmo id."""
    payload = json.dumps(
        {"s": session_id, "t": turn, "n": name, "i": input_dict},
        sort_keys=True,
        ensure_ascii=False,
    )
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"call_{h}"


def is_within(path: str, workspace: str | None) -> bool:
    """True se `path` resolvido estiver dentro de `workspace` (se fornecido)."""
    if not workspace:
        return True
    try:
        wp = Path(workspace).resolve()
        pp = Path(path).resolve()
        return str(pp).startswith(str(wp))
    except Exception:
        return False


# ── Schemas Pydantic ──────────────────────────────────────────────

class ToolOutput(BaseModel):
    """Saída rica padronizada para tools. Compatível com o retorno (str, bool)
    antigo via `.to_legacy()`."""
    message: str
    details: dict = Field(default_factory=dict)
    artifacts: list[dict] = Field(default_factory=list)
    is_error: bool = False

    def to_legacy(self) -> tuple[str, bool]:
        return self.message, self.is_error
