"""Contrato único de Agent para o Jarvas v0.5.0.

AgentResult é o retorno canônico de qualquer agent. ToolCallRecord descreve
uma chamada de ferramenta dentro do turno. AgentProtocol é o shape que
todo adapter precisa implementar — `.run(message, ctx)` síncrono retornando
AgentResult.

Esses tipos substituem tuplas/dicts ad-hoc usados nos guards e pipelines
legados, alinhando com o hardening proposto em `logica refatorada Jarvas.md`
(Pydantic + metadados ricos).
"""
from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from jarvas.context import SessionContext

MemoryScope = Literal["session", "project", "global"]


class ToolCallRecord(BaseModel):
    tool_call_id: str
    name: str
    input: dict = Field(default_factory=dict)
    output: str | dict | None = None
    is_error: bool = False
    duration_ms: int | None = None


class AgentResult(BaseModel):
    content: str
    model: str = ""
    agent_name: str = ""
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    confidence: float | None = None
    metadata: dict = Field(default_factory=dict)


@runtime_checkable
class AgentProtocol(Protocol):
    """Shape de qualquer agent do Jarvas.

    Atributos são lidos pelo Supervisor para roteamento, whitelist de tools
    e limites de delegação. `run()` é o ponto de execução único.
    """

    name: str
    role: str
    model: str
    tools: list[str]
    memory_scope: MemoryScope
    can_delegate_to: list[str]

    def run(self, message: str, ctx: SessionContext) -> AgentResult: ...
