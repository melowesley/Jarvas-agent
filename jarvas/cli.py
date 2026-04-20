# jarvas/cli.py
"""Jarvas — ponto de entrada do assistente de IA distribuído."""

import argparse
from rich.console import Console
from rich.markdown import Markdown
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from jarvas.session import get_session
from jarvas.orchestrator import process as orchestrator_process

console = Console()
_ctx = get_session()


def _exibir_resposta(texto: str, modelo: str):
    console.print(f"\n[bold cyan]Jarvas[/bold cyan] [dim]({modelo})[/dim]")
    console.print(Markdown(texto))
    console.print()


def _processar_mensagem(mensagem: str) -> None:
    """Processa uma mensagem. Slash commands vao para dispatch, resto para orchestrator."""
    from jarvas.commands import dispatch

    if mensagem.strip().startswith("/"):
        resultado = dispatch(mensagem.strip(), _ctx.historico)
        if resultado is not None:
            console.print(resultado)
        return

    try:
        resposta = orchestrator_process(mensagem, _ctx)
        modelo = "jarvas"
        _exibir_resposta(resposta, modelo)
    except Exception as e:
        console.print(f"[red]Erro:[/red] {e}")


def rodar_interativo():
    import os
    console.print("[bold green]Jarvas[/bold green] — assistente de IA distribuído")
    console.print("[dim]Digite sua mensagem ou /help para ver os comandos[/dim]\n")

    _scheduler = None
    if os.getenv("MOLTBOOK_API_KEY"):
        try:
            from jarvas.moltbook_scheduler import create_moltbook_scheduler
            _scheduler = create_moltbook_scheduler()
            _scheduler.start()
            console.print("[dim]Moltbook scheduler iniciado.[/dim]")
        except Exception as exc:
            console.print(f"[yellow]Moltbook scheduler não iniciado:[/yellow] {exc}")

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

    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)


def main():
    parser = argparse.ArgumentParser(
        prog="jarvas",
        description="Jarvas — seu assistente de IA distribuído",
    )
    parser.add_argument("args", nargs="*", help="Pergunta direta ou 'continuar <data> <hora>'")
    parser.add_argument("--version", action="version", version="jarvas 0.4.0")
    parser.add_argument("--managed", action="store_true", help="Run the managed agent server")
    parser.add_argument("--port", type=int, default=8080, help="Porta do servidor managed (default: 8080)")
    parser.add_argument("--in", dest="project_path", help="Abre Jarvas ancorado em um projeto")
    parsed = parser.parse_args()

    if parsed.managed:
        import uvicorn
        uvicorn.run("jarvas.api:app", host="0.0.0.0", port=parsed.port, reload=False)
        return

    if parsed.project_path:
        _ctx.set_project(parsed.project_path)
        console.print(f"[green]Projeto:[/green] {parsed.project_path}")
        rodar_interativo()
        return

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
            _ctx.historico.extend(carregado)
            console.print(f"[green]Contexto restaurado:[/green] {len(carregado)} mensagens de {data} {hora}")
        except Exception as e:
            console.print(f"[yellow]Não foi possível carregar contexto:[/yellow] {e}")
        rodar_interativo()
        return

    # pergunta direta: jarvas "minha pergunta"
    _processar_mensagem(" ".join(parsed.args))


if __name__ == "__main__":
    main()
