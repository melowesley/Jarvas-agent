"""SmartPublisher — event-driven publishing layer for Moltbook.

Use this when you have a specific, known advance to publish (not mined from MemPalace).
For autonomous mining-based publication, use MoltbookAgent.autonomous_tick() instead.
"""
from __future__ import annotations

import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum

log = logging.getLogger("jarvas.moltbook.publisher")


class EventKind(Enum):
    RELEASE = "release"
    MILESTONE = "milestone"
    CRITICAL_FIX = "critical_fix"
    DISCOVERY = "discovery"
    IMPROVEMENT = "improvement"
    LESSON = "lesson"


@dataclass
class PublishEvent:
    id: str
    kind: str
    title: str
    content: str
    impact_score: int = 5  # 0-10
    improvement_pct: int = 0  # 0-100%
    relates_to: List[str] = None
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if self.relates_to is None:
            self.relates_to = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SmartPublisher:
    """In-memory event-driven publisher. Tracks cooldown, deduplication, and audit log."""

    def __init__(self, cooldown_hours: int = 2):
        self.cooldown_delta = timedelta(hours=cooldown_hours)
        self.last_publish_time: Optional[datetime] = None
        self.published_events: set = set()
        self.queued_events: List[PublishEvent] = []
        self.log_events: List[Dict[str, Any]] = []

    def _log_action(self, event_id: str, action: str, decision: str, reason: str = "", extra: Dict = None) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_id": event_id,
            "action": action,
            "decision": decision,
            "reason": reason,
        }
        if extra:
            entry.update(extra)
        self.log_events.append(entry)
        log.info("[JARVAS] %s | %s → %s (%s)", event_id[:8], action, decision, reason)

    def is_relevant(self, event: PublishEvent) -> bool:
        if event.kind in [EventKind.RELEASE.value, EventKind.MILESTONE.value,
                          EventKind.CRITICAL_FIX.value, EventKind.DISCOVERY.value]:
            return True
        if event.impact_score >= 8:
            return True
        if event.improvement_pct >= 20:
            return True
        if event.impact_score >= 6 and event.improvement_pct >= 10:
            return True
        return False

    def is_duplicate(self, event: PublishEvent) -> bool:
        return event.id in self.published_events

    def in_cooldown(self) -> bool:
        if self.last_publish_time is None:
            return False
        return datetime.now(timezone.utc) - self.last_publish_time < self.cooldown_delta

    def next_publish_window(self) -> str:
        if self.last_publish_time is None:
            return "now"
        return (self.last_publish_time + self.cooldown_delta).isoformat()

    def evaluate(self, event: PublishEvent) -> Dict[str, Any]:
        if not self.is_relevant(event):
            self._log_action(event.id, "evaluate", "QUEUE_DIGEST",
                             f"Baixa relevância (score={event.impact_score}, melhoria={event.improvement_pct}%)")
            return {"decision": "QUEUE_DIGEST", "reason": "low_relevance", "will_publish": False}

        if self.is_duplicate(event):
            self._log_action(event.id, "evaluate", "IGNORE", "Evento já foi publicado")
            return {"decision": "IGNORE", "reason": "duplicate", "will_publish": False}

        if self.in_cooldown():
            window = self.next_publish_window()
            self._log_action(event.id, "evaluate", "QUEUE_DIGEST", f"Cooldown ativo até {window}")
            return {"decision": "QUEUE_DIGEST", "reason": "cooldown", "will_publish": False, "next_window": window}

        self._log_action(event.id, "evaluate", "PUBLISH_NOW",
                         f"Score={event.impact_score}, Melhoria={event.improvement_pct}%, Tipo={event.kind}")
        return {"decision": "PUBLISH_NOW", "reason": "relevant_and_timely", "will_publish": True}

    def publish_if_relevant(self, event: PublishEvent) -> Dict[str, Any]:
        evaluation = self.evaluate(event)

        if not evaluation["will_publish"]:
            self.queued_events.append(event)
            return {"status": "queued", "evaluation": evaluation, "event_id": event.id}

        result = self._publish_to_moltbook(event)

        if result.get("success"):
            self.published_events.add(event.id)
            self.last_publish_time = datetime.now(timezone.utc)
            self._log_action(event.id, "publish", "SUCCESS", f"Post criado (id={result.get('post_id')})")

        return {
            "status": "published" if result.get("success") else "failed",
            "evaluation": evaluation,
            "event_id": event.id,
            "post_id": result.get("post_id"),
            "error": result.get("error"),
        }

    def _publish_to_moltbook(self, event: PublishEvent) -> Dict[str, Any]:
        """Posts event directly to Moltbook via MoltbookAgent HTTP helpers."""
        try:
            from jarvas.agents.adapters.moltbook import AGENT

            content = (
                f"📌 {event.title}\n\n"
                f"{event.content}\n\n"
                f"#{event.kind} #Jarvas"
            )
            response = AGENT._post_http("/posts", {
                "submolt_name": __import__("os").getenv("MOLTBOOK_SUBMOLT", "general"),
                "title": event.title[:100],
                "content": content,
            })
            post_id = response.get("id") or response.get("post_id", f"mlt_{event.id}")
            return {"success": True, "post_id": post_id}

        except Exception as e:
            log.error("[JARVAS] Erro ao publicar no Moltbook: %s", e)
            self._log_action(event.id, "publish", "ERROR", str(e))
            return {"success": False, "error": str(e)}

    def get_queue(self) -> List[PublishEvent]:
        return self.queued_events.copy()

    def publish_digest(self) -> Optional[Dict[str, Any]]:
        if not self.queued_events:
            return None

        content = "Essa semana:\n\n" + "".join(
            f"• {e.title} (+{e.improvement_pct}%)\n" for e in self.queued_events
        )
        digest = PublishEvent(
            id=f"digest_{datetime.now(timezone.utc).timestamp()}",
            kind=EventKind.LESSON.value,
            title="📋 Resumo de avanços",
            content=content,
            impact_score=6,
        )
        count = len(self.queued_events)
        result = self._publish_to_moltbook(digest)
        self.queued_events.clear()
        self._log_action(digest.id, "publish_digest",
                         "SUCCESS" if result.get("success") else "ERROR",
                         f"{count} eventos inclusos")
        return {
            "status": "published" if result.get("success") else "failed",
            "event_count": count,
            "post_id": result.get("post_id"),
        }

    def get_audit_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.log_events[-limit:]

    def reset(self) -> None:
        self.last_publish_time = None
        self.published_events.clear()
        self.queued_events.clear()
        self.log_events.clear()

    def status(self) -> Dict[str, Any]:
        return {
            "published_count": len(self.published_events),
            "queued_count": len(self.queued_events),
            "last_publish": self.last_publish_time.isoformat() if self.last_publish_time else None,
            "in_cooldown": self.in_cooldown(),
            "next_window": self.next_publish_window(),
            "log_size": len(self.log_events),
        }


_publisher_instance: Optional[SmartPublisher] = None


def get_publisher() -> SmartPublisher:
    global _publisher_instance
    if _publisher_instance is None:
        _publisher_instance = SmartPublisher(cooldown_hours=2)
    return _publisher_instance
