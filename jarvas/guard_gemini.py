"""Guarda Gemini — chat direto e processamento de memória em segundo plano."""

import os
import warnings
from functools import lru_cache

with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai

from dotenv import load_dotenv

from jarvas.supabase_client import save_guard_log

load_dotenv()

_SYSTEM_PROMPT = (
    "Você é o Guarda Gemini do sistema Jarvas. "
    "Seu papel é analisar, encontrar padrões e organizar memórias de forma semântica. "
    "Seja preciso e estruturado nas respostas."
)


@lru_cache(maxsize=1)
def _get_model():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não definido no .env")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp",
        system_instruction=_SYSTEM_PROMPT,
    )


def chat(mensagem: str) -> str:
    """Envia mensagem diretamente ao guarda Gemini e retorna a resposta."""
    model = _get_model()
    resposta = model.generate_content(mensagem)
    resultado = resposta.text
    save_guard_log("gemini", mensagem, resultado)
    return resultado


def web_search(query: str) -> str:
    """Pede ao Gemini para fazer uma busca na web e resumir os resultados."""
    model = _get_model()
    prompt = f"Faça uma busca na web sobre: {query}\nResuma os resultados encontrados."
    resposta = model.generate_content(prompt)
    resultado = resposta.text
    save_guard_log("gemini", f"[web] {query}", resultado)
    return resultado
