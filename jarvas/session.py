"""Estado global persistente da sessão atual do Jarvas."""
from __future__ import annotations
import os
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Session:
    """Estado completo da sessão atual."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_path: Optional[str] = None
    last_file_read: Optional[str] = None
    last_file_edited: Optional[str] = None
    override_model: Optional[str] = None
    historico: list = field(default_factory=list)
    last_pipeline_result: dict | None = None
    last_debate_result: dict | None = None
    user_name: Optional[str] = None

    def has_project(self) -> bool:
        return self.project_path is not None and os.path.isdir(self.project_path)

    def list_project_files(self) -> list[str]:
        if not self.has_project():
            return []
        return os.listdir(self.project_path)

    def find_file(self, filename: str) -> Optional[str]:
        """Busca arquivo no projeto — exato → stem → fuzzy keywords."""
        if not self.has_project():
            return None
        import re as _re
        from pathlib import Path as _Path
        filename_lower = filename.lower().strip()
        files = os.listdir(self.project_path)

        # 1. Match exato (case-insensitive)
        for f in files:
            if f.lower() == filename_lower:
                return os.path.join(self.project_path, f)

        # 2. Match por stem ("main" → "main.py")
        stem_query = _Path(filename_lower).stem
        for f in files:
            if _Path(f).stem.lower() == stem_query:
                return os.path.join(self.project_path, f)

        # 3. Fuzzy: todas as palavras da query aparecem no nome do arquivo
        words = [w for w in _re.split(r'[\s_\-\.]+', filename_lower) if len(w) >= 3]
        if words:
            for f in files:
                if all(w in f.lower() for w in words):
                    return os.path.join(self.project_path, f)

        return None

    def context_summary(self) -> str:
        """Resumo do contexto atual para injetar em system prompts."""
        lines = []
        if self.has_project():
            lines.append(f"Projeto ativo: {self.project_path}")
            files = self.list_project_files()
            if files:
                lines.append(f"Arquivos disponíveis: {', '.join(sorted(files))}")
        if self.last_file_read:
            lines.append(f"Último arquivo lido: {self.last_file_read}")
        if self.last_file_edited:
            lines.append(f"Último arquivo editado: {self.last_file_edited}")
        return "\n".join(lines) if lines else "Sem projeto ativo."


_session_instance: Session = Session()


def get_session() -> Session:
    """Retorna a sessão global singleton. Use em todos os handlers."""
    return _session_instance


def reset_session() -> None:
    global _session_instance
    _session_instance = Session()
