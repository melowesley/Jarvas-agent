"""Guarda Gemini — chat direto e minerador de progresso de conversas."""

import os
import warnings
from functools import lru_cache

with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai

from dotenv import load_dotenv

from jarvas.supabase_client import save_guard_log

load_dotenv(override=True)

_SYSTEM_PROMPT = (
    "Você é o Minerador de Conhecimento do Jarvas. "
    "Analisa conversas técnicas e extrai APENAS padrões de progresso concreto. "
    "IGNORE: saudações, agradecimentos, conversas sociais, pedidos genéricos sem resolução. "
    "Detecte sinais como: 'deu certo', 'funcionou', 'esse erro persiste', 'resolvido', 'ainda não resolve'. "
    "Quando solicitado, retorne JSON VÁLIDO com schema: "
    '{ "aprendizados": [{"descricao": str, "evidence": [str]}], '
    '"falhas": [{"erro": str, "causa": str}], '
    '"termos_chave": [str], '
    '"progresso": "true"|"false"|"partial", '
    '"workaround": null, '
    '"confidence": 0.0 }. '
    "Se a conversa não contiver progresso técnico relevante, retorne: "
    '{"progresso": "false", "confidence": 0.0}. '
    "Nunca invente aprendizados. Só inclua o que há evidência explícita na conversa."
)


@lru_cache(maxsize=1)
def _get_model():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não definido no .env")
    genai.configure(api_key=api_key, transport="rest")
    return genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=_SYSTEM_PROMPT,
    )


def _gen_config(temperature: float) -> dict:
    return {"temperature": temperature, "top_p": 0.9}


def chat(mensagem: str, temperature: float = 0.3) -> str:
    """Envia mensagem diretamente ao guarda Gemini e retorna a resposta.

    Default 0.3 = analítico/preciso. Use 0.6 para replies sociais com tom natural.
    """
    model = _get_model()
    resposta = model.generate_content(mensagem, generation_config=_gen_config(temperature))
    resultado = resposta.text
    save_guard_log("gemini", mensagem, resultado)
    return resultado


def web_search(query: str) -> str:
    """Pede ao Gemini para fazer uma busca na web e resumir os resultados."""
    model = _get_model()
    prompt = f"Faça uma busca na web sobre: {query}\nResuma os resultados encontrados."
    resposta = model.generate_content(prompt, generation_config=_gen_config(0.4))
    resultado = resposta.text
    save_guard_log("gemini", f"[web] {query}", resultado)
    return resultado


def mine_conversation(messages: list[dict]) -> dict | None:
    """
    Analisa histórico de conversa e extrai padrões de progresso.
    Retorna dict validado ou None se sem progresso relevante.
    """
    import json
    import re

    if len(messages) < 4:
        return None

    msgs = messages[-20:]
    transcript = "\n".join(
        f"{m['role'].upper()}: {m.get('content', '')[:500]}" for m in msgs
    )
    prompt = (
        f"Analise esta conversa técnica:\n\n{transcript}\n\n"
        "Retorne APENAS o JSON estruturado conforme schema definido. Sem texto adicional."
    )
    try:
        from jarvas.miners.models import LearningsOut

        model = _get_model()
        resposta = model.generate_content(prompt, generation_config=_gen_config(0.2))
        match = re.search(r'\{.*\}', resposta.text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            validated = LearningsOut(**data)
            if validated.confidence < 0.3 or validated.progresso == "false":
                return None
            return validated.model_dump()
    except Exception:
        pass
    return None
