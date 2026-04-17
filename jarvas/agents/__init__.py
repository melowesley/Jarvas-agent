"""Pacote de agents formalizados do Jarvas v0.5.0.

Cada agent é um adapter fino sobre a lógica existente, expondo o contrato
AgentProtocol (`agents.base`). Descoberta via `agents.registry.get_agent(name)`.
"""
from jarvas.agents.base import (
    AgentProtocol,
    AgentResult,
    ToolCallRecord,
)
from jarvas.agents.registry import get_agent, list_agents, register

__all__ = [
    "AgentProtocol",
    "AgentResult",
    "ToolCallRecord",
    "get_agent",
    "list_agents",
    "register",
]
