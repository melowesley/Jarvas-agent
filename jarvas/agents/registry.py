"""Registry único de agents do Jarvas v0.5.0.

Lookup por `name`. Lazy-load dos adapters default pra evitar import cíclico
e pra não exigir API keys só por importar o pacote.
"""
from __future__ import annotations

from typing import Callable

from jarvas.agents.base import AgentProtocol

_REGISTRY: dict[str, AgentProtocol] = {}
_DEFAULTS_LOADED = False


def register(agent: AgentProtocol) -> None:
    _REGISTRY[agent.name] = agent


def _ensure_defaults() -> None:
    global _DEFAULTS_LOADED
    if _DEFAULTS_LOADED:
        return
    _DEFAULTS_LOADED = True

    from jarvas.agents.adapters import (
        hermes,
        gemini_analyst,
        deepseek_coder,
        memory_miner,
        file_editor as file_editor_adapter,
        autoescola,
        uiux,
    )

    for mod in (
        hermes,
        gemini_analyst,
        deepseek_coder,
        memory_miner,
        file_editor_adapter,
        autoescola,
        uiux,
    ):
        register(mod.AGENT)


def get_agent(name: str) -> AgentProtocol:
    _ensure_defaults()
    if name not in _REGISTRY:
        raise KeyError(f"Agent desconhecido: {name}. Registrados: {list(_REGISTRY)}")
    return _REGISTRY[name]


def list_agents() -> list[str]:
    _ensure_defaults()
    return sorted(_REGISTRY)
