"""Orquestrador de debate multi-agente — Gemini vs DeepSeek, chega ao consenso."""

from jarvas.guard_gemini import chat as gemini_chat
from jarvas.guard_deepseek import chat as deepseek_chat
from jarvas.supabase_client import save_debate_log


def run_debate(topico: str, max_rounds: int = 3) -> dict:
    """Executa debate entre Gemini e DeepSeek sobre o tópico dado.

    Retorna dict com: topic, rounds (lista), consensus (str).
    """
    rounds: list[dict] = []

    ctx_gemini = (
        f"Você está num debate sobre: '{topico}'. "
        f"Apresente seu ponto de vista inicial de forma clara e argumentada."
    )
    ctx_deepseek = ctx_gemini

    for rodada in range(1, max_rounds + 1):
        resp_gemini = gemini_chat(ctx_gemini)
        resp_deepseek = deepseek_chat(ctx_deepseek)

        rounds.append({
            "round": rodada,
            "gemini": resp_gemini,
            "deepseek": resp_deepseek,
        })

        ctx_gemini = (
            f"Debate sobre '{topico}' — rodada {rodada + 1}.\n"
            f"DeepSeek disse: {resp_deepseek}\n"
            f"Responda e refine sua posição, ou concorde se o argumento fizer sentido."
        )
        ctx_deepseek = (
            f"Debate sobre '{topico}' — rodada {rodada + 1}.\n"
            f"Gemini disse: {resp_gemini}\n"
            f"Responda e refine sua posição, ou concorde se o argumento fizer sentido."
        )

    # Consenso final — Gemini sintetiza
    prompt_consenso = (
        f"Debate sobre '{topico}' concluído após {max_rounds} rodada(s).\n"
        f"Rodadas: {rounds}\n"
        f"Sintetize o consenso alcançado em 2-3 parágrafos objetivos."
    )
    consenso = gemini_chat(prompt_consenso)

    save_debate_log(topico, rounds, consenso)

    return {
        "topic": topico,
        "rounds": rounds,
        "consensus": consenso,
    }


def format_debate_result(resultado: dict) -> str:
    """Formata o resultado do debate para exibição no terminal."""
    linhas = [
        f"\n[bold]Debate:[/bold] {resultado['topic']}",
        f"[dim]Rodadas: {len(resultado['rounds'])}[/dim]\n",
    ]
    for r in resultado["rounds"]:
        linhas.append(f"[cyan]Rodada {r['round']}[/cyan]")
        linhas.append(f"[green]Gemini:[/green] {r['gemini'][:200]}...")
        linhas.append(f"[blue]DeepSeek:[/blue] {r['deepseek'][:200]}...\n")
    linhas.append(f"[bold yellow]Consenso:[/bold yellow]\n{resultado['consensus']}")
    return "\n".join(linhas)
