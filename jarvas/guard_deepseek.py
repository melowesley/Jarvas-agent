"""Guarda DeepSeek — chat direto, busca web e processamento arquivístico."""

import os
from functools import lru_cache

from openai import OpenAI
from dotenv import load_dotenv

from jarvas.supabase_client import save_guard_log

load_dotenv()

_SYSTEM_PROMPT = (
    "Você é o Guarda DeepSeek do sistema Jarvas. "
    "Seu papel é estruturar, deduplicar e indexar informações de forma arquivística. "
    "Organize dados com precisão e consistência."
)


@lru_cache(maxsize=1)
def _get_client() -> OpenAI:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY não definido no .env")
    return OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com/v1",
    )


def chat(mensagem: str) -> str:
    """Envia mensagem diretamente ao guarda DeepSeek e retorna a resposta."""
    client = _get_client()
    resposta = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": mensagem},
        ],
        temperature=0.6,
        max_tokens=2000,
    )
    resultado = resposta.choices[0].message.content
    save_guard_log("deepseek", mensagem, resultado)
    return resultado


def web_search(query: str) -> str:
    """Pede ao DeepSeek para pesquisar um tópico na web."""
    client = _get_client()
    prompt = (
        f"Pesquise e resuma informações sobre: {query}\n"
        "Apresente os principais pontos de forma estruturada."
    )
    resposta = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
        max_tokens=2000,
    )
    resultado = resposta.choices[0].message.content
    save_guard_log("deepseek", f"[web] {query}", resultado)
    return resultado
