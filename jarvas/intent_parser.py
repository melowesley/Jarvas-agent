"""Classifica mensagens do usuario em Intents tipados."""
from __future__ import annotations
import re
from dataclasses import dataclass, field


@dataclass
class Intent:
    type: str
    raw: str
    args: dict = field(default_factory=dict)


_FILE_EXTS = r'(\S+\.(pdf|xlsx|xls|csv|docx|txt|jpg|jpeg|png))'
_OCR_WORDS = {"ocr", "extraia texto", "leia a imagem", "gere excel", "extraia texto da imagem"}
_EDIT_WORDS = ["edite", "melhore", "corrija", "reescreva", "refatore"]
_READ_WORDS = ["leia", "mostra", "abra", "ver o arquivo", "mostre o arquivo"]
_DEBATE_WORDS = ["debate", "peça um debate", "debate sobre"]
_MEMORY_WORDS = ["armazene", "guarda isso", "salva isso", "memorize"]
_WEB_WORDS = ["pesquise", "busque na web", "procure sobre"]


def parse(mensagem: str, project_ctx: str | None = None) -> Intent:
    """Retorna o Intent mais especifico para a mensagem."""
    lower = mensagem.lower()

    # 1. SET_PROJECT — #/path ou #C:/path
    m = re.search(r'#([A-Za-z]:[/\\][^\s]+|/[^\s]+)', mensagem)
    if m:
        return Intent(type="SET_PROJECT", raw=mensagem, args={"path": m.group(1)})

    # 2. ATTACH / OCR — extensao de arquivo no texto
    m = re.search(_FILE_EXTS, mensagem, re.IGNORECASE)
    if m:
        path = m.group(1)
        ext = m.group(2).lower()
        if ext in ("jpg", "jpeg", "png") and any(w in lower for w in _OCR_WORDS):
            return Intent(type="OCR", raw=mensagem, args={"path": path})
        if any(w in lower for w in _OCR_WORDS):
            return Intent(type="OCR", raw=mensagem, args={"path": path})
        return Intent(type="ATTACH", raw=mensagem, args={"path": path, "file_type": ext})

    # 3. FILE_EDIT
    if any(w in lower for w in _EDIT_WORDS):
        return Intent(type="FILE_EDIT", raw=mensagem, args={"instruction": mensagem})

    # 4. FILE_READ
    if any(w in lower for w in _READ_WORDS):
        return Intent(type="FILE_READ", raw=mensagem, args={"instruction": mensagem})

    # 5. DEBATE
    if any(w in lower for w in _DEBATE_WORDS):
        topic = re.sub(r'.*(debate sobre|peça um debate sobre|debate)\s*', '', lower).strip()
        return Intent(type="DEBATE", raw=mensagem, args={"topic": topic or mensagem})

    # 6. STORE_MEMORY
    if any(w in lower for w in _MEMORY_WORDS):
        return Intent(type="STORE_MEMORY", raw=mensagem, args={"scope": 5})

    # 7. SEARCH_WEB
    if any(w in lower for w in _WEB_WORDS):
        query = re.sub(r'.*(pesquise|busque na web|procure sobre)\s+', '', lower).strip()
        return Intent(type="SEARCH_WEB", raw=mensagem, args={"query": query})

    # 8. PIPELINE — topico tecnico detectado pelo router existente
    from jarvas.router import detect_task_type
    task_type = detect_task_type(mensagem)
    if task_type != "chat":
        return Intent(type="PIPELINE", raw=mensagem, args={"task_type": task_type})

    # 9. CHAT — fallback
    return Intent(type="CHAT", raw=mensagem, args={})
