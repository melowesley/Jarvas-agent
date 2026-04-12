# jarvas/router.py
"""Detecção de tipo de tarefa por palavras-chave e seleção de modelo."""

# IMPORTANTE: A ordem das chaves define a prioridade de detecção.
# "analysis" deve vir antes de "code" para que mensagens como
# "analise esse código" sejam roteadas para analysis e não para code
# (já que "código" é palavra-chave de code). Não reordene sem testar.
_PALAVRAS_CHAVE = {
    "analysis": [
        "analise", "analisa", "compare", "compara", "explica",
        "resumo", "resume", "explain", "analyze", "summarize",
    ],
    "vision": [
        "imagem", "ocr", "foto", "extrair texto", "ler imagem",
        "extract text", "image", "screenshot",
    ],
    "code": [
        "html", "python", "javascript", "código", "codigo", "kotlin",
        "criar site", "cria um site", "script", "função", "funcao",
        "botia", "typescript", "react", "css",
    ],
}

_MODELOS = {
    "code": "meta-llama/llama-3.3-70b-instruct",
    "vision": "openai/gpt-4o",
    "analysis": "anthropic/claude-3.5-sonnet",
    "chat": "nousresearch/hermes-3-llama-3.1-70b",
}


def detect_task_type(mensagem: str) -> str:
    """Retorna 'code', 'vision', 'analysis' ou 'chat' baseado nas palavras-chave.

    Quando a mensagem corresponde a múltiplos tipos, o primeiro tipo definido
    em _PALAVRAS_CHAVE tem prioridade: analysis > vision > code > chat.
    """
    lower = mensagem.lower()
    for tipo, palavras in _PALAVRAS_CHAVE.items():
        if any(p in lower for p in palavras):
            return tipo
    return "chat"


def choose_model(tipo: str) -> str:
    """Retorna o ID do modelo OpenRouter para o tipo de tarefa."""
    return _MODELOS.get(tipo, _MODELOS["chat"])
