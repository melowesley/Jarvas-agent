"""Entry point do Jarvas v0.5.0.

`process()` classifica a mensagem em Intent e delega ao Supervisor
multi-agente (`jarvas.agents.supervisor.route`). O dispatcher legado por
`_HANDLERS` foi removido na v0.5.0 final.
"""
from __future__ import annotations

from jarvas.context import SessionContext
from jarvas.intent_parser import parse


def process(mensagem: str, session_ctx: SessionContext) -> str:
    """Classifica a mensagem e executa o agent correto via Supervisor."""
    from jarvas.agents import supervisor

    intent = parse(mensagem, session_ctx.project_path)
    return supervisor.route(intent, session_ctx)
