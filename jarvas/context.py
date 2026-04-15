"""Estado global de uma sessao do Jarvas."""
from __future__ import annotations
from dataclasses import dataclass, field
import uuid


@dataclass
class SessionContext:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_path: str | None = None
    historico: list[dict] = field(default_factory=list)
    last_pipeline_result: dict | None = None
    last_debate_result: dict | None = None
