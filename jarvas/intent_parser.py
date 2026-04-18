"""Classifica mensagens do usuario em Intents tipados."""
from __future__ import annotations
import re
from dataclasses import dataclass, field


@dataclass
class Intent:
    type: str
    raw: str
    args: dict = field(default_factory=dict)


_FILE_EXTS = r'(\S+\.(pdf|xlsx|xls|csv|docx|txt|jpg|jpeg|png|py|js|ts|json|yaml|yml|md|html|css|sh|toml|ini|cfg|rs|go|java|cpp|c|rb))'
_OCR_WORDS = {"ocr", "extraia texto", "leia a imagem", "gere excel", "extraia texto da imagem"}
_EDIT_WORDS = [
    "edite", "edita", "editar",
    "melhore", "melhora", "melhorar",
    "corrija", "corrige", "corrigir",
    "reescreva", "reescreve", "reescrever",
    "refatore", "refatora", "refatorar",
    "adicione", "adiciona", "adicionar",
    "modifique", "modifica", "modificar",
    "atualize", "atualiza", "atualizar",
]
_READ_WORDS = [
    "leia", "lê", "ler",
    "mostra", "mostre", "mostrar",
    "abra", "abre", "abrir",
    "ver o arquivo", "mostre o arquivo",
    "analisa esse arquivo", "analise esse arquivo",
    "analisa o arquivo", "analise o arquivo",
    "veja", "ver",
]
_READ_WORDS_RE = re.compile(
    r'\b(leia|lê|ler|mostra|mostre|mostrar|abra|abre|abrir|veja|ver)\b'
    r'|ver o arquivo|mostre o arquivo'
    r'|analis[ae] (esse |o )?arquivo',
    re.IGNORECASE,
)
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

    # 2. ATTACH / OCR / FILE_READ / FILE_EDIT — extensao de arquivo no texto
    m = re.search(_FILE_EXTS, mensagem, re.IGNORECASE)
    if m:
        path = m.group(1)
        ext = m.group(2).lower()
        if ext in ("jpg", "jpeg", "png") and any(w in lower for w in _OCR_WORDS):
            return Intent(type="OCR", raw=mensagem, args={"path": path})
        if any(w in lower for w in _OCR_WORDS):
            return Intent(type="OCR", raw=mensagem, args={"path": path})
        # Arquivo de código/texto: EDIT ou READ antes de cair em ATTACH
        code_exts = {"py", "js", "ts", "json", "yaml", "yml", "md", "html", "css",
                     "sh", "toml", "ini", "cfg", "rs", "go", "java", "cpp", "c", "rb", "txt"}
        if ext in code_exts:
            if any(w in lower for w in _EDIT_WORDS):
                return Intent(type="FILE_EDIT", raw=mensagem, args={"instruction": mensagem, "path": path})
            return Intent(type="FILE_READ", raw=mensagem, args={"instruction": mensagem, "path": path})
        return Intent(type="ATTACH", raw=mensagem, args={"path": path, "file_type": ext})

    # 3. FILE_EDIT — trigger + nome de arquivo com extensão
    if any(w in lower for w in _EDIT_WORDS) and re.search(r'\w+\.\w{2,4}', lower):
        return Intent(type="FILE_EDIT", raw=mensagem, args={"instruction": mensagem})

    # 4. FILE_READ — requer verbo de leitura + referência a arquivo
    if _READ_WORDS_RE.search(mensagem) and re.search(r'\w+\.\w{2,4}|arquivo|pasta', lower):
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
