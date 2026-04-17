"""Adapter do especialista UI/UX (skill externa `ui-ux-pro-max-skill-main`).

Envolve o Hermes injetando a skill UI/UX como contexto de sistema. Quando o
runtime `managed/` passar a carregar skills persistidas (Fase 3), este adapter
pode migrar pra consumir `AgentRecord.skills` em vez do prompt inline.
"""
from __future__ import annotations

from jarvas.agents.base import AgentResult
from jarvas.context import SessionContext

_UIUX_ROLE = (
    "Você é o especialista UI/UX Pro Max do Jarvas. "
    "Projeta interfaces limpas, acessíveis e consistentes; sugere tokens de design, "
    "hierarquia visual, microinterações e estados vazios/erro. "
    "Responda com exemplos de componentes, guidelines e snippets de CSS/Tailwind "
    "quando fizer sentido."
)


class UIUXSpecialistAgent:
    name = "uiux_specialist"
    role = _UIUX_ROLE
    model = "openrouter/auto"
    tools: list[str] = ["file_read", "file_edit"]
    memory_scope = "project"
    can_delegate_to: list[str] = []

    def run(self, message: str, ctx: SessionContext) -> AgentResult:
        from jarvas.hermes_client import chat as hermes_chat

        content, modelo = hermes_chat(
            message,
            historico=ctx.historico,
            system_prompt=self.role,
        )
        return AgentResult(
            content=content,
            model=modelo,
            agent_name=self.name,
        )


AGENT = UIUXSpecialistAgent()
