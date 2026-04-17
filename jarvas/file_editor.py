"""Le e edita arquivos do projeto com seguranca."""
from __future__ import annotations
import difflib
import os
from pathlib import Path

from jarvas.guard_pipeline import run_edit
from jarvas.supabase_client import save_file_edit

_BLOCKED_SUFFIXES = {".env", ".key", ".pem"}
_BLOCKED_NAMES = {".env"}


def _resolve(path: str, project_base: str | None) -> Path:
    p = Path(path)
    if not p.is_absolute() and project_base:
        p = Path(project_base) / path
    return p.resolve()


def _is_blocked(p: Path) -> bool:
    return (
        p.suffix in _BLOCKED_SUFFIXES
        or p.name in _BLOCKED_NAMES
        or ".git" in p.parts
    )


def find_file_in_project(filename: str, project_path: str) -> str | None:
    """Busca arquivo na pasta do projeto ignorando case e variações de encoding."""
    if not project_path or not os.path.isdir(project_path):
        return None
    filename_lower = filename.lower()
    for f in os.listdir(project_path):
        if f.lower() == filename_lower:
            return os.path.join(project_path, f)
    return None


def read_file(path: str, project_base: str | None = None) -> str:
    """Le arquivo e retorna conteudo como string."""
    p = _resolve(path, project_base)
    if _is_blocked(p):
        return f"[erro] Acesso bloqueado: {p.name}"
    if not p.exists() and project_base:
        found = find_file_in_project(Path(path).name, project_base)
        if found:
            p = Path(found)
        else:
            return f"[erro] Arquivo nao encontrado: {Path(path).name}"
    elif not p.exists():
        return f"[erro] Arquivo nao encontrado: {p.name}"
    return p.read_text(encoding="utf-8")


def edit_file(
    path: str,
    instruction: str,
    project_base: str | None,
    session_id: str,
) -> dict:
    """Edita arquivo no disco usando guard_pipeline e retorna diff."""
    p = _resolve(path, project_base)
    if _is_blocked(p):
        return {"error": f"Acesso bloqueado: {p.name}"}
    if not p.exists():
        return {"error": f"Arquivo nao encontrado: {p}"}

    original = p.read_text(encoding="utf-8")
    edited = run_edit(original, instruction)

    diff = "\n".join(difflib.unified_diff(
        original.splitlines(),
        edited.splitlines(),
        fromfile=f"original/{p.name}",
        tofile=f"editado/{p.name}",
        lineterm="",
    ))

    p.write_text(edited, encoding="utf-8")
    save_file_edit(session_id, str(p), instruction, original, edited, diff)

    return {"path": str(p), "diff": diff, "original": original, "edited": edited}
