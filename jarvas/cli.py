# jarvas/cli.py
"""Jarvas — ponto de entrada do assistente de IA distribuído."""

import argparse
import uuid
from rich.console import Console
from rich.markdown import Markdown
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from jarvas.router import detect_task_type

console = Console()
_historico: list[dict] = []
_session_id = str(uuid.uuid4())


def _exibir_resposta(texto: str, modelo: str):
    console.print(f"\n[bold cyan]Jarvas[/bold cyan] [dim]({modelo})[/dim]")
    console.print(Markdown(texto))
    console.print()


def _processar_mensagem(mensagem: str) -> None:
    """Processa uma mensagem. Roteia slash commands ou envia ao Hermes."""
    from jarvas.commands import dispatch

    if mensagem.strip().startswith("/"):
        resultado = dispatch(mensagem.strip(), _historico)
        if resultado is not None:
            console.print(resultado)
        return

    from jarvas.hermes_client import chat
    from jarvas.supabase_client import save_message
    try:
        resposta, modelo = chat(mensagem, historico=_historico)
        tipo = detect_task_type(mensagem)
        _historico.append({"role": "user", "content": mensagem})
        _historico.append({"role": "assistant", "content": resposta})
        try:
            save_message(_session_id, "user", mensagem, task_type=tipo)
            save_message(_session_id, "assistant", resposta, model=modelo, task_type=tipo)
        except Exception:
            pass  # falha no Supabase nunca bloqueia o usuário
        _exibir_resposta(resposta, modelo)
    except Exception as e:
        console.print(f"[red]Erro:[/red] {e}")


def rodar_interativo():
    console.print("[bold green]Jarvas[/bold green] — assistente de IA distribuído")
    console.print("[dim]Digite sua mensagem ou /help para ver os comandos[/dim]\n")

    session = PromptSession(history=InMemoryHistory())
    while True:
        try:
            entrada = session.prompt("você > ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Até logo![/dim]")
            break

        if not entrada:
            continue
        if entrada.lower() in ("sair", "exit", "quit"):
            console.print("[dim]Até logo![/dim]")
            break

        _processar_mensagem(entrada)


def main():
    parser = argparse.ArgumentParser(
        prog="jarvas",
        description="Jarvas — seu assistente de IA distribuído",
    )
    parser.add_argument("args", nargs="*", help="Pergunta direta ou 'continuar <data> <hora>'")
    parser.add_argument("--version", action="version", version="jarvas 0.1.0")
    parsed = parser.parse_args()

    if not parsed.args:
        rodar_interativo()
        return

    # jarvas continuar ontem 15h
    if parsed.args[0].lower() == "continuar":
        data = parsed.args[1] if len(parsed.args) > 1 else "ontem"
        hora = parsed.args[2] if len(parsed.args) > 2 else "12h"
        from jarvas.supabase_client import load_session_by_time
        try:
            carregado = load_session_by_time(data, hora)
            _historico.extend(carregado)
            console.print(f"[green]Contexto restaurado:[/green] {len(carregado)} mensagens de {data} {hora}")
        except Exception as e:
            console.print(f"[yellow]Não foi possível carregar contexto:[/yellow] {e}")
        rodar_interativo()
        return

    # pergunta direta: jarvas "minha pergunta"
    _processar_mensagem(" ".join(parsed.args))


if __name__ == "__main__":
    main()
