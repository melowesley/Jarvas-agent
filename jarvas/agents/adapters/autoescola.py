"""Adapter do especialista Autoescola Jarvas.

Envolve o dataset `LESSONS` e a função `validate_step` como um agent que
responde perguntas sobre as lições e valida passos. Não chama LLM direto:
usa Hermes com o curriculum injetado no prompt.
"""
from __future__ import annotations

import json

from jarvas.agents.base import AgentResult
from jarvas.context import SessionContext


class AutoescolaSpecialistAgent:
    name = "autoescola_specialist"
    role = (
        "Professor da Autoescola Jarvas. Responde perguntas sobre as 6 aulas do "
        "curriculum (progresso, comandos válidos, próximos passos) usando o "
        "dataset LESSONS como contexto autoritativo."
    )
    model = "openrouter/auto"
    tools: list[str] = ["file_read"]
    memory_scope = "project"
    can_delegate_to: list[str] = []

    def run(self, message: str, ctx: SessionContext) -> AgentResult:
        from jarvas.autoescola_data import LESSONS
        from jarvas.hermes_client import chat as hermes_chat

        resumo = [
            {"id": i + 1, "titulo": l.get("title", ""), "passos": len(l.get("steps", []))}
            for i, l in enumerate(LESSONS)
        ]
        prompt = (
            "Você é o especialista da Autoescola Jarvas.\n"
            f"Curriculum: {json.dumps(resumo, ensure_ascii=False)}\n\n"
            f"Pergunta do usuário: {message}"
        )
        content, modelo = hermes_chat(prompt, historico=ctx.historico)
        return AgentResult(
            content=content,
            model=modelo,
            agent_name=self.name,
            metadata={"total_lessons": len(LESSONS)},
        )


AGENT = AutoescolaSpecialistAgent()
