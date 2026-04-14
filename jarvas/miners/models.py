"""Modelos Pydantic para output dos miners de conversa e código."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


class FailureItem(BaseModel):
    erro: str
    causa: str


class LearningItem(BaseModel):
    descricao: str
    evidence: list[str] = []


class LearningsOut(BaseModel):
    aprendizados: list[LearningItem] = []
    falhas: list[FailureItem] = []
    termos_chave: list[str] = []
    progresso: Literal["true", "false", "partial"] = "false"
    workaround: str | None = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class CodeSnippet(BaseModel):
    linguagem: str = ""
    codigo: str
    funcionou: bool
    motivo: str = ""
    sensitive: bool = False  # True se contiver credenciais detectadas


class CodeMineOut(BaseModel):
    snippets: list[CodeSnippet] = []
    confidence: float = Field(0.0, ge=0.0, le=1.0)
