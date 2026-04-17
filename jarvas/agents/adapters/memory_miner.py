"""Adapter do minerador de conversa → MemPalace."""
from __future__ import annotations

from jarvas.agents.base import AgentResult
from jarvas.context import SessionContext


class MemoryMinerAgent:
    name = "memory_miner"
    role = (
        "Minerador de progresso do Jarvas. Extrai aprendizados, falhas e termos-chave "
        "do histórico da conversa e grava no MemPalace com metadados rastreáveis."
    )
    model = "gemini-2.5-flash"
    tools: list[str] = ["mempalace_add"]
    memory_scope = "global"
    can_delegate_to: list[str] = []

    def run(self, message: str, ctx: SessionContext) -> AgentResult:
        from jarvas.memory_writer import store

        content = store(ctx, scope=5)
        return AgentResult(
            content=content,
            model=self.model,
            agent_name=self.name,
        )


AGENT = MemoryMinerAgent()
