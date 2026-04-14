# Plano de Implementação — Jarvas

**Objetivo:** Construir o Jarvas — assistente de IA distribuído com Hermes (OpenRouter), guardas Gemini + DeepSeek, persistência no Supabase e organização de memória via MemPalace — acessível pelo PS7 e VSCode.

**Arquitetura:** Jarvas é um novo pacote Python que envolve o `hermes-agent` (já instalado) e adiciona guardas, banco Supabase e um despachante de comandos customizados. O binário `hermes` cuida do backbone de IA; Jarvas pré-processa os comandos e pós-processa os resultados. Todos os dados persistem no Supabase.

**Tecnologias:** Python 3.13, openai (cliente OpenRouter), google-generativeai, supabase-py, mempalace (instalação local), prompt_toolkit (REPL), rich (formatação de saída)

---

## Mapa de Arquivos

| Arquivo | Responsabilidade |
|---------|-----------------|
| `pyproject.toml` | Definição do pacote, instala o comando `jarvas` |
| `jarvas/__init__.py` | Marcador de pacote Python |
| `jarvas/cli.py` | Ponto de entrada: loop REPL, lê input, roteia comandos |
| `jarvas/commands.py` | Registro de slash commands: mapeia `/g`, `/d`, `/debate`, `/hopen`, `/hmem` |
| `jarvas/router.py` | Seleção de modelo por palavra-chave para chamadas ao Hermes |
| `jarvas/hermes_client.py` | Wrapper da API OpenRouter — envia chat ao modelo selecionado |
| `jarvas/supabase_client.py` | Leitura/escrita no Supabase: salvar mensagens, carregar contexto de sessão |
| `jarvas/guard_gemini.py` | Guarda Gemini: chat direto + processamento de memória em segundo plano |
| `jarvas/guard_deepseek.py` | Guarda DeepSeek: chat direto + processamento de memória em segundo plano |
| `jarvas/debate.py` | Orquestra debate multi-agente entre os guardas, retorna consenso |
| `jarvas/mempalace_client.py` | Envolve a API Python do MemPalace para os comandos `/hmem` |
| `tests/test_router.py` | Testes unitários para a lógica de roteamento por palavra-chave |
| `tests/test_commands.py` | Testes unitários para o parser de slash commands |
| `tests/test_debate.py` | Testes unitários para a orquestração do debate |

---

## Fase 1 — CLI Principal + Roteamento Hermes

### Tarefa 1: Estrutura do projeto + comando `jarvas`

**Arquivos:**
- Criar: `pyproject.toml`
- Criar: `jarvas/__init__.py`
- Criar: `jarvas/__main__.py`
- Criar: `jarvas/cli.py`

- [ ] **Passo 1: Escrever o teste que vai falhar**

```python
# tests/test_cli.py
import subprocess, sys

def test_jarvas_help():
    result = subprocess.run(
        [sys.executable, "-m", "jarvas", "--help"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "jarvas" in result.stdout.lower()
```

- [ ] **Passo 2: Rodar o teste para confirmar que falha**

```
python -m pytest tests/test_cli.py::test_jarvas_help -v
```
Esperado: FALHA — `No module named jarvas`

- [ ] **Passo 3: Criar `jarvas/__init__.py`** (arquivo vazio)

```python
# jarvas/__init__.py
```

- [ ] **Passo 4: Criar `jarvas/__main__.py`**

```python
# jarvas/__main__.py
from jarvas.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Passo 5: Criar `jarvas/cli.py` mínimo**

```python
# jarvas/cli.py
"""Jarvas — ponto de entrada do assistente de IA distribuído."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="jarvas",
        description="Jarvas — seu assistente de IA distribuído",
    )
    parser.add_argument("query", nargs="?", help="Pergunta direta (opcional)")
    parser.add_argument("--version", action="version", version="jarvas 0.1.0")
    args = parser.parse_args()

    if args.query:
        print(f"[jarvas] modo direto: {args.query}")
    else:
        print("[jarvas] modo interativo — em breve")
        sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Passo 6: Criar `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "jarvas"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "openai>=1.0",
    "python-dotenv>=1.0",
    "rich>=13.0",
    "prompt_toolkit>=3.0",
    "google-generativeai>=0.8",
    "supabase>=2.0",
    "requests>=2.31",
]

[project.scripts]
jarvas = "jarvas.cli:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["jarvas*"]
```

- [ ] **Passo 7: Instalar o pacote em modo editável**

```
cd c:\Users\Computador\OneDrive\Desktop\jarvas
pip install -e .
```

Esperado: `Successfully installed jarvas-0.1.0`

- [ ] **Passo 8: Rodar o teste para confirmar que passa**

```
python -m pytest tests/test_cli.py::test_jarvas_help -v
```
Esperado: PASSOU

- [ ] **Passo 9: Commit**

```bash
git init
git add pyproject.toml jarvas/__init__.py jarvas/__main__.py jarvas/cli.py tests/test_cli.py
git commit -m "feat: estrutura do pacote jarvas com ponto de entrada CLI"
```

---

### Tarefa 2: Roteador de palavras-chave + seleção de modelo

**Arquivos:**
- Criar: `jarvas/router.py`
- Criar: `tests/test_router.py`

- [ ] **Passo 1: Escrever os testes que vão falhar**

```python
# tests/test_router.py
from jarvas.router import detect_task_type, choose_model


def test_detecta_codigo():
    assert detect_task_type("cria um site html") == "code"
    assert detect_task_type("escreve um python script") == "code"
    assert detect_task_type("kotlin app") == "code"


def test_detecta_visao():
    assert detect_task_type("extrai texto da imagem") == "vision"
    assert detect_task_type("lê essa foto") == "vision"


def test_detecta_analise():
    assert detect_task_type("analise esse código") == "analysis"
    assert detect_task_type("compare as duas opções") == "analysis"


def test_chat_padrao():
    assert detect_task_type("oi como você está") == "chat"
    assert detect_task_type("qual é a capital da França") == "chat"


def test_modelo_codigo():
    assert choose_model("code") == "meta-llama/llama-3.3-70b-instruct"


def test_modelo_visao():
    assert choose_model("vision") == "openai/gpt-4o"


def test_modelo_analise():
    assert choose_model("analysis") == "anthropic/claude-3.5-sonnet"


def test_modelo_chat():
    assert choose_model("chat") == "nousresearch/hermes-3-llama-3.1-70b"
```

- [ ] **Passo 2: Rodar para confirmar que falha**

```
python -m pytest tests/test_router.py -v
```
Esperado: FALHA — `No module named jarvas.router`

- [ ] **Passo 3: Criar `jarvas/router.py`**

```python
# jarvas/router.py
"""Detecção de tipo de tarefa por palavras-chave e seleção de modelo."""

_PALAVRAS_CHAVE = {
    "code": [
        "html", "python", "javascript", "código", "codigo", "kotlin",
        "criar site", "cria um site", "script", "função", "funcao",
        "botia", "typescript", "react", "css",
    ],
    "vision": [
        "imagem", "ocr", "foto", "extrair texto", "ler imagem",
        "extract text", "image", "screenshot",
    ],
    "analysis": [
        "analise", "analisa", "compare", "compara", "explica",
        "resumo", "resume", "explain", "analyze", "summarize",
    ],
}

_MODELOS = {
    "code": "meta-llama/llama-3.3-70b-instruct",
    "vision": "openai/gpt-4o",
    "analysis": "anthropic/claude-3.5-sonnet",
    "chat": "nousresearch/hermes-3-llama-3.1-70b",
}


def detect_task_type(mensagem: str) -> str:
    """Retorna 'code', 'vision', 'analysis' ou 'chat' baseado nas palavras-chave."""
    lower = mensagem.lower()
    for tipo, palavras in _PALAVRAS_CHAVE.items():
        if any(p in lower for p in palavras):
            return tipo
    return "chat"


def choose_model(tipo: str) -> str:
    """Retorna o ID do modelo OpenRouter para o tipo de tarefa."""
    return _MODELOS.get(tipo, _MODELOS["chat"])
```

- [ ] **Passo 4: Rodar os testes para confirmar que passam**

```
python -m pytest tests/test_router.py -v
```
Esperado: Todos PASSARAM

- [ ] **Passo 5: Commit**

```bash
git add jarvas/router.py tests/test_router.py
git commit -m "feat: roteador por palavras-chave — detecta tipo de tarefa e seleciona modelo"
```

---

### Tarefa 3: Cliente Hermes (chamadas à API OpenRouter)

**Arquivos:**
- Criar: `jarvas/hermes_client.py`

- [ ] **Passo 1: Criar `jarvas/hermes_client.py`**

```python
# jarvas/hermes_client.py
"""Cliente OpenRouter para o Hermes — envia mensagens, retorna resposta do assistente."""

import os
from openai import OpenAI
from dotenv import load_dotenv
from jarvas.router import detect_task_type, choose_model

load_dotenv()


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
        "Você é Jarvas, um assistente de IA distribuído do Melo (usuário). "
        "Responda de forma clara e objetiva em português ou no idioma do usuário."
    )

    messages: list[dict] = [{"role": "system", "content": sistema}]
    if historico:
        messages.extend(historico)
    messages.append({"role": "user", "content": mensagem})

    resposta = _get_client().chat.completions.create(
        model=modelo_selecionado,
        messages=messages,
        temperature=0.7,
        max_tokens=2000,
    )
    return resposta.choices[0].message.content, modelo_selecionado
```

- [ ] **Passo 2: Testar manualmente (precisa da chave de API)**

```python
# rodar no terminal Python interativo
from jarvas.hermes_client import chat
resposta, modelo = chat("oi, quem é você?")
print(f"[{modelo}] {resposta}")
```

Esperado: Resposta via `nousresearch/hermes-3-llama-3.1-70b`

- [ ] **Passo 3: Commit**

```bash
git add jarvas/hermes_client.py
git commit -m "feat: cliente OpenRouter — roteia para o melhor modelo por tipo de tarefa"
```

---

### Tarefa 4: REPL interativo

**Arquivos:**
- Modificar: `jarvas/cli.py`

- [ ] **Passo 1: Atualizar `jarvas/cli.py` com o REPL completo**

```python
# jarvas/cli.py
"""Jarvas — ponto de entrada do assistente de IA distribuído."""

import argparse
import sys
import uuid
from rich.console import Console
from rich.markdown import Markdown
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from jarvas.router import detect_task_type

console = Console()
_historico: list[dict] = []
_session_id = str(uuid.uuid4())


def _exibir_resposta(texto: str, modelo: str):
    console.print(f"\n[bold cyan]Jarvas[/bold cyan] [dim]({modelo})[/dim]")
    console.print(Markdown(texto))
    console.print()


def _processar_mensagem(mensagem: str) -> bool:
    """Processa uma mensagem. Retorna False se a sessão deve encerrar."""
    from jarvas.commands import dispatch

    if mensagem.strip().startswith("/"):
        resultado = dispatch(mensagem.strip(), _historico)
        if resultado is not None:
            console.print(resultado)
        return True

    from jarvas.hermes_client import chat
    from jarvas.supabase_client import save_message
    try:
        resposta, modelo = chat(mensagem, historico=_historico)
        tipo = detect_task_type(mensagem)
        _historico.append({"role": "user", "content": mensagem})
        _historico.append({"role": "assistant", "content": resposta})
        try:
            save_message(_session_id, "user", mensagem, task_type=tipo)
            save_message(_session_id, "assistant", resposta, model=modelo, task_type=tipo)
        except Exception:
            pass  # falha no Supabase nunca bloqueia o usuário
        _exibir_resposta(resposta, modelo)
    except Exception as e:
        console.print(f"[red]Erro:[/red] {e}")
    return True


def rodar_interativo():
    console.print("[bold green]Jarvas[/bold green] — assistente de IA distribuído")
    console.print("[dim]Digite sua mensagem ou /help para ver os comandos[/dim]\n")

    session = PromptSession(history=InMemoryHistory())
    while True:
        try:
            entrada = session.prompt("você > ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Até logo![/dim]")
            break

        if not entrada:
            continue
        if entrada.lower() in ("sair", "exit", "quit"):
            console.print("[dim]Até logo![/dim]")
            break

        _processar_mensagem(entrada)


def main():
    parser = argparse.ArgumentParser(
        prog="jarvas",
        description="Jarvas — seu assistente de IA distribuído",
    )
    parser.add_argument("args", nargs="*", help="Pergunta direta ou 'continuar <data> <hora>'")
    parser.add_argument("--version", action="version", version="jarvas 0.1.0")
    parsed = parser.parse_args()

    if not parsed.args:
        rodar_interativo()
        return

    # jarvas continuar ontem 15h
    if parsed.args[0].lower() == "continuar":
        data = parsed.args[1] if len(parsed.args) > 1 else "ontem"
        hora = parsed.args[2] if len(parsed.args) > 2 else "12h"
        from jarvas.supabase_client import load_session_by_time
        try:
            carregado = load_session_by_time(data, hora)
            _historico.extend(carregado)
            console.print(f"[green]Contexto restaurado:[/green] {len(carregado)} mensagens de {data} {hora}")
        except Exception as e:
            console.print(f"[yellow]Não foi possível carregar contexto:[/yellow] {e}")
        rodar_interativo()
        return

    # pergunta direta: jarvas "minha pergunta"
    _processar_mensagem(" ".join(parsed.args))


if __name__ == "__main__":
    main()
```

- [ ] **Passo 2: Criar `jarvas/commands.py` provisório (stub)**

```python
# jarvas/commands.py
"""Despachante de slash commands. Implementação completa na Fase 4."""


def dispatch(comando: str, historico: list[dict]) -> str | None:
    if comando == "/help":
        return (
            "[bold]Comandos disponíveis:[/bold]\n"
            "  /g <prompt>      → Falar com Gemini diretamente\n"
            "  /d <prompt>      → Falar com DeepSeek diretamente\n"
            "  /debate <tópico> → Debate entre Gemini e DeepSeek\n"
            "  /hopen <modelo>  → Forçar modelo específico\n"
            "  /hmem <cmd>      → Acessar MemPalace\n"
            "  /help            → Esta mensagem\n"
        )
    return f"[yellow]Comando ainda não implementado:[/yellow] {comando}"
```

- [ ] **Passo 3: Criar `jarvas/supabase_client.py` provisório (stub)**

```python
# jarvas/supabase_client.py — stub para a Fase 1 rodar sem Supabase configurado
def save_message(*args, **kwargs): pass
def load_session_by_time(*args, **kwargs): return []
```

- [ ] **Passo 4: Testar o REPL manualmente**

```
jarvas
```

Esperado: Banner do Jarvas + prompt `você > `. Digite "oi" → recebe resposta do Hermes.

- [ ] **Passo 5: Testar modo direto**

```
jarvas "qual é a capital do Brasil?"
```

Esperado: Resposta do Hermes no terminal.

- [ ] **Passo 6: Commit**

```bash
git add jarvas/cli.py jarvas/commands.py jarvas/supabase_client.py
git commit -m "feat: REPL interativo com prompt_toolkit + modo de pergunta direta"
```

---

## Fase 2 — Memória no Supabase

### Tarefa 5: Criação do projeto Supabase

**(Passos manuais — sem código)**

- [ ] **Passo 1: Criar projeto no Supabase**

  1. Acesse supabase.com → Novo projeto
  2. Nome: `jarvas`
  3. Copie a **URL do projeto** e a **chave anon** em Configurações → API
  4. Preencha o `.env`:
     ```
     SUPABASE_URL=https://xxxx.supabase.co
     SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
     ```

- [ ] **Passo 2: Criar as tabelas no editor SQL do Supabase**

Cole esse SQL no painel do Supabase → SQL Editor → New query:

```sql
-- Conversas: todas as trocas com o Hermes
CREATE TABLE conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content     TEXT NOT NULL,
    model       TEXT,
    task_type   TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON conversations (session_id, created_at);

-- Logs dos guardas
CREATE TABLE guard_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guard       TEXT NOT NULL CHECK (guard IN ('gemini', 'deepseek')),
    input       TEXT NOT NULL,
    output      TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Transcrições de debates
CREATE TABLE debate_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic       TEXT NOT NULL,
    rounds      JSONB NOT NULL,
    consensus   TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Itens organizados pelo MemPalace
CREATE TABLE memory_items (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wing        TEXT NOT NULL,
    room        TEXT NOT NULL,
    content     TEXT NOT NULL,
    source      TEXT,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Snapshots de sessão para o "jarvas continuar"
CREATE TABLE session_contexts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  TEXT NOT NULL,
    label       TEXT,
    history     JSONB NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON session_contexts (created_at);
```

---

### Tarefa 6: Módulo cliente do Supabase

**Arquivos:**
- Substituir: `jarvas/supabase_client.py` (substituir o stub)
- Criar: `tests/test_supabase_client.py`

- [ ] **Passo 1: Escrever os testes que vão falhar**

```python
# tests/test_supabase_client.py
from unittest.mock import patch, MagicMock


def test_salvar_mensagem_chama_supabase():
    mock_sb = MagicMock()
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

    with patch("jarvas.supabase_client._get_client", return_value=mock_sb):
        from jarvas.supabase_client import save_message
        save_message(
            session_id="sessao-teste",
            role="user",
            content="olá",
            model="nousresearch/hermes-3-llama-3.1-70b",
            task_type="chat",
        )

    mock_sb.table.assert_called_with("conversations")
    mock_sb.table.return_value.insert.assert_called_once()


def test_carregar_historico_retorna_lista():
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"role": "user", "content": "oi"},
        {"role": "assistant", "content": "olá!"},
    ]

    with patch("jarvas.supabase_client._get_client", return_value=mock_sb):
        from jarvas.supabase_client import load_history
        resultado = load_history("sessao-teste", limit=10)

    assert len(resultado) == 2
    assert resultado[0]["role"] == "user"
```

- [ ] **Passo 2: Rodar para confirmar que falha**

```
python -m pytest tests/test_supabase_client.py -v
```
Esperado: FALHA

- [ ] **Passo 3: Criar `jarvas/supabase_client.py` real**

```python
# jarvas/supabase_client.py
"""Operações de leitura e escrita no Supabase para persistência do Jarvas."""

import os
from functools import lru_cache
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


@lru_cache(maxsize=1)
def _get_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL e SUPABASE_KEY devem estar definidos no .env")
    return create_client(url, key)


def save_message(
    session_id: str,
    role: str,
    content: str,
    model: str | None = None,
    task_type: str | None = None,
) -> None:
    """Persiste uma troca de conversa no Supabase."""
    _get_client().table("conversations").insert({
        "session_id": session_id,
        "role": role,
        "content": content,
        "model": model,
        "task_type": task_type,
    }).execute()


def load_history(session_id: str, limit: int = 20) -> list[dict]:
    """Carrega o histórico recente de uma sessão."""
    result = (
        _get_client()
        .table("conversations")
        .select("role, content")
        .eq("session_id", session_id)
        .order("created_at")
        .limit(limit)
        .execute()
    )
    return result.data or []


def save_guard_log(guard: str, input_text: str, output_text: str) -> None:
    """Persiste uma interação com o guarda."""
    _get_client().table("guard_logs").insert({
        "guard": guard,
        "input": input_text,
        "output": output_text,
    }).execute()


def save_debate_log(topic: str, rounds: list[dict], consensus: str) -> None:
    """Persiste a transcrição de um debate."""
    _get_client().table("debate_logs").insert({
        "topic": topic,
        "rounds": rounds,
        "consensus": consensus,
    }).execute()


def load_session_by_time(data_str: str, hora_str: str) -> list[dict]:
    """Carrega o contexto de sessão mais próximo da data+hora informada.

    Exemplos: data_str='ontem', hora_str='15h'
    """
    from datetime import datetime, timedelta

    agora = datetime.now()
    if data_str.lower() == "ontem":
        base = agora - timedelta(days=1)
    elif data_str.lower() == "hoje":
        base = agora
    else:
        try:
            base = datetime.strptime(data_str, "%Y-%m-%d")
        except ValueError:
            base = agora - timedelta(days=1)

    hora = int(hora_str.replace("h", "").replace(":", "").zfill(4)[:2])
    alvo = base.replace(hour=hora, minute=0, second=0, microsecond=0)
    alvo_iso = alvo.isoformat()

    result = (
        _get_client()
        .table("session_contexts")
        .select("history")
        .lte("created_at", alvo_iso)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]["history"]
    return []
```

- [ ] **Passo 4: Rodar os testes para confirmar que passam**

```
python -m pytest tests/test_supabase_client.py -v
```
Esperado: Todos PASSARAM

- [ ] **Passo 5: Commit**

```bash
git add jarvas/supabase_client.py tests/test_supabase_client.py
git commit -m "feat: persistência Supabase — todas as conversas salvas na nuvem"
```

---

## Fase 3 — Guardas Autônomos

### Tarefa 7: Guarda Gemini

**Arquivos:**
- Criar: `jarvas/guard_gemini.py`
- Criar: `tests/test_guard_gemini.py`

- [ ] **Passo 1: Escrever os testes que vão falhar**

```python
# tests/test_guard_gemini.py
from unittest.mock import patch, MagicMock


def test_gemini_chat_retorna_string():
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = "resposta do gemini"

    with patch("jarvas.guard_gemini._get_model", return_value=mock_model):
        from jarvas.guard_gemini import chat
        resultado = chat("olá gemini")

    assert isinstance(resultado, str)
    assert "resposta do gemini" in resultado


def test_gemini_chat_salva_no_supabase():
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = "resposta"

    with patch("jarvas.guard_gemini._get_model", return_value=mock_model), \
         patch("jarvas.guard_gemini.save_guard_log") as mock_save:
        from jarvas.guard_gemini import chat
        chat("teste")

    mock_save.assert_called_once_with("gemini", "teste", "resposta")
```

- [ ] **Passo 2: Rodar para confirmar que falha**

```
python -m pytest tests/test_guard_gemini.py -v
```
Esperado: FALHA

- [ ] **Passo 3: Criar `jarvas/guard_gemini.py`**

```python
# jarvas/guard_gemini.py
"""Guarda Gemini — chat direto e processamento de memória em segundo plano."""

import os
from functools import lru_cache
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
```

- [ ] **Passo 4: Rodar os testes para confirmar que passam**

```
python -m pytest tests/test_guard_gemini.py -v
```
Esperado: PASSOU

- [ ] **Passo 5: Commit**

```bash
git add jarvas/guard_gemini.py tests/test_guard_gemini.py
git commit -m "feat: guarda Gemini — chat direto e busca web"
```

---

### Tarefa 8: Guarda DeepSeek

**Arquivos:**
- Criar: `jarvas/guard_deepseek.py`
- Criar: `tests/test_guard_deepseek.py`

- [ ] **Passo 1: Escrever os testes que vão falhar**

```python
# tests/test_guard_deepseek.py
from unittest.mock import patch, MagicMock


def test_deepseek_chat_retorna_string():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = "resposta deepseek"

    with patch("jarvas.guard_deepseek._get_client", return_value=mock_client):
        from jarvas.guard_deepseek import chat
        resultado = chat("olá deepseek")

    assert isinstance(resultado, str)
    assert "resposta deepseek" in resultado


def test_deepseek_chat_salva_no_supabase():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = "resp"

    with patch("jarvas.guard_deepseek._get_client", return_value=mock_client), \
         patch("jarvas.guard_deepseek.save_guard_log") as mock_save:
        from jarvas.guard_deepseek import chat
        chat("teste")

    mock_save.assert_called_once_with("deepseek", "teste", "resp")
```

- [ ] **Passo 2: Rodar para confirmar que falha**

```
python -m pytest tests/test_guard_deepseek.py -v
```
Esperado: FALHA

- [ ] **Passo 3: Criar `jarvas/guard_deepseek.py`**

```python
# jarvas/guard_deepseek.py
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
```

- [ ] **Passo 4: Rodar os testes para confirmar que passam**

```
python -m pytest tests/test_guard_deepseek.py -v
```
Esperado: PASSOU

- [ ] **Passo 5: Commit**

```bash
git add jarvas/guard_deepseek.py tests/test_guard_deepseek.py
git commit -m "feat: guarda DeepSeek — chat direto e busca web"
```

---

### Tarefa 9: Orquestrador de debate

**Arquivos:**
- Criar: `jarvas/debate.py`
- Criar: `tests/test_debate.py`

- [ ] **Passo 1: Escrever os testes que vão falhar**

```python
# tests/test_debate.py
from unittest.mock import patch


def test_debate_retorna_consenso():
    with patch("jarvas.debate.gemini_chat") as mock_g, \
         patch("jarvas.debate.deepseek_chat") as mock_d, \
         patch("jarvas.debate.save_debate_log"):
        mock_g.return_value = "Gemini: Python é melhor por legibilidade."
        mock_d.return_value = "DeepSeek: Python é melhor pelo ecossistema."

        from jarvas.debate import run_debate
        resultado = run_debate("Qual linguagem usar para IA?", max_rounds=1)

    assert "topic" in resultado
    assert "consensus" in resultado
    assert "rounds" in resultado
    assert len(resultado["rounds"]) >= 1


def test_debate_respeita_max_rounds():
    with patch("jarvas.debate.gemini_chat", return_value="gemini"), \
         patch("jarvas.debate.deepseek_chat", return_value="deepseek"), \
         patch("jarvas.debate.save_debate_log"):
        from jarvas.debate import run_debate
        resultado = run_debate("tópico", max_rounds=2)

    assert len(resultado["rounds"]) <= 2
```

- [ ] **Passo 2: Rodar para confirmar que falha**

```
python -m pytest tests/test_debate.py -v
```
Esperado: FALHA

- [ ] **Passo 3: Criar `jarvas/debate.py`**

```python
# jarvas/debate.py
"""Orquestrador de debate multi-agente — Gemini vs DeepSeek, chega ao consenso."""

from jarvas.guard_gemini import chat as gemini_chat
from jarvas.guard_deepseek import chat as deepseek_chat
from jarvas.supabase_client import save_debate_log


def run_debate(topico: str, max_rounds: int = 3) -> dict:
    """Executa debate entre Gemini e DeepSeek sobre o tópico dado.

    Retorna dict com: topic, rounds (lista), consensus (str).
    """
    rounds: list[dict] = []

    ctx_gemini = (
        f"Você está num debate sobre: '{topico}'. "
        f"Apresente seu ponto de vista inicial de forma clara e argumentada."
    )
    ctx_deepseek = ctx_gemini

    for rodada in range(1, max_rounds + 1):
        resp_gemini = gemini_chat(ctx_gemini)
        resp_deepseek = deepseek_chat(ctx_deepseek)

        rounds.append({
            "round": rodada,
            "gemini": resp_gemini,
            "deepseek": resp_deepseek,
        })

        ctx_gemini = (
            f"Debate sobre '{topico}' — rodada {rodada + 1}.\n"
            f"DeepSeek disse: {resp_deepseek}\n"
            f"Responda e refine sua posição, ou concorde se o argumento fizer sentido."
        )
        ctx_deepseek = (
            f"Debate sobre '{topico}' — rodada {rodada + 1}.\n"
            f"Gemini disse: {resp_gemini}\n"
            f"Responda e refine sua posição, ou concorde se o argumento fizer sentido."
        )

    # Consenso final — Gemini sintetiza
    prompt_consenso = (
        f"Debate sobre '{topico}' concluído após {max_rounds} rodada(s).\n"
        f"Rodadas: {rounds}\n"
        f"Sintetize o consenso alcançado em 2-3 parágrafos objetivos."
    )
    consenso = gemini_chat(prompt_consenso)

    save_debate_log(topico, rounds, consenso)

    return {
        "topic": topico,
        "rounds": rounds,
        "consensus": consenso,
    }


def format_debate_result(resultado: dict) -> str:
    """Formata o resultado do debate para exibição no terminal."""
    linhas = [
        f"\n[bold]Debate:[/bold] {resultado['topic']}",
        f"[dim]Rodadas: {len(resultado['rounds'])}[/dim]\n",
    ]
    for r in resultado["rounds"]:
        linhas.append(f"[cyan]Rodada {r['round']}[/cyan]")
        linhas.append(f"[green]Gemini:[/green] {r['gemini'][:200]}...")
        linhas.append(f"[blue]DeepSeek:[/blue] {r['deepseek'][:200]}...\n")
    linhas.append(f"[bold yellow]Consenso:[/bold yellow]\n{resultado['consensus']}")
    return "\n".join(linhas)
```

- [ ] **Passo 4: Rodar os testes para confirmar que passam**

```
python -m pytest tests/test_debate.py -v
```
Esperado: PASSOU

- [ ] **Passo 5: Commit**

```bash
git add jarvas/debate.py tests/test_debate.py
git commit -m "feat: orquestrador de debate — Gemini vs DeepSeek com consenso"
```

---

## Fase 4 — Comandos Completos

### Tarefa 10: Despachante de slash commands completo

**Arquivos:**
- Substituir: `jarvas/commands.py`
- Criar: `tests/test_commands.py`

- [ ] **Passo 1: Escrever os testes que vão falhar**

```python
# tests/test_commands.py
from unittest.mock import patch


def test_comando_help():
    from jarvas.commands import dispatch
    resultado = dispatch("/help", [])
    assert resultado is not None
    assert "/g" in resultado


def test_comando_desconhecido():
    from jarvas.commands import dispatch
    resultado = dispatch("/xyz", [])
    assert "desconhecido" in resultado.lower() or "não" in resultado.lower()


def test_comando_g_chama_gemini():
    with patch("jarvas.commands.gemini_chat", return_value="resp gemini") as mock_g:
        from jarvas.commands import dispatch
        resultado = dispatch("/g olá gemini", [])
    mock_g.assert_called_once_with("olá gemini")
    assert "resp gemini" in resultado


def test_comando_d_chama_deepseek():
    with patch("jarvas.commands.deepseek_chat", return_value="resp deepseek") as mock_d:
        from jarvas.commands import dispatch
        resultado = dispatch("/d olá deepseek", [])
    mock_d.assert_called_once_with("olá deepseek")
    assert "resp deepseek" in resultado


def test_comando_debate():
    with patch("jarvas.commands.run_debate") as mock_debate, \
         patch("jarvas.commands.format_debate_result", return_value="resultado formatado"):
        mock_debate.return_value = {"topic": "t", "rounds": [], "consensus": "c"}
        from jarvas.commands import dispatch
        resultado = dispatch("/debate python vs rust", [])
    mock_debate.assert_called_once_with("python vs rust")
    assert "resultado formatado" in resultado
```

- [ ] **Passo 2: Rodar para confirmar que falha**

```
python -m pytest tests/test_commands.py -v
```
Esperado: FALHA

- [ ] **Passo 3: Substituir `jarvas/commands.py` pela implementação completa**

```python
# jarvas/commands.py
"""Despachante de slash commands do Jarvas."""

from __future__ import annotations

from jarvas.guard_gemini import chat as gemini_chat, web_search as gemini_web
from jarvas.guard_deepseek import chat as deepseek_chat, web_search as deepseek_web
from jarvas.debate import run_debate, format_debate_result


def dispatch(comando: str, historico: list[dict]) -> str:
    """Roteia um slash command para seu handler. Retorna string formatada."""
    partes = comando.split(None, 1)
    cmd = partes[0].lower()
    args = partes[1] if len(partes) > 1 else ""

    if cmd == "/help":
        return _help()
    if cmd == "/g":
        return _guarda_g(args)
    if cmd == "/d":
        return _guarda_d(args)
    if cmd == "/debate":
        if not args:
            return "[red]Uso:[/red] /debate <tópico>"
        resultado = run_debate(args)
        return format_debate_result(resultado)
    if cmd == "/hopen":
        if not args:
            return "[red]Uso:[/red] /hopen <model-id>"
        return f"[yellow]Próxima mensagem usará o modelo:[/yellow] {args}"
    if cmd == "/hmem":
        return _hmem(args)

    return f"[yellow]Comando desconhecido:[/yellow] {cmd} — use /help"


def _help() -> str:
    return (
        "\n[bold]Comandos Jarvas:[/bold]\n"
        "  [cyan]/g[/cyan] <prompt>            → Gemini diretamente\n"
        "  [cyan]/g web[/cyan] <busca>         → Gemini + busca web\n"
        "  [cyan]/d[/cyan] <prompt>            → DeepSeek diretamente\n"
        "  [cyan]/d web[/cyan] <busca>         → DeepSeek + busca web\n"
        "  [cyan]/debate[/cyan] <tópico>       → Debate Gemini vs DeepSeek\n"
        "  [cyan]/hopen[/cyan] <model-id>      → Forçar modelo específico\n"
        "  [cyan]/hmem status[/cyan]           → Status do MemPalace\n"
        "  [cyan]/hmem list[/cyan]             → Listar wings\n"
        "  [cyan]/hmem search[/cyan] <busca>   → Busca semântica\n"
        "  [cyan]/hmem add[/cyan] <wing> <room> <conteúdo>  → Adicionar memória\n"
        "  [cyan]/hmem get[/cyan] <id>         → Obter drawer\n"
        "  [cyan]/hmem del[/cyan] <id>         → Deletar drawer\n"
        "  [cyan]/hmem graph[/cyan]            → Estatísticas do grafo\n"
        "  [cyan]/hmem kg[/cyan] <busca>       → Consultar knowledge graph\n"
    )


def _guarda_g(args: str) -> str:
    if not args:
        return "[red]Uso:[/red] /g <prompt> ou /g web <busca>"
    sub = args.split(None, 1)
    if sub[0].lower() == "web":
        query = sub[1] if len(sub) > 1 else ""
        if not query:
            return "[red]Uso:[/red] /g web <busca>"
        return f"[green]Gemini web:[/green]\n{gemini_web(query)}"
    return f"[green]Gemini:[/green]\n{gemini_chat(args)}"


def _guarda_d(args: str) -> str:
    if not args:
        return "[red]Uso:[/red] /d <prompt> ou /d web <busca>"
    sub = args.split(None, 1)
    if sub[0].lower() == "web":
        query = sub[1] if len(sub) > 1 else ""
        if not query:
            return "[red]Uso:[/red] /d web <busca>"
        return f"[blue]DeepSeek web:[/blue]\n{deepseek_web(query)}"
    return f"[blue]DeepSeek:[/blue]\n{deepseek_chat(args)}"


def _hmem(args: str) -> str:
    from jarvas.mempalace_client import handle_hmem
    return handle_hmem(args)
```

- [ ] **Passo 4: Rodar os testes para confirmar que passam**

```
python -m pytest tests/test_commands.py -v
```
Esperado: Todos PASSARAM

- [ ] **Passo 5: Commit**

```bash
git add jarvas/commands.py tests/test_commands.py
git commit -m "feat: despachante completo de slash commands — /g /d /debate /hopen /hmem"
```

---

### Tarefa 11: Cliente MemPalace (`/hmem`)

**Arquivos:**
- Criar: `jarvas/mempalace_client.py`
- Criar: `tests/test_mempalace_client.py`

- [ ] **Passo 1: Instalar o MemPalace a partir do código local**

```
pip install -e c:\Users\Computador\OneDrive\Desktop\jarvas\mempalace-develop
```

Esperado: `Successfully installed mempalace-...`

- [ ] **Passo 2: Escrever os testes que vão falhar**

```python
# tests/test_mempalace_client.py
from unittest.mock import patch, MagicMock


def test_hmem_status():
    mock_tools = MagicMock()
    mock_tools.tool_status.return_value = {"total": 42, "wings": 3}

    with patch("jarvas.mempalace_client._get_tools", return_value=mock_tools):
        from jarvas.mempalace_client import handle_hmem
        resultado = handle_hmem("status")

    assert "42" in resultado or "status" in resultado.lower()


def test_hmem_search():
    mock_tools = MagicMock()
    mock_tools.tool_search.return_value = [{"id": "abc", "content": "resultado encontrado"}]

    with patch("jarvas.mempalace_client._get_tools", return_value=mock_tools):
        from jarvas.mempalace_client import handle_hmem
        resultado = handle_hmem("search python")

    assert "resultado encontrado" in resultado or "abc" in resultado


def test_hmem_subcomando_desconhecido():
    from jarvas.mempalace_client import handle_hmem
    resultado = handle_hmem("xyz")
    assert "desconhecido" in resultado.lower() or "uso" in resultado.lower()
```

- [ ] **Passo 3: Rodar para confirmar que falha**

```
python -m pytest tests/test_mempalace_client.py -v
```
Esperado: FALHA

- [ ] **Passo 4: Criar `jarvas/mempalace_client.py`**

```python
# jarvas/mempalace_client.py
"""Cliente MemPalace — envolve as ferramentas do MemPalace para os comandos /hmem."""

from __future__ import annotations
import json
from functools import lru_cache


@lru_cache(maxsize=1)
def _get_tools():
    """Importa as funções de ferramentas do MemPalace."""
    from mempalace.mcp_server import (
        tool_status, tool_list_wings, tool_get_taxonomy,
        tool_search, tool_add_drawer, tool_delete_drawer,
        tool_get_drawer, tool_graph_stats, tool_kg_query,
    )

    class _Tools:
        pass

    t = _Tools()
    t.tool_status = tool_status
    t.tool_list_wings = tool_list_wings
    t.tool_get_taxonomy = tool_get_taxonomy
    t.tool_search = tool_search
    t.tool_add_drawer = tool_add_drawer
    t.tool_delete_drawer = tool_delete_drawer
    t.tool_get_drawer = tool_get_drawer
    t.tool_graph_stats = tool_graph_stats
    t.tool_kg_query = tool_kg_query
    return t


def _fmt(obj) -> str:
    if isinstance(obj, str):
        return obj
    return json.dumps(obj, indent=2, ensure_ascii=False)


def handle_hmem(args: str) -> str:
    """Roteia subcomandos /hmem para as ferramentas do MemPalace."""
    partes = args.strip().split(None, 3) if args.strip() else []
    sub = partes[0].lower() if partes else ""

    try:
        tools = _get_tools()
    except Exception as e:
        return f"[red]MemPalace indisponível:[/red] {e}"

    if sub in ("status", ""):
        return f"[bold]Status do MemPalace:[/bold]\n{_fmt(tools.tool_status())}"

    if sub == "list":
        return f"[bold]Wings:[/bold]\n{_fmt(tools.tool_list_wings())}"

    if sub == "taxonomy":
        return f"[bold]Taxonomia:[/bold]\n{_fmt(tools.tool_get_taxonomy())}"

    if sub == "search":
        query = " ".join(partes[1:]) if len(partes) > 1 else ""
        if not query:
            return "[red]Uso:[/red] /hmem search <busca>"
        return f"[bold]Resultados:[/bold]\n{_fmt(tools.tool_search(query=query))}"

    if sub == "add":
        if len(partes) < 4:
            return "[red]Uso:[/red] /hmem add <wing> <room> <conteúdo>"
        wing, room, content = partes[1], partes[2], partes[3]
        return f"[green]Drawer adicionado:[/green]\n{_fmt(tools.tool_add_drawer(wing=wing, room=room, content=content))}"

    if sub == "get":
        if len(partes) < 2:
            return "[red]Uso:[/red] /hmem get <id>"
        return f"[bold]Drawer:[/bold]\n{_fmt(tools.tool_get_drawer(drawer_id=partes[1]))}"

    if sub == "del":
        if len(partes) < 2:
            return "[red]Uso:[/red] /hmem del <id>"
        return f"[yellow]Deletado:[/yellow]\n{_fmt(tools.tool_delete_drawer(drawer_id=partes[1]))}"

    if sub == "graph":
        return f"[bold]Estatísticas do Grafo:[/bold]\n{_fmt(tools.tool_graph_stats())}"

    if sub == "kg":
        query = " ".join(partes[1:]) if len(partes) > 1 else ""
        if not query:
            return "[red]Uso:[/red] /hmem kg <busca>"
        return f"[bold]Knowledge Graph:[/bold]\n{_fmt(tools.tool_kg_query(query=query))}"

    return f"[yellow]Subcomando desconhecido:[/yellow] {sub} — use /help"
```

- [ ] **Passo 5: Rodar os testes para confirmar que passam**

```
python -m pytest tests/test_mempalace_client.py -v
```
Esperado: Todos PASSARAM

- [ ] **Passo 6: Commit**

```bash
git add jarvas/mempalace_client.py tests/test_mempalace_client.py
git commit -m "feat: cliente MemPalace — comandos /hmem conectados ao palace"
```

---

### Tarefa 12: Rodar todos os testes + verificação final

- [ ] **Passo 1: Rodar a suite completa de testes**

```
python -m pytest tests/ -v
```

Esperado: Todos PASSARAM

- [ ] **Passo 2: Testar a sessão interativa completa**

```
jarvas
```

Teste estes comandos dentro da sessão:
1. `oi, quem é você?` → Hermes responde via `nousresearch/hermes-3-llama-3.1-70b`
2. `cria um script python` → Hermes roteia para `meta-llama/llama-3.3-70b-instruct`
3. `/g explica o que é MemPalace` → Gemini responde diretamente
4. `/d qual é o melhor formato para armazenar memórias?` → DeepSeek responde
5. `/debate Python vs JavaScript para IA` → Debate roda, consenso exibido
6. `/hmem status` → Status do palace exibido
7. `/help` → Lista completa de comandos
8. `sair` → Sessão encerra

- [ ] **Passo 3: Commit final**

```bash
git add .
git commit -m "chore: todas as fases concluídas — Jarvas v0.1.0 pronto"
```

---

## Referência Rápida

```bash
# Instalação
cd c:\Users\Computador\OneDrive\Desktop\jarvas
pip install -e .
pip install -e mempalace-develop

# Uso
jarvas                          # modo interativo
jarvas "sua pergunta"           # pergunta direta
jarvas continuar ontem 15h      # retomar contexto

# Dentro da sessão
/g <prompt>          # Gemini
/d <prompt>          # DeepSeek
/g web <busca>       # Gemini + web
/d web <busca>       # DeepSeek + web
/debate <tópico>     # debate + consenso
/hopen <model-id>    # forçar modelo
/hmem status         # status do palace
/hmem search <b>     # busca no palace
/hmem add <w> <r> <conteúdo>  # adicionar memória
sair                 # encerrar
```
