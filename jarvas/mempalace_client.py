"""Cliente MemPalace — envolve as ferramentas do MemPalace para os comandos /hmem."""

from __future__ import annotations

import json
from functools import lru_cache


@lru_cache(maxsize=1)
def _get_tools():
    """Importa as funções de ferramentas do MemPalace (lazy — evita falha se não instalado)."""
    from mempalace.mcp_server import (
        tool_status, tool_list_wings, tool_get_taxonomy,
        tool_search, tool_add_drawer, tool_delete_drawer,
        tool_get_drawer, tool_graph_stats, tool_kg_query,
    )

    class _Tools:
        pass

    t = _Tools()
    t.tool_status = tool_status
    t.tool_list_wings = tool_list_wings
    t.tool_get_taxonomy = tool_get_taxonomy
    t.tool_search = tool_search
    t.tool_add_drawer = tool_add_drawer
    t.tool_delete_drawer = tool_delete_drawer
    t.tool_get_drawer = tool_get_drawer
    t.tool_graph_stats = tool_graph_stats
    t.tool_kg_query = tool_kg_query
    return t


def _fmt(obj) -> str:
    if isinstance(obj, str):
        return obj
    return json.dumps(obj, indent=2, ensure_ascii=False)


_KNOWN_SUBS = {"status", "", "list", "taxonomy", "search", "add", "get", "del", "graph", "kg"}


def handle_hmem(args: str) -> str:
    """Roteia subcomandos /hmem para as ferramentas do MemPalace."""
    partes = args.strip().split(None, 3) if args.strip() else []
    sub = partes[0].lower() if partes else ""

    if sub not in _KNOWN_SUBS:
        return f"[yellow]Subcomando desconhecido:[/yellow] {sub} — use /help"

    try:
        tools = _get_tools()
    except Exception as e:
        return f"[red]MemPalace indisponível:[/red] {e}"

    if sub in ("status", ""):
        return f"[bold]Status do MemPalace:[/bold]\n{_fmt(tools.tool_status())}"

    if sub == "list":
        return f"[bold]Wings:[/bold]\n{_fmt(tools.tool_list_wings())}"

    if sub == "taxonomy":
        return f"[bold]Taxonomia:[/bold]\n{_fmt(tools.tool_get_taxonomy())}"

    if sub == "search":
        query = " ".join(partes[1:]) if len(partes) > 1 else ""
        if not query:
            return "[red]Uso:[/red] /hmem search <busca>"
        return f"[bold]Resultados:[/bold]\n{_fmt(tools.tool_search(query=query))}"

    if sub == "add":
        if len(partes) < 4:
            return "[red]Uso:[/red] /hmem add <wing> <room> <conteúdo>"
        wing, room, content = partes[1], partes[2], partes[3]
        return f"[green]Drawer adicionado:[/green]\n{_fmt(tools.tool_add_drawer(wing=wing, room=room, content=content))}"

    if sub == "get":
        if len(partes) < 2:
            return "[red]Uso:[/red] /hmem get <id>"
        return f"[bold]Drawer:[/bold]\n{_fmt(tools.tool_get_drawer(drawer_id=partes[1]))}"

    if sub == "del":
        if len(partes) < 2:
            return "[red]Uso:[/red] /hmem del <id>"
        return f"[yellow]Deletado:[/yellow]\n{_fmt(tools.tool_delete_drawer(drawer_id=partes[1]))}"

    if sub == "graph":
        return f"[bold]Estatísticas do Grafo:[/bold]\n{_fmt(tools.tool_graph_stats())}"

    if sub == "kg":
        query = " ".join(partes[1:]) if len(partes) > 1 else ""
        if not query:
            return "[red]Uso:[/red] /hmem kg <busca>"
        return f"[bold]Knowledge Graph:[/bold]\n{_fmt(tools.tool_kg_query(entity=query))}"

    return f"[yellow]Subcomando desconhecido:[/yellow] {sub} — use /help"
