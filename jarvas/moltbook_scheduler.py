"""Scheduler do Moltbook Publisher — jobs periódicos de publicação e engajamento."""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


def create_moltbook_scheduler():
    """Cria e retorna um BackgroundScheduler configurado para o Moltbook.

    Jobs registrados (modo normal):
      08:00 UTC  — publish_curated:today   (manhã)
      20:00 UTC  — publish_curated:today   (noite)
      09:00 UTC  — send_heartbeat          (manhã)
      21:00 UTC  — send_heartbeat          (noite)
      dom 21:00  — publish_weekly_retro
      23:00 UTC  — ingest_engagement       (diário)
      a cada 30m — resonance_scan          (só modo social)

    Modo teste (MOLTBOOK_TEST_SCHEDULE=1):
      +30s  publish_curated
      +60s  send_heartbeat
      +90s  ingest_engagement
    """
    from apscheduler.schedulers.background import BackgroundScheduler

    mode = os.getenv("MOLTBOOK_MODE", "normal").lower()
    test_mode = os.getenv("MOLTBOOK_TEST_SCHEDULE", "0") == "1"

    scheduler = BackgroundScheduler(timezone="UTC", daemon=True)

    def _run(cmd: str) -> None:
        try:
            from jarvas.agents.registry import get_agent
            from jarvas.session import get_session
            agent = get_agent("moltbook_publisher")
            result = agent.run(cmd, get_session())
            log.info("[moltbook] %s → %s", cmd, result.content[:120])
        except Exception as exc:
            log.error("[moltbook] job '%s' falhou: %s", cmd, exc)

    if test_mode:
        from apscheduler.triggers.interval import IntervalTrigger
        scheduler.add_job(lambda: _run("publish_curated:today"), IntervalTrigger(seconds=30), id="test_publish")
        scheduler.add_job(lambda: _run("send_heartbeat"), IntervalTrigger(seconds=60), id="test_heartbeat")
        scheduler.add_job(lambda: _run("ingest_engagement"), IntervalTrigger(seconds=90), id="test_engagement")
        log.info("[moltbook] Scheduler em modo TESTE (intervalos curtos)")
        return scheduler

    from apscheduler.triggers.cron import CronTrigger

    scheduler.add_job(
        lambda: _run("publish_curated:today"),
        CronTrigger(hour=8, minute=0),
        id="publish_morning",
    )
    scheduler.add_job(
        lambda: _run("publish_curated:today"),
        CronTrigger(hour=20, minute=0),
        id="publish_evening",
    )
    scheduler.add_job(
        lambda: _run("send_heartbeat"),
        CronTrigger(hour=9, minute=0),
        id="heartbeat_morning",
    )
    scheduler.add_job(
        lambda: _run("send_heartbeat"),
        CronTrigger(hour=21, minute=0),
        id="heartbeat_evening",
    )
    scheduler.add_job(
        lambda: _run("publish_weekly_retro"),
        CronTrigger(day_of_week="sun", hour=21, minute=0),
        id="weekly_retro",
    )
    scheduler.add_job(
        lambda: _run("ingest_engagement"),
        CronTrigger(hour=23, minute=0),
        id="ingest_engagement",
    )

    if mode == "social":
        from apscheduler.triggers.interval import IntervalTrigger
        scheduler.add_job(
            lambda: _run("resonance_scan"),
            IntervalTrigger(minutes=30),
            id="resonance_scan",
        )
        log.info("[moltbook] Resonance scan ativo (modo social)")

    log.info("[moltbook] Scheduler criado com %d jobs (modo=%s)", len(scheduler.get_jobs()), mode)
    return scheduler
