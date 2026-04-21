# jarvas/hermes_client.py
"""Cliente OpenRouter para o Hermes — envia mensagens, retorna resposta do assistente."""

import os
from functools import lru_cache
from openai import OpenAI
from dotenv import load_dotenv
from jarvas.router import detect_task_type, choose_model

load_dotenv()


@lru_cache(maxsize=1)
def _get_client() -> OpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY não definido no .env")
    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )


def build_system_prompt(base: str = "") -> str:
    """Constrói system prompt incluindo contexto atual da sessão."""
    from jarvas.session import get_session
    ctx = get_session()
    context = ctx.context_summary()

    base_text = base or (
        "Você é Jarvas, um assistente de IA distribuído. "
        "Responda de forma clara e objetiva em português ou no idioma do usuário."
    )
    if context == "Sem projeto ativo.":
        return base_text

    return (
        f"{base_text}\n\n"
        f"CONTEXTO ATUAL DA SESSÃO:\n{context}\n\n"
        "REGRAS:\n"
        "- Se houver projeto ativo, considere isso ao responder\n"
        "- Se o usuário mencionar arquivos, assuma que estão no projeto ativo\n"
        "- Não diga que não tem acesso a arquivos — você TEM acesso através dos intents\n"
        "- Se precisar ler um arquivo, sugira o comando exato (ex: \"leia main.py\")"
    )


def chat(
    mensagem: str,
    historico: list[dict] | None = None,
    modelo: str | None = None,
    system_prompt: str | None = None,
) -> tuple[str, str]:
    """Envia mensagem ao Hermes via OpenRouter.

    Retorna: (texto_resposta, modelo_usado)
    """
    client = _get_client()
    tipo = detect_task_type(mensagem)
    modelo_selecionado = modelo or choose_model(tipo)

    sistema = system_prompt or build_system_prompt()

    messages: list[dict] = [{"role": "system", "content": sistema}]
    if historico:
        messages.extend(historico)
    messages.append({"role": "user", "content": mensagem})

    from jarvas.model_registry import FALLBACK_CHAINS

    modelos_a_tentar = [modelo_selecionado] + FALLBACK_CHAINS.get(modelo_selecionado, [])

    for tentativa in modelos_a_tentar:
        try:
            resposta = client.chat.completions.create(
                model=tentativa,
                messages=messages,
                temperature=0.3,
                max_tokens=2000,
            )
            content = resposta.choices[0].message.content or ""
            if tentativa != modelo_selecionado:
                print(
                    f"\n[aviso] Modelo '{modelo_selecionado}' falhou na chamada.\n"
                    f"        Usando fallback: '{tentativa}'\n"
                )
            return content, tentativa
        except Exception as e:
            err = str(e).lower()
            if any(k in err for k in ("404", "not found", "model", "unavailable")):
                continue
            raise

    return "[erro] Nenhum modelo disponível respondeu com sucesso.", modelo_selecionado
