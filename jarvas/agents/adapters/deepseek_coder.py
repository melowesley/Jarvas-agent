"""Adapter do guarda DeepSeek — estruturação, código e dados."""
from __future__ import annotations

from jarvas.agents.base import AgentResult
from jarvas.context import SessionContext


class DeepSeekCoderAgent:
    name = "deepseek_coder"
    role = (
        "Arquivista do Jarvas. Estrutura, deduplica e indexa informações; "
        "classifica snippets de código em funcionou/falhou; redige credenciais detectadas."
    )
    model = "deepseek-chat"
    tools: list[str] = ["file_read", "file_edit", "bash"]
    memory_scope = "session"
    can_delegate_to: list[str] = []

    def run(self, message: str, ctx: SessionContext) -> AgentResult:
        from jarvas.guard_deepseek import chat as deepseek_chat

        content = deepseek_chat(message)
        return AgentResult(
            content=content,
            model=self.model,
            agent_name=self.name,
        )


AGENT = DeepSeekCoderAgent()
