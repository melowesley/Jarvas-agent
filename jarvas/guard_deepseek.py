"""Guarda DeepSeek — chat direto, busca web e mineração de código."""

import os
import re
from functools import lru_cache

_SENSITIVE_RE = re.compile(
    r'(api[_-]?key|token|secret|password|bearer|sk-|AIza)\s*[=:]\s*\S+',
    re.IGNORECASE,
)

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


def mine_code(messages: list[dict]) -> dict | None:
    """
    Extrai snippets de código da conversa, classifica funcionou/falhou,
    e redige credenciais detectadas. Retorna None se sem snippets relevantes.
    """
    import json

    code_blocks: list[dict] = []
    for m in messages:
        for match in re.finditer(r'```(\w*)\n(.*?)```', m.get("content", ""), re.DOTALL):
            lang = match.group(1) or "text"
            code = match.group(2)
            sensitive = bool(_SENSITIVE_RE.search(code))
            code_blocks.append({
                "lang": lang,
                "code": code,
                "sensitive": sensitive,
                "role": m.get("role", ""),
            })

    if not code_blocks:
        return None

    summary = "\n---\n".join(
        f"[{b['role']}] {b['lang']}:\n{b['code'][:300]}" for b in code_blocks
    )
    prompt = (
        f"Classifique cada snippet abaixo como funcionou/falhou e explique brevemente:\n\n{summary}\n\n"
        'Retorne JSON: {"snippets": [{"linguagem":str,"codigo":str,"funcionou":bool,"motivo":str}], "confidence": 0.0}'
    )
    try:
        from jarvas.miners.models import CodeMineOut

        client = _get_client()
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
        )
        text = resp.choices[0].message.content
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            # Marcar e redigir credenciais detectadas localmente
            for i, s in enumerate(data.get("snippets", [])):
                if i < len(code_blocks) and code_blocks[i]["sensitive"]:
                    s["sensitive"] = True
                    s["codigo"] = "[REDACTED]"
            out = CodeMineOut(**data)
            if out.confidence < 0.3:
                return None
            return out.model_dump()
    except Exception:
        pass
    return None
