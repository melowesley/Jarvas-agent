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

    sistema = system_prompt or (
        "Você é Jarvas, um assistente de IA distribuído. "
        "Responda de forma clara e objetiva em português ou no idioma do usuário."
    )

    messages: list[dict] = [{"role": "system", "content": sistema}]
    if historico:
        messages.extend(historico)
    messages.append({"role": "user", "content": mensagem})

    resposta = client.chat.completions.create(
        model=modelo_selecionado,
        messages=messages,
        temperature=0.7,
        max_tokens=2000,
    )
    content = resposta.choices[0].message.content or ""
    return content, modelo_selecionado
