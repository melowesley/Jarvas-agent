# jarvas/commands.py
"""Despachante de slash commands. Implementação completa na Tarefa 10."""


def dispatch(comando: str, historico: list[dict]) -> str | None:
    """Roteia slash commands. Stub — implementação completa em Tarefa 10."""
    if comando == "/help":
        return (
            "\n[bold]Comandos disponíveis:[/bold]\n"
            "  [cyan]/g[/cyan] <prompt>      → Gemini diretamente\n"
            "  [cyan]/d[/cyan] <prompt>      → DeepSeek diretamente\n"
            "  [cyan]/debate[/cyan] <tópico> → Debate Gemini vs DeepSeek\n"
            "  [cyan]/hopen[/cyan] <modelo>  → Forçar modelo específico\n"
            "  [cyan]/hmem[/cyan] <cmd>      → Acessar MemPalace\n"
            "  [cyan]/help[/cyan]            → Esta mensagem\n"
        )
    return f"[yellow]Comando ainda não implementado:[/yellow] {comando}"
