"""Despachante de slash commands do Jarvas."""

from __future__ import annotations

from jarvas.guard_gemini import chat as gemini_chat, web_search as gemini_web
from jarvas.guard_deepseek import chat as deepseek_chat, web_search as deepseek_web
from jarvas.debate import run_debate, format_debate_result


def dispatch(comando: str, historico: list[dict]) -> str:
    """Roteia um slash command para seu handler. Retorna string formatada."""
    partes = comando.split(None, 1)
    cmd = partes[0].lower()
    args = partes[1] if len(partes) > 1 else ""

    if cmd == "/help":
        return _help()
    if cmd == "/g":
        return _guarda_g(args)
    if cmd == "/d":
        return _guarda_d(args)
    if cmd == "/debate":
        if not args:
            return "[red]Uso:[/red] /debate <tópico>"
        resultado = run_debate(args)
        return format_debate_result(resultado)
    if cmd == "/hopen":
        if not args:
            return "[red]Uso:[/red] /hopen <model-id>"
        return f"[yellow]Próxima mensagem usará o modelo:[/yellow] {args}"
    if cmd == "/hmem":
        return _hmem(args)
    if cmd == "/session":
        return _session(args)


def _help() -> str:
    return (
        "\n[bold]Comandos Jarvas:[/bold]\n"
        "  [cyan]/g[/cyan] <prompt>            → Gemini diretamente\n"
        "  [cyan]/g web[/cyan] <busca>         → Gemini + busca web\n"
        "  [cyan]/d[/cyan] <prompt>            → DeepSeek diretamente\n"
        "  [cyan]/d web[/cyan] <busca>         → DeepSeek + busca web\n"
        "  [cyan]/debate[/cyan] <tópico>       → Debate Gemini vs DeepSeek\n"
        "  [cyan]/hopen[/cyan] <model-id>      → Forçar modelo específico\n"
        "\n[bold yellow]⚠️  MemPalace (limitado no Python 3.13/Windows):[/bold yellow]\n"
        "  [cyan]/hmem status[/cyan]           → Status do MemPalace\n"
        "  [cyan]/hmem list[/cyan]             → Listar wings\n"
        "  [cyan]/hmem search[/cyan] <busca>   → Busca semântica\n"
        "  [cyan]/hmem add[/cyan] <wing> <room> <conteúdo>  → Adicionar memória\n"
        "  [cyan]/hmem get[/cyan] <id>         → Obter drawer\n"
        "  [cyan]/hmem del[/cyan] <id>         → Deletar drawer\n"
        "  [cyan]/hmem graph[/cyan]            → Estatísticas do grafo\n"
        "  [cyan]/hmem kg[/cyan] <busca>       → Consultar knowledge graph\n"
        "  [dim](Nota: Requer Python 3.12 ou pip install mempalace)[/dim]\n"
        "\n[bold]Sessões Gerenciadas:[/bold]\n"
        "  [cyan]/session list[/cyan]          → Listar agentes disponíveis\n"
        "  [cyan]/session new[/cyan] <agent>   → Criar nova sessão com agente\n"
        "  [cyan]/session send[/cyan] <id> <msg> → Enviar mensagem para sessão\n"
        "  [cyan]/session history[/cyan] <id>  → Ver histórico da sessão\n"
    )


def _guarda_g(args: str) -> str:
    if not args:
        return "[red]Uso:[/red] /g <prompt> ou /g web <busca>"
    sub = args.split(None, 1)
    if sub[0].lower() == "web":
        query = sub[1] if len(sub) > 1 else ""
        if not query:
            return "[red]Uso:[/red] /g web <busca>"
        return f"[green]Gemini web:[/green]\n{gemini_web(query)}"
    return f"[green]Gemini:[/green]\n{gemini_chat(args)}"


def _guarda_d(args: str) -> str:
    if not args:
        return "[red]Uso:[/red] /d <prompt> ou /d web <busca>"
    sub = args.split(None, 1)
    if sub[0].lower() == "web":
        query = sub[1] if len(sub) > 1 else ""
        if not query:
            return "[red]Uso:[/red] /d web <busca>"
        return f"[blue]DeepSeek web:[/blue]\n{deepseek_web(query)}"
    return f"[blue]DeepSeek:[/blue]\n{deepseek_chat(args)}"


def _hmem(args: str) -> str:
    from jarvas.mempalace_client import handle_hmem
    return handle_hmem(args)


def _session(args: str) -> str:
    import httpx
    sub = args.split(None, 2)
    if not sub or sub[0] not in ["list", "new", "send", "history"]:
        return "[red]Uso:[/red] /session list | new <agent> | send <id> <msg> | history <id>"
    
    try:
        if sub[0] == "list":
            res = httpx.get("http://localhost:8000/v1/agents")
            agents = res.json()
            return "\n".join(f"- {a['name']} ({a['id']})" for a in agents)
        
        elif sub[0] == "new":
            if len(sub) < 2:
                return "[red]Uso:[/red] /session new <agent-name>"
            agent_name = sub[1]
            # Find agent by name
            res = httpx.get("http://localhost:8000/v1/agents")
            agents = res.json()
            agent = next((a for a in agents if a['name'] == agent_name), None)
            if not agent:
                return f"[red]Agente não encontrado:[/red] {agent_name}"
            res = httpx.post("http://localhost:8000/v1/sessions", json={"agent_id": agent['id']})
            session = res.json()
            return f"[green]Sessão criada:[/green] {session['id']}"
        
        elif sub[0] == "send":
            if len(sub) < 3:
                return "[red]Uso:[/red] /session send <session-id> <message>"
            session_id = sub[1]
            message = sub[2]
            res = httpx.post(f"http://localhost:8000/v1/sessions/{session_id}/events", json={"content": message})
            if res.status_code == 202:
                # Wait for response - simplified, just return sent
                return f"[green]Mensagem enviada para sessão:[/green] {session_id}"
            else:
                return f"[red]Erro ao enviar:[/red] {res.status_code}"
        
        elif sub[0] == "history":
            if len(sub) < 2:
                return "[red]Uso:[/red] /session history <session-id>"
            session_id = sub[1]
            res = httpx.get(f"http://localhost:8000/v1/sessions/{session_id}/events")
            events = res.json()
            return "\n".join(f"{e['type']}: {e.get('content', '')}" for e in events)
    
    except Exception as e:
        return f"[red]Erro:[/red] {e}"
