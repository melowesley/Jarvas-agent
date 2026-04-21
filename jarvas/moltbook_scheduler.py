"""Scheduler do Moltbook Publisher — modo AUTÔNOMO.

Jarvas decide sozinho quando publicar, comentar ou engajar. Não há mais horários
fixos. A cada tick (default 15 min), o agente:

  1. Checa se há avanços genuínos no MemPalace para publicar
  2. Checa /home do Moltbook — notificações, DMs, atividade nos seus posts
  3. Responde comentários em seus posts (se houver)
  4. Engaja com posts do feed que tenham relação com os projetos
  5. Minera novo conhecimento absorvido de volta pro MemPalace

Se nada for relevante, fica em silêncio. Silêncio > ruído.

Variáveis de ambiente:
  MOLTBOOK_TICK_MINUTES  — intervalo entre ticks (default 15)
  MOLTBOOK_TEST_SCHEDULE — se "1", dispara um único tick em +30s
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Final
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger(__name__)

UTC: Final = ZoneInfo("UTC")


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "1" if default else "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _safe_preview(result: object, limit: int = 160) -> str:
    content = getattr(result, "content", result)
    text = "<sem conteúdo>" if content is None else str(content)
    return text if len(text) <= limit else f"{text[:limit]}..."


def run_moltbook_command(cmd: str) -> None:
    """Executa um comando do agente do Moltbook com logging resiliente."""
    try:
        from jarvas.agents.registry import get_agent
        from jarvas.session import get_session

        agent = get_agent("moltbook_publisher")
        result = agent.run(cmd, get_session())
        log.info("[moltbook] %s -> %s", cmd, _safe_preview(result))
    except Exception:
        log.exception("[moltbook] job %r falhou", cmd)


def create_moltbook_scheduler() -> "BackgroundScheduler":
    """Cria scheduler em modo autônomo.

    Apenas UM job periódico: `autonomous_tick`. Jarvas decide o que fazer
    dentro do tick — publicar, engajar, minerar ou ficar em silêncio.
    """
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    test_mode = _env_flag("MOLTBOOK_TEST_SCHEDULE")
    tick_minutes = int(os.getenv("MOLTBOOK_TICK_MINUTES", "15"))

    scheduler = BackgroundScheduler(
        timezone=UTC,
        daemon=True,
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300},
    )

    if test_mode:
        scheduler.add_job(
            run_moltbook_command,
            trigger=DateTrigger(run_date=datetime.now(UTC) + timedelta(seconds=30)),
            id="test_autonomous_tick",
            args=["autonomous_tick"],
            replace_existing=True,
        )
        log.info("[moltbook] Scheduler em modo TESTE — tick único em +30s")
        return scheduler

    scheduler.add_job(
        run_moltbook_command,
        trigger=IntervalTrigger(minutes=tick_minutes, timezone=UTC),
        id="autonomous_tick",
        args=["autonomous_tick"],
        replace_existing=True,
    )
    log.info("[moltbook] Scheduler autônomo: tick a cada %d min", tick_minutes)
    return scheduler
