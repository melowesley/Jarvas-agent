"""Adapter do editor/processador de arquivos."""
from __future__ import annotations

import re

from jarvas.agents.base import AgentResult
from jarvas.context import SessionContext

_PATH_RE = re.compile(r'[\w./\\:-]+\.\w+')


class FileEditorAgent:
    name = "file_editor"
    role = (
        "Especialista em leitura, edição e processamento de arquivos do projeto. "
        "Detecta o caminho na mensagem, aplica a instrução e retorna diff ou resumo."
    )
    model = "openrouter/auto"
    tools: list[str] = ["file_read", "file_edit", "file_process"]
    memory_scope = "project"
    can_delegate_to: list[str] = []

    def run(self, message: str, ctx: SessionContext) -> AgentResult:
        from jarvas.file_editor import edit_file, read_file
        from jarvas.file_processor import process_file

        m = _PATH_RE.search(message)
        path = m.group(0) if m else ""
        lower = message.lower()

        # Heurística: nomes típicos de intents
        if any(w in lower for w in ("leia", "mostra", "abra", "ver ")):
            if not path:
                return AgentResult(
                    content="[erro] Nao encontrei o caminho do arquivo.",
                    agent_name=self.name,
                )
            content = read_file(path, ctx.project_path)
            return AgentResult(
                content=f"**Arquivo:** `{path}`\n\n```\n{content}\n```",
                agent_name=self.name,
                metadata={"path": path, "op": "read"},
            )

        if any(path.lower().endswith(ext) for ext in (".pdf", ".xlsx", ".xls", ".csv", ".docx", ".jpg", ".jpeg", ".png")):
            result = process_file(path, message, ctx.project_path, ctx.session_id)
            if "error" in result:
                return AgentResult(content=f"[erro] {result['error']}", agent_name=self.name)
            return AgentResult(
                content=(
                    f"**Arquivo processado:** `{result['output_path']}`\n\n"
                    f"**Resumo:** {result['summary']}"
                ),
                agent_name=self.name,
                metadata=result,
            )

        if not path:
            return AgentResult(
                content="[erro] Nao encontrei o nome do arquivo na mensagem.",
                agent_name=self.name,
            )
        result = edit_file(path, message, ctx.project_path, ctx.session_id)
        if "error" in result:
            return AgentResult(content=f"[erro] {result['error']}", agent_name=self.name)
        return AgentResult(
            content=f"**Arquivo editado:** `{result['path']}`\n\n```diff\n{result['diff']}\n```",
            agent_name=self.name,
            metadata={"path": result["path"], "op": "edit"},
        )


AGENT = FileEditorAgent()
