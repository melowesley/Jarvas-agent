"""Estratégias multi-agent (Pipeline paralelo, Debate em rounds).

Na Fase 2 estas funções são chamadas diretamente pelo Supervisor para preservar
comportamento bit-a-bit. Na Fase 3 elas viram tools `call_strategy` expostas no
`managed/toolset.py`.
"""
from __future__ import annotations

from jarvas.agents.base import AgentResult
from jarvas.context import SessionContext


def run_pipeline(message: str, task_type: str, ctx: SessionContext) -> AgentResult:
    """Executa guard_pipeline.run (Hermes+Gemini+DeepSeek paralelos + síntese)."""
    from jarvas.guard_pipeline import run

    results = run(message, task_type, ctx)
    ctx.historico.append({"role": "user", "content": message})
    ctx.historico.append({"role": "assistant", "content": results["sintese"]})
    return AgentResult(
        content=results["sintese"],
        agent_name="pipeline_strategy",
        metadata={k: v for k, v in results.items() if k != "sintese"},
    )


def run_debate_strategy(topic: str, ctx: SessionContext, max_rounds: int = 3) -> AgentResult:
    """Executa debate.run_debate e formata pra CLI."""
    from jarvas.debate import format_debate_result, run_debate

    resultado = run_debate(topic, max_rounds=max_rounds)
    ctx.last_debate_result = resultado
    ctx.historico.append({"role": "user", "content": topic})
    ctx.historico.append({"role": "assistant", "content": resultado["consensus"]})
    formatted = format_debate_result(resultado)
    return AgentResult(
        content=formatted,
        agent_name="debate_strategy",
        metadata={"topic": resultado["topic"], "rounds": len(resultado["rounds"])},
    )
