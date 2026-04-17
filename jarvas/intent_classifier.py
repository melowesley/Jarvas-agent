"""
intent_classifier.py
Classificador de intents do Jarvas.
Usa regex + keywords + contexto da sessão para decidir a ação.
"""
from __future__ import annotations
import re

# ─────────────────────────────────────────────
# GATILHOS POR INTENT
# ─────────────────────────────────────────────

SET_PROJECT_PATTERN = re.compile(
    r'^\s*#\s*([a-zA-Z]:[\\\/][\w\-\\\/\. ]+|[\\\/][\w\-\\\/\.]+)',
    re.IGNORECASE,
)

FILE_EDIT_VERBS = [
    "edite", "edita", "editar",
    "melhore", "melhora", "melhorar",
    "corrija", "corrige", "corrigir",
    "refatore", "refatora", "refatorar",
    "adicione", "adiciona", "adicionar",
    "modifique", "modifica", "modificar",
    "atualize", "atualiza", "atualizar",
    "reescreva", "reescreve", "reescrever",
    "altere", "altera", "alterar",
    "remova", "remove", "remover",
    "apague", "apaga", "apagar",
]

FILE_READ_VERBS = [
    "leia", "lê", "ler",
    "mostra", "mostre", "mostrar",
    "abra", "abre", "abrir",
    "veja", "ver",
    "exibe", "exibir",
    "analise", "analisa", "analisar",
]

LIST_FILES_PATTERNS = [
    "liste os arquivos", "lista os arquivos", "listar arquivos",
    "quais arquivos", "que arquivos", "arquivos tem",
    "o que tem na pasta", "o que há na pasta",
    "mostra os arquivos", "mostrar arquivos",
    " ls ", "ls\n", " dir ", "dir\n",
]

ATTACH_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".doc", ".txt", ".csv"}
OCR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

STORE_MEMORY_TRIGGERS = [
    "armazene", "armazena", "armazenar",
    "memorize", "memoriza", "memorizar",
    "guarda isso", "guarde isso", "guardar isso",
    "salva isso", "salve isso", "salvar isso",
    "lembra disso", "lembre disso",
]

RESUME_SESSION_PATTERNS = [
    r"\bontem\b", r"\bantes\b",
    r"lembra quando", r"quando travei",
    r"aquele bug", r"aquele erro", r"aquele problema",
    r"continuar de onde", r"retomar",
]

DEBATE_TRIGGERS = ["debate sobre", "debate entre", "compare "]

SEARCH_WEB_TRIGGERS = [
    "pesquise", "pesquisa", "pesquisar",
    "busque na web", "busca na web",
    "procure online", "pesquisa online",
]

PIPELINE_MARKERS = [
    "escreva", "escreve", "escrever",
    "crie", "cria", "criar",
    "gere", "gera", "gerar",
    "implemente", "implementa", "implementar",
    "como fazer", "como eu faço",
]


def _file_ref(text: str) -> str | None:
    """Retorna nome do arquivo mencionado (com extensão) ou None.
    Usa o ÚLTIMO ponto para suportar nomes com versão (ex: v0.4.0.pdf)."""
    m = re.search(
        r'[\w\-][\w\.\-]*\.(pdf|docx|xlsx|xls|csv|txt|py|jpg|jpeg|png|webp|bmp|doc|md)',
        text,
        re.IGNORECASE,
    )
    return m.group(0) if m else None


def classify(message: str) -> tuple[str, dict]:
    """
    Classifica a mensagem e retorna (intent_type, params).
    Ordem de prioridade: intents explícitos → arquivo detectado → CHAT.
    """
    msg = message.strip()
    lower = msg.lower()

    # 1. SET_PROJECT — marcador # com caminho
    m = SET_PROJECT_PATTERN.match(msg)
    if m:
        return "SET_PROJECT", {"path": m.group(1)}

    # 2. Slash commands (prefixo /)
    if msg.startswith("/"):
        parts = msg.split(maxsplit=1)
        return "SLASH_COMMAND", {
            "command": parts[0],
            "args": parts[1] if len(parts) > 1 else "",
        }

    # 3. LIST_FILES
    for pattern in LIST_FILES_PATTERNS:
        if pattern in f" {lower} ":
            return "LIST_FILES", {}
    # bare "ls" or "dir" as entire message
    if lower.strip() in ("ls", "dir"):
        return "LIST_FILES", {}

    # 4. STORE_MEMORY
    for trigger in STORE_MEMORY_TRIGGERS:
        if trigger in lower:
            return "STORE_MEMORY", {"instruction": msg}

    # 5. DEBATE
    for trigger in DEBATE_TRIGGERS:
        if trigger in lower:
            return "DEBATE", {"topic": msg}

    # 6. SEARCH_WEB
    for trigger in SEARCH_WEB_TRIGGERS:
        if trigger in lower:
            return "SEARCH_WEB", {"query": msg}

    # 7. ATTACH / OCR / FILE_EDIT / FILE_READ — requer referência de arquivo
    file_ref = _file_ref(lower)
    if file_ref:
        ext = "." + file_ref.rsplit(".", 1)[-1]

        if ext in ATTACH_EXTENSIONS:
            return "ATTACH", {"filename": file_ref, "instruction": msg}

        if ext in OCR_EXTENSIONS:
            return "OCR", {"filename": file_ref, "instruction": msg}

        # FILE_EDIT — verbo de edição + arquivo
        for verb in FILE_EDIT_VERBS:
            if re.search(rf'\b{re.escape(verb)}\b', lower):
                return "FILE_EDIT", {"filename": file_ref, "instruction": msg}

        # FILE_READ — verbo de leitura + arquivo (ou só o nome do arquivo)
        for verb in FILE_READ_VERBS:
            if re.search(rf'\b{re.escape(verb)}\b', lower):
                return "FILE_READ", {"filename": file_ref}

        # Só nome de arquivo sem verbo → assumir leitura
        return "FILE_READ", {"filename": file_ref}

    # 8. RESUME_SESSION — referências ao passado sem arquivo nomeado
    for pattern in RESUME_SESSION_PATTERNS:
        if re.search(pattern, lower):
            return "RESUME_SESSION", {"description": msg}

    # 9. PIPELINE — verbos de geração/implementação
    for marker in PIPELINE_MARKERS:
        if re.search(rf'\b{re.escape(marker)}\b', lower):
            return "PIPELINE", {"message": msg}

    # 10. CHAT — fallback
    return "CHAT", {"message": msg}
