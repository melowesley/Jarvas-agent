"""Adapter do Hermes (generalista via OpenRouter) para o contrato AgentProtocol."""
from __future__ import annotations

from jarvas.agents.base import AgentResult
from jarvas.context import SessionContext


class HermesAgent:
    name = "hermes"
    role = (
        "Generalista do Jarvas. Responde em português de forma clara e objetiva; "
        "delega para especialistas quando a tarefa exige análise semântica (gemini_analyst), "
        "código (deepseek_coder) ou edição de arquivos (file_editor)."
    )
    model = "openrouter/auto"  # resolvido dinamicamente por `router.choose_model`
    tools: list[str] = ["call_agent", "call_strategy", "web_search"]
    memory_scope = "session"
    can_delegate_to: list[str] = [
        "gemini_analyst",
        "deepseek_coder",
        "file_editor",
        "memory_miner",
        "autoescola_specialist",
        "uiux_specialist",
    ]

    def run(self, message: str, ctx: SessionContext) -> AgentResult:
        from jarvas.hermes_client import chat as hermes_chat

        content, modelo = hermes_chat(message, historico=ctx.historico)
        return AgentResult(
            content=content,
            model=modelo,
            agent_name=self.name,
        )


AGENT = HermesAgent()
