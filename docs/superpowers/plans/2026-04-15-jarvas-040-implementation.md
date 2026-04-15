# Jarvas 0.4.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o Jarvas em um sistema completo de aprendizado colaborativo com intent parser, guard pipeline automático, editor de arquivos, processador unificado de arquivos, memória persistente (MemPalace + Supabase) e interface web com botões de ação rápida na porta 8080.

**Architecture:** Toda mensagem passa pelo `intent_parser.py` que retorna um `Intent` tipado. O `orchestrator.py` despacha o Intent para o handler correto. Cada handler é um módulo focado com responsabilidade única. O `cli.py` e a `api.py` delegam para o orchestrator — nunca chamam handlers diretamente.

**Tech Stack:** Python 3.11+, FastAPI, Rich, prompt_toolkit, supabase-py, google-generativeai, openai (OpenRouter), pymupdf, openpyxl, python-docx, Pillow, pytesseract, concurrent.futures (stdlib)

---

## File Map

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `jarvas/context.py` | CRIAR | SessionContext dataclass — estado global da sessão |
| `jarvas/intent_parser.py` | CRIAR | Classifica mensagem em Intent tipado |
| `jarvas/guard_pipeline.py` | CRIAR | Hermes + Gemini + DeepSeek em paralelo + síntese |
| `jarvas/file_editor.py` | CRIAR | Lê e edita arquivos no disco com segurança |
| `jarvas/memory_writer.py` | CRIAR | Extrai insights e grava no MemPalace + Supabase |
| `jarvas/file_processor.py` | CRIAR | Processa PDF/Excel/Word/CSV/imagens guiado por prompt |
| `jarvas/orchestrator.py` | CRIAR | Tabela de dispatch Intent → handler |
| `jarvas/supabase_client.py` | MODIFICAR | Adicionar 4 novas funções de persistência |
| `jarvas/cli.py` | MODIFICAR | Usar orchestrator.process() em vez de dispatch direto |
| `jarvas/api.py` | MODIFICAR | Porta 8080, novos endpoints, usar orchestrator |
| `jarvas/static/chat.html` | MODIFICAR | Novo UI com botões de ação rápida |
| `tests/test_context.py` | CRIAR | Testes do SessionContext |
| `tests/test_intent_parser.py` | CRIAR | Testes de todos os tipos de Intent |
| `tests/test_guard_pipeline.py` | CRIAR | Testes do pipeline paralelo |
| `tests/test_file_editor.py` | CRIAR | Testes de leitura e edição de arquivos |
| `tests/test_memory_writer.py` | CRIAR | Testes do extrator de insights |
| `tests/test_file_processor.py` | CRIAR | Testes de extração por tipo de arquivo |
| `tests/test_orchestrator.py` | CRIAR | Testes de dispatch por intent |

---

## Task 1: SessionContext (`jarvas/context.py`)

**Files:**
- Create: `jarvas/context.py`
- Create: `tests/test_context.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_context.py
import uuid
from jarvas.context import SessionContext


def test_session_context_defaults():
    ctx = SessionContext()
    assert isinstance(ctx.session_id, str)
    assert len(ctx.session_id) == 36  # UUID format
    assert ctx.project_path is None
    assert ctx.historico == []
    assert ctx.last_pipeline_result is None
    assert ctx.last_debate_result is None


def test_session_context_custom_id():
    sid = str(uuid.uuid4())
    ctx = SessionContext(session_id=sid)
    assert ctx.session_id == sid


def test_session_context_project_path():
    ctx = SessionContext(project_path="C:/projetos/ocr")
    assert ctx.project_path == "C:/projetos/ocr"


def test_session_context_historico_isolation():
    ctx1 = SessionContext()
    ctx2 = SessionContext()
    ctx1.historico.append({"role": "user", "content": "oi"})
    assert ctx2.historico == []
```

- [ ] **Step 2: Rodar o teste e verificar que falha**

```bash
pytest tests/test_context.py -v
```
Esperado: `ModuleNotFoundError: No module named 'jarvas.context'`

- [ ] **Step 3: Implementar `jarvas/context.py`**

```python
"""Estado global de uma sessão do Jarvas."""
from __future__ import annotations
from dataclasses import dataclass, field
import uuid


@dataclass
class SessionContext:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_path: str | None = None
    historico: list[dict] = field(default_factory=list)
    last_pipeline_result: dict | None = None
    last_debate_result: dict | None = None
```

- [ ] **Step 4: Rodar o teste e verificar que passa**

```bash
pytest tests/test_context.py -v
```
Esperado: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add jarvas/context.py tests/test_context.py
git commit -m "feat: SessionContext — estado global da sessão"
```

---

## Task 2: Intent Parser (`jarvas/intent_parser.py`)

**Files:**
- Create: `jarvas/intent_parser.py`
- Create: `tests/test_intent_parser.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_intent_parser.py
from jarvas.intent_parser import parse, Intent


def test_intent_is_dataclass():
    i = Intent(type="CHAT", raw="oi")
    assert i.type == "CHAT"
    assert i.raw == "oi"
    assert i.args == {}


def test_set_project_windows_path():
    i = parse("jarvas trabalharemos em #C:/projetos/ocr")
    assert i.type == "SET_PROJECT"
    assert i.args["path"] == "C:/projetos/ocr"


def test_set_project_unix_path():
    i = parse("vamos trabalhar em #/home/user/projeto")
    assert i.type == "SET_PROJECT"
    assert i.args["path"] == "/home/user/projeto"


def test_attach_pdf():
    i = parse("processe esse arquivo relatorio.pdf e me dê um resumo")
    assert i.type == "ATTACH"
    assert "relatorio.pdf" in i.args["path"]
    assert i.args["file_type"] == "pdf"


def test_attach_excel():
    i = parse("analise a planilha dados.xlsx")
    assert i.type == "ATTACH"
    assert i.args["file_type"] == "xlsx"


def test_ocr_image():
    i = parse("ocr nota_fiscal.jpg e gere excel")
    assert i.type == "OCR"
    assert "nota_fiscal.jpg" in i.args["path"]


def test_ocr_extraia_texto():
    i = parse("extraia texto da imagem foto.png")
    assert i.type == "OCR"


def test_file_edit():
    i = parse("edite o arquivo main.py para usar snake_case")
    assert i.type == "FILE_EDIT"
    assert "main.py" in i.args["instruction"]


def test_file_edit_melhore():
    i = parse("melhore o código em utils.py")
    assert i.type == "FILE_EDIT"


def test_file_read():
    i = parse("leia o arquivo config.py")
    assert i.type == "FILE_READ"


def test_file_read_mostra():
    i = parse("mostra o arquivo router.py")
    assert i.type == "FILE_READ"


def test_debate():
    i = parse("debate sobre qual banco de dados usar")
    assert i.type == "DEBATE"
    assert "banco de dados" in i.args["topic"]


def test_debate_peca():
    i = parse("jarvas peça um debate sobre python vs javascript")
    assert i.type == "DEBATE"


def test_store_memory():
    i = parse("armazene as últimas interações")
    assert i.type == "STORE_MEMORY"
    assert i.args["scope"] == 5


def test_store_memory_guarda():
    i = parse("guarda isso no mempalace")
    assert i.type == "STORE_MEMORY"


def test_search_web():
    i = parse("pesquise sobre pytesseract no windows")
    assert i.type == "SEARCH_WEB"
    assert "pytesseract" in i.args["query"]


def test_pipeline_code():
    i = parse("escreva um script python para renomear arquivos")
    assert i.type == "PIPELINE"
    assert i.args["task_type"] == "code"


def test_pipeline_analysis():
    i = parse("analise esse trecho de código")
    assert i.type == "PIPELINE"
    assert i.args["task_type"] == "analysis"


def test_chat_fallback():
    i = parse("oi tudo bem?")
    assert i.type == "CHAT"


def test_priority_set_project_over_attach():
    # SET_PROJECT tem prioridade sobre ATTACH
    i = parse("trabalhar em #C:/projetos/dados.xlsx")
    assert i.type == "SET_PROJECT"
```

- [ ] **Step 2: Rodar o teste e verificar que falha**

```bash
pytest tests/test_intent_parser.py -v
```
Esperado: `ModuleNotFoundError: No module named 'jarvas.intent_parser'`

- [ ] **Step 3: Implementar `jarvas/intent_parser.py`**

```python
"""Classifica mensagens do usuário em Intents tipados."""
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
    """Retorna o Intent mais específico para a mensagem."""
    lower = mensagem.lower()

    # 1. SET_PROJECT — #/path ou #C:/path
    m = re.search(r'#([A-Za-z]:[/\\][^\s]+|/[^\s]+)', mensagem)
    if m:
        return Intent(type="SET_PROJECT", raw=mensagem, args={"path": m.group(1)})

    # 2. ATTACH / OCR — extensão de arquivo no texto
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

    # 8. PIPELINE — tópico técnico detectado pelo router existente
    from jarvas.router import detect_task_type
    task_type = detect_task_type(mensagem)
    if task_type != "chat":
        return Intent(type="PIPELINE", raw=mensagem, args={"task_type": task_type})

    # 9. CHAT — fallback
    return Intent(type="CHAT", raw=mensagem, args={})
```

- [ ] **Step 4: Rodar o teste e verificar que passa**

```bash
pytest tests/test_intent_parser.py -v
```
Esperado: 21 PASSED

- [ ] **Step 5: Commit**

```bash
git add jarvas/intent_parser.py tests/test_intent_parser.py
git commit -m "feat: intent parser — classifica mensagens em 10 tipos de Intent"
```

---

## Task 3: Guard Pipeline (`jarvas/guard_pipeline.py`)

**Files:**
- Create: `jarvas/guard_pipeline.py`
- Create: `tests/test_guard_pipeline.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_guard_pipeline.py
from unittest.mock import patch, MagicMock
from jarvas.context import SessionContext
from jarvas.guard_pipeline import run, run_edit


def _mock_hermes(msg, historico=None, modelo=None):
    return (f"hermes:{msg[:20]}", "mock-model")


def _mock_gemini(msg):
    return f"gemini:{msg[:20]}"


def _mock_deepseek(msg):
    return f"deepseek:{msg[:20]}"


@patch("jarvas.guard_pipeline.save_pipeline_result")
@patch("jarvas.guard_pipeline.hermes_chat", side_effect=_mock_hermes)
@patch("jarvas.guard_pipeline.gemini_chat", side_effect=_mock_gemini)
@patch("jarvas.guard_pipeline.deepseek_chat", side_effect=_mock_deepseek)
def test_run_returns_four_keys(mock_ds, mock_g, mock_h, mock_save):
    ctx = SessionContext()
    result = run("como funciona um loop?", "code", ctx)
    assert "hermes" in result
    assert "gemini" in result
    assert "deepseek" in result
    assert "sintese" in result


@patch("jarvas.guard_pipeline.save_pipeline_result")
@patch("jarvas.guard_pipeline.hermes_chat", side_effect=_mock_hermes)
@patch("jarvas.guard_pipeline.gemini_chat", side_effect=_mock_gemini)
@patch("jarvas.guard_pipeline.deepseek_chat", side_effect=_mock_deepseek)
def test_run_saves_to_context(mock_ds, mock_g, mock_h, mock_save):
    ctx = SessionContext()
    run("analise esse código", "analysis", ctx)
    assert ctx.last_pipeline_result is not None
    assert "sintese" in ctx.last_pipeline_result


@patch("jarvas.guard_pipeline.save_pipeline_result")
@patch("jarvas.guard_pipeline.hermes_chat", side_effect=_mock_hermes)
@patch("jarvas.guard_pipeline.gemini_chat", side_effect=_mock_gemini)
@patch("jarvas.guard_pipeline.deepseek_chat", side_effect=_mock_deepseek)
def test_run_calls_save(mock_ds, mock_g, mock_h, mock_save):
    ctx = SessionContext()
    run("código python", "code", ctx)
    mock_save.assert_called_once()


@patch("jarvas.guard_pipeline.hermes_chat")
def test_run_edit_strips_markdown(mock_h):
    mock_h.return_value = ("```python\ndef foo():\n    pass\n```", "model")
    result = run_edit("def foo(): pass", "adicione docstring")
    assert result == "def foo():\n    pass"


@patch("jarvas.guard_pipeline.hermes_chat")
def test_run_edit_returns_plain_code(mock_h):
    mock_h.return_value = ("def foo():\n    \"\"\"docstring\"\"\"\n    pass", "model")
    result = run_edit("def foo(): pass", "adicione docstring")
    assert "docstring" in result
```

- [ ] **Step 2: Rodar o teste e verificar que falha**

```bash
pytest tests/test_guard_pipeline.py -v
```
Esperado: `ModuleNotFoundError: No module named 'jarvas.guard_pipeline'`

- [ ] **Step 3: Implementar `jarvas/guard_pipeline.py`**

```python
"""Pipeline paralelo: Hermes + Gemini + DeepSeek → síntese."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed

from jarvas.hermes_client import chat as hermes_chat
from jarvas.guard_gemini import chat as gemini_chat
from jarvas.guard_deepseek import chat as deepseek_chat
from jarvas.supabase_client import save_pipeline_result
from jarvas.context import SessionContext


def run(mensagem: str, task_type: str, session_ctx: SessionContext) -> dict:
    """Executa os 3 modelos em paralelo e sintetiza o resultado."""
    results: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(hermes_chat, mensagem): "hermes",
            executor.submit(gemini_chat, mensagem): "gemini",
            executor.submit(deepseek_chat, mensagem): "deepseek",
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                resp = future.result()
                results[key] = resp[0] if isinstance(resp, tuple) else resp
            except Exception as e:
                results[key] = f"[erro: {e}]"

    prompt_sintese = (
        f"Você recebeu 3 perspectivas sobre: \"{mensagem}\"\n\n"
        f"Hermes: {results.get('hermes', '')}\n"
        f"Gemini: {results.get('gemini', '')}\n"
        f"DeepSeek: {results.get('deepseek', '')}\n\n"
        "Sintetize em uma resposta única, clara e objetiva. "
        "Aponte divergências relevantes se houver."
    )
    sintese_resp, _ = hermes_chat(prompt_sintese)
    results["sintese"] = sintese_resp

    save_pipeline_result(
        session_ctx.session_id, mensagem, task_type, results
    )
    session_ctx.last_pipeline_result = results
    return results


def run_edit(original_code: str, instruction: str) -> str:
    """Envia código + instrução ao Hermes. Retorna apenas o código editado."""
    prompt = (
        f"Instrução: {instruction}\n\n"
        f"Código original:\n{original_code}\n\n"
        "Retorne APENAS o código editado, sem explicações, sem markdown, "
        "sem blocos de código cercados por ```."
    )
    resp, _ = hermes_chat(prompt)
    resp = resp.strip()
    if resp.startswith("```"):
        lines = resp.splitlines()
        end = -1 if lines[-1].strip() == "```" else len(lines)
        resp = "\n".join(lines[1:end])
    return resp
```

- [ ] **Step 4: Rodar o teste e verificar que passa**

```bash
pytest tests/test_guard_pipeline.py -v
```
Esperado: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add jarvas/guard_pipeline.py tests/test_guard_pipeline.py
git commit -m "feat: guard pipeline paralelo — Hermes+Gemini+DeepSeek+síntese"
```

---

## Task 4: File Editor (`jarvas/file_editor.py`)

**Files:**
- Create: `jarvas/file_editor.py`
- Create: `tests/test_file_editor.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_file_editor.py
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from jarvas.file_editor import read_file, edit_file


def test_read_file_absolute():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                     delete=False, encoding="utf-8") as f:
        f.write("def hello(): pass\n")
        path = f.name
    try:
        content = read_file(path)
        assert "def hello" in content
    finally:
        os.unlink(path)


def test_read_file_relative_with_project_base():
    with tempfile.TemporaryDirectory() as tmpdir:
        fpath = Path(tmpdir) / "main.py"
        fpath.write_text("x = 1\n", encoding="utf-8")
        content = read_file("main.py", project_base=tmpdir)
        assert "x = 1" in content


def test_read_file_not_found():
    result = read_file("/caminho/inexistente/arquivo.py")
    assert "[erro]" in result.lower()


def test_read_file_blocks_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"
        env_path.write_text("SECRET=123\n", encoding="utf-8")
        result = read_file(str(env_path))
        assert "[erro]" in result.lower()


def test_read_file_blocks_pem():
    with tempfile.TemporaryDirectory() as tmpdir:
        pem_path = Path(tmpdir) / "cert.pem"
        pem_path.write_text("-----BEGIN CERTIFICATE-----\n", encoding="utf-8")
        result = read_file(str(pem_path))
        assert "[erro]" in result.lower()


@patch("jarvas.file_editor.save_file_edit")
@patch("jarvas.file_editor.run_edit")
def test_edit_file_writes_to_disk(mock_run_edit, mock_save):
    mock_run_edit.return_value = "def hello():\n    \"\"\"Oi.\"\"\"\n    pass\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                     delete=False, encoding="utf-8") as f:
        f.write("def hello(): pass\n")
        path = f.name
    try:
        result = edit_file(path, "adicione docstring", None, "sess-001")
        assert "diff" in result
        assert Path(path).read_text(encoding="utf-8") == mock_run_edit.return_value
    finally:
        os.unlink(path)


@patch("jarvas.file_editor.save_file_edit")
@patch("jarvas.file_editor.run_edit")
def test_edit_file_blocks_env(mock_run_edit, mock_save):
    with tempfile.TemporaryDirectory() as tmpdir:
        env = Path(tmpdir) / ".env"
        env.write_text("X=1\n", encoding="utf-8")
        result = edit_file(str(env), "edite", None, "sess-001")
        assert "error" in result
        mock_run_edit.assert_not_called()
```

- [ ] **Step 2: Rodar o teste e verificar que falha**

```bash
pytest tests/test_file_editor.py -v
```
Esperado: `ModuleNotFoundError: No module named 'jarvas.file_editor'`

- [ ] **Step 3: Implementar `jarvas/file_editor.py`**

```python
"""Lê e edita arquivos do projeto com segurança."""
from __future__ import annotations
import difflib
from pathlib import Path

from jarvas.guard_pipeline import run_edit
from jarvas.supabase_client import save_file_edit

_BLOCKED_SUFFIXES = {".env", ".key", ".pem"}
_BLOCKED_NAMES = {".env"}


def _resolve(path: str, project_base: str | None) -> Path:
    p = Path(path)
    if not p.is_absolute() and project_base:
        p = Path(project_base) / path
    return p.resolve()


def _is_blocked(p: Path) -> bool:
    return (
        p.suffix in _BLOCKED_SUFFIXES
        or p.name in _BLOCKED_NAMES
        or ".git" in p.parts
    )


def read_file(path: str, project_base: str | None = None) -> str:
    """Lê arquivo e retorna conteúdo como string."""
    p = _resolve(path, project_base)
    if _is_blocked(p):
        return f"[erro] Acesso bloqueado: {p.name}"
    if not p.exists():
        return f"[erro] Arquivo não encontrado: {p}"
    return p.read_text(encoding="utf-8")


def edit_file(
    path: str,
    instruction: str,
    project_base: str | None,
    session_id: str,
) -> dict:
    """Edita arquivo no disco usando guard_pipeline e retorna diff."""
    p = _resolve(path, project_base)
    if _is_blocked(p):
        return {"error": f"Acesso bloqueado: {p.name}"}
    if not p.exists():
        return {"error": f"Arquivo não encontrado: {p}"}

    original = p.read_text(encoding="utf-8")
    edited = run_edit(original, instruction)

    diff = "\n".join(difflib.unified_diff(
        original.splitlines(),
        edited.splitlines(),
        fromfile=f"original/{p.name}",
        tofile=f"editado/{p.name}",
        lineterm="",
    ))

    p.write_text(edited, encoding="utf-8")
    save_file_edit(session_id, str(p), instruction, original, edited, diff)

    return {"path": str(p), "diff": diff, "original": original, "edited": edited}
```

- [ ] **Step 4: Rodar o teste e verificar que passa**

```bash
pytest tests/test_file_editor.py -v
```
Esperado: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add jarvas/file_editor.py tests/test_file_editor.py
git commit -m "feat: file editor — leitura e edição segura de arquivos no disco"
```

---

## Task 5: Memory Writer (`jarvas/memory_writer.py`)

**Files:**
- Create: `jarvas/memory_writer.py`
- Create: `tests/test_memory_writer.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_memory_writer.py
import json
from unittest.mock import patch, MagicMock
from jarvas.context import SessionContext
from jarvas.memory_writer import store


def _mock_hermes_json(prompt, historico=None, modelo=None):
    payload = json.dumps({
        "acertos": ["uso de snake_case"],
        "erros": ["variável não definida"],
        "decisoes": ["usar openpyxl"],
        "padroes": ["sempre validar entrada"],
    })
    return (payload, "mock-model")


@patch("jarvas.memory_writer.save_memory_log")
@patch("jarvas.memory_writer.handle_hmem", return_value='{"id": "drawer-abc"}')
@patch("jarvas.memory_writer.hermes_chat", side_effect=_mock_hermes_json)
def test_store_calls_hmem_add(mock_h, mock_hmem, mock_save):
    ctx = SessionContext(project_path="C:/projetos/ocr")
    ctx.historico = [
        {"role": "user", "content": "como faço X?"},
        {"role": "assistant", "content": "faça Y"},
    ]
    result = store(ctx, scope=5)
    mock_hmem.assert_called_once()
    args = mock_hmem.call_args[0][0]
    assert args.startswith("add wing_code")


@patch("jarvas.memory_writer.save_memory_log")
@patch("jarvas.memory_writer.handle_hmem", return_value='{"id": "drawer-xyz"}')
@patch("jarvas.memory_writer.hermes_chat", side_effect=_mock_hermes_json)
def test_store_uses_general_room_without_project(mock_h, mock_hmem, mock_save):
    ctx = SessionContext()
    ctx.historico = [{"role": "user", "content": "oi"}]
    store(ctx)
    args = mock_hmem.call_args[0][0]
    assert "wing_user" in args
    assert "general" in args


@patch("jarvas.memory_writer.save_memory_log")
@patch("jarvas.memory_writer.handle_hmem", return_value='{"id": "d1"}')
@patch("jarvas.memory_writer.hermes_chat", side_effect=_mock_hermes_json)
def test_store_calls_save_memory_log(mock_h, mock_hmem, mock_save):
    ctx = SessionContext()
    ctx.historico = [{"role": "user", "content": "teste"}]
    store(ctx)
    mock_save.assert_called_once()


@patch("jarvas.memory_writer.save_memory_log")
@patch("jarvas.memory_writer.handle_hmem", return_value="texto sem json")
@patch("jarvas.memory_writer.hermes_chat")
def test_store_handles_bad_json_from_hermes(mock_h, mock_hmem, mock_save):
    mock_h.return_value = ("isso não é json válido", "model")
    ctx = SessionContext()
    ctx.historico = [{"role": "user", "content": "x"}]
    result = store(ctx)  # não deve lançar exceção
    assert result is not None
```

- [ ] **Step 2: Rodar o teste e verificar que falha**

```bash
pytest tests/test_memory_writer.py -v
```
Esperado: `ModuleNotFoundError: No module named 'jarvas.memory_writer'`

- [ ] **Step 3: Implementar `jarvas/memory_writer.py`**

```python
"""Extrai insights do histórico e grava no MemPalace + Supabase."""
from __future__ import annotations
import json
from pathlib import Path

from jarvas.hermes_client import chat as hermes_chat
from jarvas.mempalace_client import handle_hmem
from jarvas.supabase_client import save_memory_log
from jarvas.context import SessionContext


def store(session_ctx: SessionContext, scope: int = 5) -> str:
    """Analisa histórico recente e grava insights no MemPalace."""
    msgs = session_ctx.historico[-scope:]

    extra = ""
    if session_ctx.last_pipeline_result:
        extra += f"\nÚltimo pipeline — síntese: {session_ctx.last_pipeline_result.get('sintese', '')[:500]}"
    if session_ctx.last_debate_result:
        extra += f"\nÚltimo debate — consenso: {session_ctx.last_debate_result.get('consensus', '')[:500]}"

    prompt = (
        'Analise essas interações e extraia em JSON puro (sem markdown):\n'
        '{"acertos": [...], "erros": [...], "decisoes": [...], "padroes": [...]}\n\n'
        f"Interações:\n{json.dumps(msgs, ensure_ascii=False, indent=2)}\n{extra}"
    )

    resp, _ = hermes_chat(prompt)

    try:
        dados = json.loads(resp.strip())
    except Exception:
        dados = {"raw": resp}

    wing = "wing_code" if session_ctx.project_path else "wing_user"
    if session_ctx.project_path:
        room = Path(session_ctx.project_path).name.lower().replace(" ", "-")
    else:
        room = "general"

    content = json.dumps(dados, ensure_ascii=False)
    result = handle_hmem(f"add {wing} {room} {content}")

    drawer_id = None
    try:
        r = json.loads(result.split("\n", 1)[-1])
        drawer_id = r.get("id")
    except Exception:
        pass

    save_memory_log(session_ctx.session_id, wing, room, content, drawer_id)
    return result
```

- [ ] **Step 4: Rodar o teste e verificar que passa**

```bash
pytest tests/test_memory_writer.py -v
```
Esperado: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add jarvas/memory_writer.py tests/test_memory_writer.py
git commit -m "feat: memory writer — extrai insights e grava no MemPalace"
```

---

## Task 6: File Processor (`jarvas/file_processor.py`)

**Files:**
- Create: `jarvas/file_processor.py`
- Create: `tests/test_file_processor.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_file_processor.py
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from jarvas.file_processor import extract_content, process_file, _get_output_dir


def test_extract_txt():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                     delete=False, encoding="utf-8") as f:
        f.write("linha1\nlinha2\n")
        path = f.name
    try:
        content = extract_content(path)
        assert "linha1" in content
        assert "linha2" in content
    finally:
        os.unlink(path)


def test_extract_csv():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv",
                                     delete=False, encoding="utf-8") as f:
        f.write("nome,valor\nAlice,100\nBob,200\n")
        path = f.name
    try:
        content = extract_content(path)
        assert "Alice" in content
        assert "Bob" in content
    finally:
        os.unlink(path)


def test_extract_xlsx():
    import openpyxl
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Nome", "Valor"])
    ws.append(["Alice", 100])
    wb.save(path)
    try:
        content = extract_content(path)
        assert "Alice" in content
        assert "Nome" in content
    finally:
        os.unlink(path)


def test_unsupported_extension():
    content = extract_content("arquivo.xyz")
    assert "[erro]" in content.lower()


def test_output_dir_excel(tmp_path):
    out = _get_output_dir(".xlsx", str(tmp_path))
    assert out.name == "excel"
    assert out.exists()


def test_output_dir_images(tmp_path):
    out = _get_output_dir(".jpg", str(tmp_path))
    assert out.name == "images"


def test_output_dir_no_project():
    out = _get_output_dir(".pdf", None)
    assert out.exists()


@patch("jarvas.file_processor.save_attachment")
@patch("jarvas.file_processor.hermes_chat")
def test_process_file_txt(mock_h, mock_save, tmp_path):
    mock_h.return_value = ("Coluna1\tColuna2\nValor1\tValor2", "model")
    txt = tmp_path / "dados.txt"
    txt.write_text("dados aqui", encoding="utf-8")
    result = process_file(str(txt), "extraia em excel", str(tmp_path), "sess-1")
    assert "output_path" in result
    assert Path(result["output_path"]).exists()


@patch("jarvas.file_processor.save_attachment")
@patch("jarvas.file_processor.hermes_chat")
def test_process_file_saves_to_supabase(mock_h, mock_save, tmp_path):
    mock_h.return_value = ("resultado", "model")
    txt = tmp_path / "nota.txt"
    txt.write_text("conteúdo", encoding="utf-8")
    process_file(str(txt), "analise", str(tmp_path), "sess-2")
    mock_save.assert_called_once()
```

- [ ] **Step 2: Rodar o teste e verificar que falha**

```bash
pytest tests/test_file_processor.py -v
```
Esperado: `ModuleNotFoundError: No module named 'jarvas.file_processor'`

- [ ] **Step 3: Instalar dependências necessárias**

```bash
pip install pymupdf openpyxl python-docx Pillow pytesseract
```

- [ ] **Step 4: Implementar `jarvas/file_processor.py`**

```python
"""Processa arquivos (PDF/Excel/Word/CSV/imagem) guiado pelo prompt do usuário."""
from __future__ import annotations
import csv as _csv
from pathlib import Path

from jarvas.supabase_client import save_attachment

_OUTPUT_BASE = "jarvas_outputs"

_TYPE_FOLDERS: dict[str, str] = {
    ".xlsx": "excel", ".xls": "excel",
    ".csv": "csv",
    ".pdf": "pdf",
    ".docx": "docs", ".txt": "docs",
    ".jpg": "images", ".jpeg": "images", ".png": "images",
}


def _get_output_dir(ext: str, project_base: str | None) -> Path:
    folder = _TYPE_FOLDERS.get(ext.lower(), "misc")
    base = Path(project_base) if project_base else Path.home()
    out = base / _OUTPUT_BASE / folder
    out.mkdir(parents=True, exist_ok=True)
    return out


def extract_content(path: str) -> str:
    """Extrai conteúdo textual do arquivo conforme tipo."""
    p = Path(path)
    if not p.exists():
        return f"[erro] arquivo não encontrado: {path}"
    ext = p.suffix.lower()

    if ext == ".pdf":
        import fitz
        doc = fitz.open(str(p))
        return "\n".join(page.get_text() for page in doc)

    if ext in (".xlsx", ".xls"):
        import openpyxl
        wb = openpyxl.load_workbook(str(p), read_only=True, data_only=True)
        ws = wb.active
        rows = [
            "\t".join("" if c is None else str(c) for c in row)
            for row in ws.iter_rows(values_only=True)
        ]
        return "\n".join(rows)

    if ext == ".csv":
        with open(str(p), newline="", encoding="utf-8-sig") as f:
            reader = _csv.reader(f)
            return "\n".join("\t".join(row) for row in reader)

    if ext == ".docx":
        from docx import Document
        doc = Document(str(p))
        return "\n".join(para.text for para in doc.paragraphs)

    if ext == ".txt":
        return p.read_text(encoding="utf-8")

    if ext in (".jpg", ".jpeg", ".png"):
        import pytesseract
        from PIL import Image
        img = Image.open(str(p))
        return pytesseract.image_to_string(img, lang="por+eng")

    return f"[erro] tipo não suportado: {ext}"


def _write_output(data: str, source_path: str, project_base: str | None,
                  output_format: str) -> str:
    source = Path(source_path)
    out_dir = _get_output_dir(f".{output_format}", project_base)
    out_path = out_dir / f"{source.stem}_resultado.{output_format}"

    if output_format == "xlsx":
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        for i, line in enumerate(data.splitlines(), start=1):
            cols = line.split("\t") if "\t" in line else [line]
            for j, val in enumerate(cols, start=1):
                ws.cell(row=i, column=j, value=val)
        wb.save(str(out_path))
    else:
        out_path.write_text(data, encoding="utf-8")

    return str(out_path)


def process_file(
    path: str,
    instruction: str,
    project_base: str | None,
    session_id: str,
) -> dict:
    """Extrai conteúdo do arquivo, processa com IA e salva resultado."""
    from jarvas.hermes_client import chat as hermes_chat

    content = extract_content(path)
    if content.startswith("[erro]"):
        return {"error": content}

    prompt = (
        f"Arquivo: {Path(path).name}\n"
        f"Conteúdo extraído:\n{content[:8000]}\n\n"
        f"Instrução: {instruction}\n\n"
        "Execute a instrução. Para dados tabulares, use formato TSV "
        "(colunas separadas por tab) para facilitar exportação."
    )
    resp, _ = hermes_chat(prompt)

    instr_lower = instruction.lower()
    if "excel" in instr_lower or "xlsx" in instr_lower:
        out_format = "xlsx"
    elif "csv" in instr_lower:
        out_format = "csv"
    else:
        out_format = "txt"

    out_path = _write_output(resp, path, project_base, out_format)

    save_attachment(
        session_id,
        Path(path).name,
        Path(path).suffix.lstrip("."),
        content[:2000],
        resp[:2000],
    )

    return {
        "output_path": out_path,
        "summary": resp[:500],
        "file_type": Path(path).suffix,
    }
```

- [ ] **Step 5: Rodar o teste e verificar que passa**

```bash
pytest tests/test_file_processor.py -v
```
Esperado: 9 PASSED (os testes de OCR/PDF requerem Tesseract e pymupdf instalados)

- [ ] **Step 6: Commit**

```bash
git add jarvas/file_processor.py tests/test_file_processor.py
git commit -m "feat: file processor unificado — PDF/Excel/Word/CSV/imagem + saída em pastas"
```

---

## Task 7: Supabase — Novas Funções (`jarvas/supabase_client.py`)

**Files:**
- Modify: `jarvas/supabase_client.py`

> **ANTES DE IMPLEMENTAR:** Execute o SQL abaixo no Supabase SQL Editor do projeto `hgwrmzwebhhqzippjyoe`:

```sql
CREATE TABLE pipeline_results (
  id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  session_id   text        NOT NULL,
  user_message text        NOT NULL,
  task_type    text,
  hermes       text,
  gemini       text,
  deepseek     text,
  sintese      text,
  created_at   timestamptz DEFAULT now()
);

CREATE TABLE file_edits (
  id               uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  session_id       text        NOT NULL,
  file_path        text        NOT NULL,
  instruction      text,
  original_content text,
  edited_content   text,
  diff             text,
  created_at       timestamptz DEFAULT now()
);

CREATE TABLE attachments (
  id                uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  session_id        text        NOT NULL,
  file_name         text        NOT NULL,
  file_type         text,
  extracted_content text,
  analysis          text,
  created_at        timestamptz DEFAULT now()
);

CREATE TABLE memory_logs (
  id         uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  session_id text        NOT NULL,
  wing       text,
  room       text,
  content    text,
  drawer_id  text,
  created_at timestamptz DEFAULT now()
);
```

- [ ] **Step 1: Adicionar as 4 funções ao final de `jarvas/supabase_client.py`**

```python
def save_pipeline_result(
    session_id: str,
    user_message: str,
    task_type: str,
    results: dict,
) -> None:
    """Persiste resultado completo do guard pipeline."""
    try:
        _get_client().table("pipeline_results").insert({
            "session_id": session_id,
            "user_message": user_message,
            "task_type": task_type,
            "hermes": results.get("hermes"),
            "gemini": results.get("gemini"),
            "deepseek": results.get("deepseek"),
            "sintese": results.get("sintese"),
        }).execute()
    except Exception as e:
        print(f"[warn] pipeline_result não salvo: {e}")


def save_file_edit(
    session_id: str,
    file_path: str,
    instruction: str,
    original: str,
    edited: str,
    diff: str,
) -> None:
    """Persiste uma edição de arquivo."""
    try:
        _get_client().table("file_edits").insert({
            "session_id": session_id,
            "file_path": file_path,
            "instruction": instruction,
            "original_content": original,
            "edited_content": edited,
            "diff": diff,
        }).execute()
    except Exception as e:
        print(f"[warn] file_edit não salvo: {e}")


def save_attachment(
    session_id: str,
    file_name: str,
    file_type: str,
    extracted_content: str,
    analysis: str,
) -> None:
    """Persiste um anexo processado."""
    try:
        _get_client().table("attachments").insert({
            "session_id": session_id,
            "file_name": file_name,
            "file_type": file_type,
            "extracted_content": extracted_content,
            "analysis": analysis,
        }).execute()
    except Exception as e:
        print(f"[warn] attachment não salvo: {e}")


def save_memory_log(
    session_id: str,
    wing: str,
    room: str,
    content: str,
    drawer_id: str | None,
) -> None:
    """Persiste um registro de memória gravada no MemPalace."""
    try:
        _get_client().table("memory_logs").insert({
            "session_id": session_id,
            "wing": wing,
            "room": room,
            "content": content,
            "drawer_id": drawer_id,
        }).execute()
    except Exception as e:
        print(f"[warn] memory_log não salvo: {e}")
```

- [ ] **Step 2: Verificar que os testes existentes continuam passando**

```bash
pytest tests/ -v -k "supabase"
```
Esperado: todos os testes existentes do supabase_client passam

- [ ] **Step 3: Commit**

```bash
git add jarvas/supabase_client.py
git commit -m "feat: supabase — pipeline_results, file_edits, attachments, memory_logs"
```

---

## Task 8: Orchestrator (`jarvas/orchestrator.py`)

**Files:**
- Create: `jarvas/orchestrator.py`
- Create: `tests/test_orchestrator.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_orchestrator.py
from unittest.mock import patch, MagicMock
from jarvas.context import SessionContext
from jarvas.orchestrator import process


@patch("jarvas.orchestrator.handle_chat", return_value="chat ok")
def test_process_chat(mock_h):
    ctx = SessionContext()
    result = process("oi tudo bem?", ctx)
    assert result == "chat ok"
    mock_h.assert_called_once()


@patch("jarvas.orchestrator.handle_pipeline", return_value="pipeline ok")
def test_process_pipeline(mock_h):
    ctx = SessionContext()
    result = process("escreva um script python", ctx)
    assert result == "pipeline ok"


@patch("jarvas.orchestrator.handle_debate", return_value="debate ok")
def test_process_debate(mock_h):
    ctx = SessionContext()
    result = process("debate sobre sql vs nosql", ctx)
    assert result == "debate ok"


@patch("jarvas.orchestrator.handle_file_read", return_value="leitura ok")
def test_process_file_read(mock_h):
    ctx = SessionContext()
    result = process("leia o arquivo main.py", ctx)
    assert result == "leitura ok"


@patch("jarvas.orchestrator.handle_file_edit", return_value="edição ok")
def test_process_file_edit(mock_h):
    ctx = SessionContext()
    result = process("edite o arquivo utils.py para snake_case", ctx)
    assert result == "edição ok"


@patch("jarvas.orchestrator.handle_set_project", return_value="projeto ok")
def test_process_set_project(mock_h):
    ctx = SessionContext()
    result = process("trabalhar em #C:/projetos/ocr", ctx)
    assert result == "projeto ok"


@patch("jarvas.orchestrator.handle_store_memory", return_value="memória ok")
def test_process_store_memory(mock_h):
    ctx = SessionContext()
    result = process("armazene as últimas interações", ctx)
    assert result == "memória ok"


@patch("jarvas.orchestrator.handle_file_process", return_value="arquivo ok")
def test_process_attach(mock_h):
    ctx = SessionContext()
    result = process("analise o arquivo relatorio.pdf", ctx)
    assert result == "arquivo ok"


@patch("jarvas.orchestrator.handle_search_web", return_value="web ok")
def test_process_search_web(mock_h):
    ctx = SessionContext()
    result = process("pesquise sobre pytesseract", ctx)
    assert result == "web ok"
```

- [ ] **Step 2: Rodar o teste e verificar que falha**

```bash
pytest tests/test_orchestrator.py -v
```
Esperado: `ModuleNotFoundError: No module named 'jarvas.orchestrator'`

- [ ] **Step 3: Implementar `jarvas/orchestrator.py`**

```python
"""Despacha Intents para handlers. Ponto central do Jarvas 0.4.0."""
from __future__ import annotations
import re

from jarvas.intent_parser import parse, Intent
from jarvas.context import SessionContext


def process(mensagem: str, session_ctx: SessionContext) -> str:
    """Classifica a mensagem e executa o handler correto."""
    intent = parse(mensagem, session_ctx.project_path)
    handler = _HANDLERS.get(intent.type, handle_chat)
    return handler(intent, session_ctx)


# ─── Handlers ────────────────────────────────────────────────────────────────

def handle_chat(intent: Intent, ctx: SessionContext) -> str:
    from jarvas.hermes_client import chat as hermes_chat
    from jarvas.supabase_client import save_message
    from jarvas.router import detect_task_type

    resposta, modelo = hermes_chat(intent.raw, historico=ctx.historico)
    ctx.historico.append({"role": "user", "content": intent.raw})
    ctx.historico.append({"role": "assistant", "content": resposta})
    try:
        tipo = detect_task_type(intent.raw)
        save_message(ctx.session_id, "user", intent.raw, task_type=tipo)
        save_message(ctx.session_id, "assistant", resposta, model=modelo, task_type=tipo)
    except Exception:
        pass
    return resposta


def handle_pipeline(intent: Intent, ctx: SessionContext) -> str:
    from jarvas.guard_pipeline import run

    result = run(intent.raw, intent.args["task_type"], ctx)
    ctx.historico.append({"role": "user", "content": intent.raw})
    ctx.historico.append({"role": "assistant", "content": result["sintese"]})
    return result["sintese"]


def handle_debate(intent: Intent, ctx: SessionContext) -> str:
    from jarvas.debate import run_debate, format_debate_result

    topic = intent.args.get("topic", intent.raw)
    resultado = run_debate(topic)
    ctx.last_debate_result = resultado
    ctx.historico.append({"role": "user", "content": intent.raw})
    ctx.historico.append({"role": "assistant", "content": resultado["consensus"]})
    return format_debate_result(resultado)


def handle_file_read(intent: Intent, ctx: SessionContext) -> str:
    from jarvas.file_editor import read_file
    import re

    m = re.search(r'[\w./\\:-]+\.\w+', intent.raw)
    path = m.group(0) if m else intent.raw
    content = read_file(path, ctx.project_path)
    return f"**Arquivo:** `{path}`\n\n```\n{content}\n```"


def handle_file_edit(intent: Intent, ctx: SessionContext) -> str:
    from jarvas.file_editor import edit_file
    import re

    m = re.search(r'[\w./\\:-]+\.\w+', intent.raw)
    path = m.group(0) if m else ""
    if not path:
        return "[erro] Não encontrei o nome do arquivo na mensagem."
    result = edit_file(path, intent.args["instruction"], ctx.project_path, ctx.session_id)
    if "error" in result:
        return f"[erro] {result['error']}"
    return f"**Arquivo editado:** `{result['path']}`\n\n```diff\n{result['diff']}\n```"


def handle_set_project(intent: Intent, ctx: SessionContext) -> str:
    path = intent.args["path"]
    ctx.project_path = path
    return f"Projeto definido: `{path}`"


def handle_store_memory(intent: Intent, ctx: SessionContext) -> str:
    from jarvas.memory_writer import store

    scope = intent.args.get("scope", 5)
    return store(ctx, scope=scope)


def handle_file_process(intent: Intent, ctx: SessionContext) -> str:
    from jarvas.file_processor import process_file

    path = intent.args.get("path", "")
    result = process_file(path, intent.raw, ctx.project_path, ctx.session_id)
    if "error" in result:
        return f"[erro] {result['error']}"
    return (
        f"**Arquivo processado:** `{result['output_path']}`\n\n"
        f"**Resumo:** {result['summary']}"
    )


def handle_search_web(intent: Intent, ctx: SessionContext) -> str:
    from jarvas.guard_gemini import web_search

    query = intent.args.get("query", intent.raw)
    return web_search(query)


_HANDLERS = {
    "CHAT":         handle_chat,
    "PIPELINE":     handle_pipeline,
    "DEBATE":       handle_debate,
    "FILE_READ":    handle_file_read,
    "FILE_EDIT":    handle_file_edit,
    "SET_PROJECT":  handle_set_project,
    "STORE_MEMORY": handle_store_memory,
    "ATTACH":       handle_file_process,
    "OCR":          handle_file_process,
    "SEARCH_WEB":   handle_search_web,
}
```

- [ ] **Step 4: Rodar o teste e verificar que passa**

```bash
pytest tests/test_orchestrator.py -v
```
Esperado: 9 PASSED

- [ ] **Step 5: Commit**

```bash
git add jarvas/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: orchestrator — tabela de dispatch Intent→handler"
```

---

## Task 9: Atualizar CLI (`jarvas/cli.py`)

**Files:**
- Modify: `jarvas/cli.py`

- [ ] **Step 1: Substituir `_processar_mensagem` para usar orchestrator**

Localize a função `_processar_mensagem` (linha ~23) e substitua por:

```python
# Adicionar no topo do arquivo, junto com os outros imports:
from jarvas.context import SessionContext
from jarvas.orchestrator import process as orchestrator_process

# Substituir a variável global _historico e _session_id por:
_ctx = SessionContext()

# Substituir a função _processar_mensagem inteira por:
def _processar_mensagem(mensagem: str) -> None:
    """Processa uma mensagem. Slash commands vão para dispatch, resto para orchestrator."""
    from jarvas.commands import dispatch

    if mensagem.strip().startswith("/"):
        resultado = dispatch(mensagem.strip(), _ctx.historico)
        if resultado is not None:
            console.print(resultado)
        return

    try:
        resposta = orchestrator_process(mensagem, _ctx)
        modelo = "jarvas"
        _exibir_resposta(resposta, modelo)
    except Exception as e:
        console.print(f"[red]Erro:[/red] {e}")
```

- [ ] **Step 2: Atualizar `rodar_interativo` para usar `_ctx.historico` no `continuar`**

Localize onde `_historico.extend(carregado)` é chamado e substitua por `_ctx.historico.extend(carregado)`.

- [ ] **Step 3: Atualizar `--version` para `0.4.0`**

```python
parser.add_argument("--version", action="version", version="jarvas 0.4.0")
```

- [ ] **Step 4: Rodar smoke test no terminal**

```bash
python -m jarvas --version
```
Esperado: `jarvas 0.4.0`

```bash
python -m jarvas "oi tudo bem?"
```
Esperado: resposta do Hermes via orchestrator

- [ ] **Step 5: Commit**

```bash
git add jarvas/cli.py
git commit -m "feat: cli usa orchestrator — todas as mensagens roteadas por intent"
```

---

## Task 10: Atualizar API (`jarvas/api.py`)

**Files:**
- Modify: `jarvas/api.py`

- [ ] **Step 1: Alterar porta padrão para 8080**

Localize a linha com `parsed.port` e o argumento `--port` e atualize:

```python
# Em cli.py (já existe):
parser.add_argument("--port", type=int, default=8080, help="Porta do servidor managed (default: 8080)")
```

- [ ] **Step 2: Adicionar novos endpoints em `jarvas/api.py`**

Adicionar após o endpoint `/debate` existente:

```python
from jarvas.context import SessionContext as _SessionContext

# Sessão web compartilhada (uma por processo)
_web_ctx = _SessionContext()


class FileReadRequest(BaseModel):
    path: str


class FileEditRequest(BaseModel):
    path: str
    instruction: str


class MemoryRequest(BaseModel):
    scope: int = 5


class FileProcessRequest(BaseModel):
    path: str
    instruction: str


class ProjectRequest(BaseModel):
    path: str


@app.post("/pipeline")
async def pipeline(req: ChatRequest):
    """Guard pipeline completo: Hermes + Gemini + DeepSeek + síntese."""
    from jarvas.guard_pipeline import run
    from jarvas.router import detect_task_type
    task_type = detect_task_type(req.mensagem)
    result = run(req.mensagem, task_type, _web_ctx)
    return result


@app.post("/file/read")
async def file_read(req: FileReadRequest):
    """Lê arquivo do projeto."""
    from jarvas.file_editor import read_file
    content = read_file(req.path, _web_ctx.project_path)
    return {"content": content, "path": req.path}


@app.post("/file/edit")
async def file_edit(req: FileEditRequest):
    """Edita arquivo no disco."""
    from jarvas.file_editor import edit_file
    result = edit_file(req.path, req.instruction, _web_ctx.project_path, _web_ctx.session_id)
    return result


@app.post("/memory/store")
async def memory_store(req: MemoryRequest):
    """Grava insights no MemPalace."""
    from jarvas.memory_writer import store
    result = store(_web_ctx, scope=req.scope)
    return {"result": result}


@app.post("/attach")
async def attach(req: FileProcessRequest):
    """Processa anexo guiado por instrução."""
    from jarvas.file_processor import process_file
    result = process_file(req.path, req.instruction, _web_ctx.project_path, _web_ctx.session_id)
    return result


@app.post("/context/project")
async def set_project(req: ProjectRequest):
    """Define o projeto atual da sessão web."""
    _web_ctx.project_path = req.path
    return {"project_path": req.path}


@app.get("/context")
async def get_context():
    """Retorna estado atual da sessão web."""
    return {
        "session_id": _web_ctx.session_id,
        "project_path": _web_ctx.project_path,
        "historico_count": len(_web_ctx.historico),
    }
```

- [ ] **Step 3: Atualizar versão na API**

```python
app = FastAPI(title="Jarvas API", version="0.4.0", lifespan=lifespan)
```

- [ ] **Step 4: Atualizar `POST /chat` para usar orchestrator**

```python
@app.post("/chat")
async def chat(req: ChatRequest):
    """Chat principal — roteado pelo orchestrator."""
    import asyncio as _asyncio
    from jarvas.orchestrator import process as orchestrator_process

    _web_ctx.historico = req.historico or []
    resposta = orchestrator_process(req.mensagem, _web_ctx)

    if len(_web_ctx.historico) >= 4:
        from jarvas.miners.conversation_miner import mine
        _asyncio.create_task(_asyncio.to_thread(mine, _web_ctx.historico))

    return {"resposta": resposta, "session_id": _web_ctx.session_id}
```

- [ ] **Step 5: Rodar o servidor e verificar health**

```bash
python -m jarvas --managed
```
Em outro terminal:
```bash
curl http://localhost:8080/health
```
Esperado: `{"status": "ok", "version": "0.1.0"}` (ou similar sem erro 500)

- [ ] **Step 6: Commit**

```bash
git add jarvas/api.py
git commit -m "feat: api porta 8080, novos endpoints pipeline/file/memory/attach/context"
```

---

## Task 11: Web UI (`jarvas/static/chat.html`)

**Files:**
- Modify/Create: `jarvas/static/chat.html`

- [ ] **Step 1: Verificar se `jarvas/static/` existe**

```bash
ls jarvas/static/
```
Se não existir: `mkdir jarvas/static`

- [ ] **Step 2: Criar/substituir `jarvas/static/chat.html`**

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Jarvas 0.4.0</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', sans-serif; background: #0f0f0f; color: #e0e0e0; height: 100vh; display: flex; flex-direction: column; }

    /* Header */
    #header { background: #1a1a2e; padding: 10px 16px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #2a2a4a; }
    #header h1 { font-size: 1.1rem; color: #7eb8f7; }
    #status-dot { width: 10px; height: 10px; border-radius: 50%; background: #4caf50; display: inline-block; margin-right: 6px; }
    #project-label { font-size: 0.75rem; color: #888; }

    /* Messages */
    #messages { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
    .msg { max-width: 80%; padding: 10px 14px; border-radius: 12px; line-height: 1.5; font-size: 0.9rem; }
    .msg.user { background: #1e3a5f; align-self: flex-end; border-bottom-right-radius: 4px; }
    .msg.jarvas { background: #1a1a2e; align-self: flex-start; border-bottom-left-radius: 4px; border-left: 3px solid #7eb8f7; }
    .msg.jarvas .label { font-size: 0.75rem; color: #7eb8f7; margin-bottom: 4px; }
    .msg.jarvas .details-btn { font-size: 0.72rem; color: #888; cursor: pointer; margin-top: 6px; display: inline-block; }
    .msg.jarvas .details-btn:hover { color: #aaa; }
    .details-panel { display: none; margin-top: 8px; font-size: 0.78rem; color: #aaa; background: #111; padding: 8px; border-radius: 6px; }
    .details-panel.open { display: block; }
    pre { white-space: pre-wrap; word-break: break-word; }

    /* Action buttons */
    #actions { background: #111; padding: 8px 12px; display: flex; flex-wrap: wrap; gap: 6px; border-top: 1px solid #222; }
    .action-btn { font-size: 0.75rem; padding: 4px 10px; border-radius: 20px; border: 1px solid #333; background: #1a1a2e; color: #bbb; cursor: pointer; transition: all 0.15s; }
    .action-btn:hover { background: #2a2a4e; color: #fff; border-color: #7eb8f7; }

    /* Input area */
    #input-area { background: #111; padding: 10px 12px; display: flex; gap: 8px; border-top: 1px solid #222; }
    #msg-input { flex: 1; background: #1a1a2e; border: 1px solid #333; border-radius: 8px; padding: 8px 12px; color: #e0e0e0; font-size: 0.9rem; outline: none; resize: none; }
    #msg-input:focus { border-color: #7eb8f7; }
    #send-btn { background: #1e3a5f; border: none; border-radius: 8px; padding: 8px 16px; color: #7eb8f7; cursor: pointer; font-size: 0.9rem; transition: background 0.15s; }
    #send-btn:hover { background: #2a4f7f; }
  </style>
</head>
<body>

<div id="header">
  <h1><span id="status-dot"></span>Jarvas <span style="font-size:0.8rem;color:#888">v0.4.0</span></h1>
  <span id="project-label">nenhum projeto definido</span>
</div>

<div id="messages"></div>

<div id="actions">
  <button class="action-btn" onclick="quickAction('analise o código: ')">🛡️ Pipeline</button>
  <button class="action-btn" onclick="quickAction('debate sobre: ')">⚔️ Debate</button>
  <button class="action-btn" onclick="quickAction('armazene as últimas interações')">💾 Armazene</button>
  <button class="action-btn" onclick="quickAction('#')">📁 Projeto</button>
  <button class="action-btn" onclick="quickAction('leia o arquivo: ')">📄 Ler Arquivo</button>
  <button class="action-btn" onclick="quickAction('edite o arquivo: ')">✏️ Editar</button>
  <button class="action-btn" onclick="pickFile()">📎 Anexar</button>
  <button class="action-btn" onclick="quickAction('ocr: ')">🔍 OCR→XLS</button>
  <button class="action-btn" onclick="quickAction('pesquise: ')">🌐 Web Search</button>
</div>

<div id="input-area">
  <textarea id="msg-input" rows="1" placeholder="Digite sua mensagem..." onkeydown="handleKey(event)"></textarea>
  <button id="send-btn" onclick="sendMessage()">Enviar</button>
</div>

<input type="file" id="file-picker" style="display:none" onchange="insertFilePath(event)">

<script>
  const API = 'http://localhost:8080';
  let historico = [];

  async function sendMessage() {
    const input = document.getElementById('msg-input');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    input.style.height = 'auto';

    appendMsg('user', text);

    // Detecta SET_PROJECT
    const projMatch = text.match(/#([A-Za-z]:[/\\][^\s]+|\/[^\s]+)/);
    if (projMatch) {
      await fetch(`${API}/context/project`, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({path: projMatch[1]})
      });
      document.getElementById('project-label').textContent = '📁 ' + projMatch[1];
    }

    const loader = appendLoader();
    try {
      const res = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({mensagem: text, historico})
      });
      const data = await res.json();
      loader.remove();

      historico.push({role:'user', content: text});
      historico.push({role:'assistant', content: data.resposta});

      // Se vier pipeline_result (futuro), mostra detalhes
      appendJarvasMsg(data.resposta, data.pipeline_result || null);
    } catch(e) {
      loader.remove();
      appendMsg('jarvas', `[erro de conexão: ${e.message}]`);
    }
  }

  function appendMsg(role, text) {
    const div = document.createElement('div');
    div.className = `msg ${role}`;
    div.innerHTML = `<pre>${escapeHtml(text)}</pre>`;
    document.getElementById('messages').appendChild(div);
    scrollBottom();
    return div;
  }

  function appendJarvasMsg(text, pipeline) {
    const div = document.createElement('div');
    div.className = 'msg jarvas';
    let html = `<div class="label">Jarvas</div><pre>${escapeHtml(text)}</pre>`;
    if (pipeline) {
      const id = 'det_' + Date.now();
      html += `<span class="details-btn" onclick="toggleDetails('${id}')">▼ Ver detalhes (Hermes / Gemini / DeepSeek)</span>`;
      html += `<div class="details-panel" id="${id}">`;
      html += `<b>Hermes:</b><pre>${escapeHtml(pipeline.hermes||'')}</pre>`;
      html += `<b>Gemini:</b><pre>${escapeHtml(pipeline.gemini||'')}</pre>`;
      html += `<b>DeepSeek:</b><pre>${escapeHtml(pipeline.deepseek||'')}</pre>`;
      html += `</div>`;
    }
    div.innerHTML = html;
    document.getElementById('messages').appendChild(div);
    scrollBottom();
  }

  function appendLoader() {
    const div = document.createElement('div');
    div.className = 'msg jarvas';
    div.innerHTML = '<div class="label">Jarvas</div><span style="color:#555">pensando...</span>';
    document.getElementById('messages').appendChild(div);
    scrollBottom();
    return div;
  }

  function toggleDetails(id) {
    document.getElementById(id).classList.toggle('open');
  }

  function quickAction(template) {
    const input = document.getElementById('msg-input');
    input.value = template;
    input.focus();
    input.setSelectionRange(template.length, template.length);
  }

  function pickFile() {
    document.getElementById('file-picker').click();
  }

  function insertFilePath(event) {
    const file = event.target.files[0];
    if (!file) return;
    const input = document.getElementById('msg-input');
    input.value = `${file.path || file.name} `;
    input.focus();
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
    // Auto-resize
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function scrollBottom() {
    const msgs = document.getElementById('messages');
    msgs.scrollTop = msgs.scrollHeight;
  }

  // Mensagem de boas-vindas
  appendJarvasMsg('Olá! Sou o Jarvas 0.4.0. Use os botões acima para acionar comandos ou simplesmente escreva sua mensagem.', null);
</script>
</body>
</html>
```

- [ ] **Step 3: Iniciar o servidor e abrir o browser**

```bash
python -m jarvas --managed
```
Abrir: `http://localhost:8080`

- [ ] **Step 4: Testar golden path**

1. Digitar "oi" → recebe resposta do Jarvas
2. Clicar em ⚔️ Debate → digitar tópico → ver consenso
3. Clicar em 💾 Armazene → ver confirmação do MemPalace
4. Clicar em 📁 Projeto → digitar `#C:/seu/projeto` → label atualiza no header

- [ ] **Step 5: Commit**

```bash
git add jarvas/static/chat.html
git commit -m "feat: web UI porta 8080 — chat com botões de ação rápida e painel de detalhes"
```

---

## Task 12: Versão Final e Testes Completos

**Files:**
- Modify: `jarvas/api.py` (health endpoint)

- [ ] **Step 1: Rodar toda a suite de testes**

```bash
pytest tests/ -v
```
Esperado: todos os testes passam (mínimo os 60+ testes dos módulos novos)

- [ ] **Step 2: Smoke test terminal**

```bash
python -m jarvas "debate sobre python vs javascript"
```
Esperado: debate executado via orchestrator, consenso exibido

```bash
python -m jarvas "armazene as últimas interações"
```
Esperado: MemPalace status retornado

- [ ] **Step 3: Smoke test API**

```bash
python -m jarvas --managed &
curl -X POST http://localhost:8080/pipeline \
  -H "Content-Type: application/json" \
  -d '{"mensagem": "escreva uma função python hello world"}'
```
Esperado: JSON com `hermes`, `gemini`, `deepseek`, `sintese`

- [ ] **Step 4: Atualizar health endpoint**

```python
@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.4.0"}
```

- [ ] **Step 5: Commit final**

```bash
git add -A
git commit -m "feat: Jarvas 0.4.0 — release oficial

- Intent parser com 10 tipos de intenção
- Orchestrator com tabela de dispatch
- Guard pipeline paralelo (Hermes+Gemini+DeepSeek+síntese)
- File editor com segurança e diff
- Memory writer → MemPalace + Supabase
- File processor unificado (PDF/Excel/Word/CSV/imagem)
- Web UI porta 8080 com botões de ação rápida
- 4 novas tabelas Supabase

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review

### Cobertura do Spec

| Requisito do Spec | Task |
|---|---|
| Intent Parser com 10 tipos | Task 2 |
| SessionContext | Task 1 |
| Guard Pipeline paralelo + síntese | Task 3 |
| Salvar pipeline no Supabase | Task 3 + 7 |
| File Editor (leitura + edição + diff) | Task 4 |
| Bloqueio de .env/.pem | Task 4 |
| Memory Writer → MemPalace | Task 5 |
| Memory Writer → Supabase | Task 5 + 7 |
| File Processor (PDF/Excel/Word/CSV/imagem) | Task 6 |
| Saída organizada por pastas (jarvas_outputs/) | Task 6 |
| Processamento guiado por prompt | Task 6 |
| 4 novas tabelas Supabase | Task 7 |
| Orchestrator dispatch | Task 8 |
| CLI usa orchestrator | Task 9 |
| API porta 8080, novos endpoints | Task 10 |
| Web UI com botões de ação rápida | Task 11 |
| Versão 0.4.0 | Task 9 + 10 + 12 |

**Todos os requisitos do spec estão cobertos.**

### Consistência de tipos

- `SessionContext` definido na Task 1 e usado nas Tasks 3, 4, 5, 6, 8, 9, 10 — consistente
- `Intent.args["task_type"]` definido no parser (Task 2) e consumido no pipeline (Task 3) — consistente
- `save_pipeline_result(session_id, user_message, task_type, results: dict)` definido Task 7, chamado Task 3 — consistente
- `run_edit(original, instruction)` definido Task 3, importado Task 4 — consistente
