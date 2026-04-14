# jarvas/managed/sse.py

import asyncio
import json
from typing import AsyncIterator


def format_sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def event_generator(session_id: str, queue: asyncio.Queue) -> AsyncIterator[str]:
    """
    Gera eventos SSE para stream em andamento.
    Heartbeat a cada 30s para manter conexão viva.
    Encerra no evento session.status_idle ou session.error, ou após 300s de idle.
    """
    HEARTBEAT_INTERVAL = 30
    MAX_IDLE = 300

    idle_accumulated = 0
    while idle_accumulated < MAX_IDLE:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)
            idle_accumulated = 0
            yield format_sse(event)
            if event.get("type") in ("session.status_idle", "session.error"):
                break
        except asyncio.TimeoutError:
            idle_accumulated += HEARTBEAT_INTERVAL
            yield ": heartbeat\n\n"


async def replay_generator(events: list[dict]) -> AsyncIterator[str]:
    """
    Usado quando cliente conecta APÓS session.status_idle.
    Repassa todos os eventos gravados e encerra.
    """
    for event in events:
        yield format_sse(event)
