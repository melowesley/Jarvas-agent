"""Handler do intent LIST_FILES."""
from jarvas.session import get_session


def handle_list_files() -> str:
    session = get_session()

    if not session.has_project():
        return (
            "Nenhum projeto ativo. Defina um projeto primeiro com:\n"
            "  #C:\\caminho\\da\\pasta"
        )

    files = session.list_project_files()
    if not files:
        return f"A pasta `{session.project_path}` está vazia."

    lines = [f"**Arquivos em** `{session.project_path}`:"]
    for f in sorted(files):
        lines.append(f"  • {f}")

    return "\n".join(lines)
