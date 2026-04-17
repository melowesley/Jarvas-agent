"""Logs estruturados v0.5.0 — usados pelo runtime e pelo toolset.

JSON por linha em stderr. Campos padrão: agent_name, session_id, turn_id,
tool_name, duration_ms, is_error, workspace_path, cost_usd.

Desligável via `JARVAS_STRUCTURED_LOGS=0`.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone


def is_enabled() -> bool:
    return os.getenv("JARVAS_STRUCTURED_LOGS", "1") != "0"


def emit(**fields) -> None:
    if not is_enabled():
        return
    payload = {"ts": datetime.now(timezone.utc).isoformat(), **fields}
    try:
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr, flush=True)
    except Exception:
        pass


class Timer:
    """Context manager que mede duração em ms."""

    def __init__(self) -> None:
        self.start = 0.0
        self.duration_ms = 0

    def __enter__(self) -> "Timer":
        self.start = time.perf_counter()
        return self

    def __exit__(self, *exc) -> None:
        self.duration_ms = int((time.perf_counter() - self.start) * 1000)
