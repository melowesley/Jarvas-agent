"""Adapter do guarda Gemini — análise semântica e busca web."""
from __future__ import annotations

from jarvas.agents.base import AgentResult
from jarvas.context import SessionContext


class GeminiAnalystAgent:
    name = "gemini_analyst"
    role = (
        "Analista semântico do Jarvas. Especialista em interpretação de texto, "
        "mineração de conhecimento e busca/resumo de informações da web."
    )
    model = "gemini-2.5-flash"
    tools: list[str] = ["web_search", "file_read"]
    memory_scope = "session"
    can_delegate_to: list[str] = []

    def run(self, message: str, ctx: SessionContext) -> AgentResult:
        from jarvas.guard_gemini import chat as gemini_chat

        content = gemini_chat(message)
        return AgentResult(
            content=content,
            model=self.model,
            agent_name=self.name,
        )


AGENT = GeminiAnalystAgent()
