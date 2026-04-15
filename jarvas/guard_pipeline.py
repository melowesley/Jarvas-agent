"""Pipeline paralelo: Hermes + Gemini + DeepSeek -> sintese."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed

from jarvas.hermes_client import chat as hermes_chat
from jarvas.guard_gemini import chat as gemini_chat
from jarvas.guard_deepseek import chat as deepseek_chat
from jarvas.supabase_client import save_pipeline_result
from jarvas.context import SessionContext


def run(mensagem: str, task_type: str, session_ctx: SessionContext) -> dict:
    """Executa os 3 modelos em paralelo e sintetiza o resultado."""
    results: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(hermes_chat, mensagem): "hermes",
            executor.submit(gemini_chat, mensagem): "gemini",
            executor.submit(deepseek_chat, mensagem): "deepseek",
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                resp = future.result()
                results[key] = resp[0] if isinstance(resp, tuple) else resp
            except Exception as e:
                results[key] = f"[erro: {e}]"

    prompt_sintese = (
        f"Voce recebeu 3 perspectivas sobre: \"{mensagem}\"\n\n"
        f"Hermes: {results.get('hermes', '')}\n"
        f"Gemini: {results.get('gemini', '')}\n"
        f"DeepSeek: {results.get('deepseek', '')}\n\n"
        "Sintetize em uma resposta unica, clara e objetiva. "
        "Aponte divergencias relevantes se houver."
    )
    sintese_resp, _ = hermes_chat(prompt_sintese)
    results["sintese"] = sintese_resp

    save_pipeline_result(
        session_ctx.session_id, mensagem, task_type, results
    )
    session_ctx.last_pipeline_result = results
    return results


def run_edit(original_code: str, instruction: str) -> str:
    """Envia codigo + instrucao ao Hermes. Retorna apenas o codigo editado."""
    prompt = (
        f"Instrucao: {instruction}\n\n"
        f"Codigo original:\n{original_code}\n\n"
        "Retorne APENAS o codigo editado, sem explicacoes, sem markdown, "
        "sem blocos de codigo cercados por ```."
    )
    resp, _ = hermes_chat(prompt)
    resp = resp.strip()
    if resp.startswith("```"):
        lines = resp.splitlines()
        end = -1 if lines[-1].strip() == "```" else len(lines)
        resp = "\n".join(lines[1:end])
    return resp
