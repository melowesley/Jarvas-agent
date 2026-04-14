# Jarvas Managed Agent — Design Spec

**Data:** 2026-04-13  
**Status:** Aprovado  
**Abordagem:** B — Camada nova sobre código existente

---

## Contexto

O Jarvas é um assistente CLI de IA distribuído que usa OpenRouter (Hermes), Gemini e DeepSeek como agentes. O arquivo `logica refatorada Jarvas.md` documenta o padrão **Anthropic Claude Managed Agents** — onde Agents, Environments, Sessions e Events formam uma arquitetura reutilizável e versionada.

O objetivo é implementar esse padrão no Jarvas usando OpenRouter como backend de modelos, expondo uma API REST + SSE compatível com o padrão Managed Agents, sem quebrar nenhuma funcionalidade existente (/g, /d, /debate, /hmem, REPL).

======pode quebrar nao tem problema=========

---

## Arquitetura

### Novo pacote `jarvas/managed/`

```
jarvas/managed/
  __init__.py       # package marker
  models.py         # Pydantic: Agent, Session, Environment, Events
  store.py          # estado em memória: dicts por id
  toolset.py        # ferramentas built-in: bash, write, read, web_search
  runtime.py        # loop assíncrono: OpenRouter + tool-use via httpx
  sse.py            # helpers SSE: format_sse, event_generator
  router.py         # APIRouter FastAPI com todos os endpoints
  startup.py        # seed dos 3 agentes pré-registrados
```

### Endpoints REST

| Método | Path | Descrição |
|--------|------|-----------|
| POST | `/v1/agents` | Criar agente |
| GET | `/v1/agents` | Listar agentes |
| GET | `/v1/agents/{id}` | Obter agente |
| POST | `/v1/sessions` | Iniciar sessão |
| GET | `/v1/sessions/{id}` | Status da sessão |
| POST | `/v1/sessions/{id}/events` | Enviar mensagem (→ 202) |
| GET | `/v1/sessions/{id}/stream` | Stream SSE |

### Formato SSE

```
data: {"type": "agent.message", "session_id": "...", "content": "...", "model": "..."}

data: {"type": "agent.tool_use", "session_id": "...", "tool_name": "bash", "tool_input": {...}}

data: {"type": "agent.tool_result", "session_id": "...", "tool_name": "bash", "output": "...", "is_error": false}

data: {"type": "session.status_idle", "session_id": "..."}
```

---

## Componentes

### Models (`models.py`)
- `AgentCreate` / `AgentRecord` — name, model, system_prompt, tools: list[str]
- `SessionCreate` / `SessionRecord` — agent_id, status: idle/running/error
- `EnvironmentRecord` — allowed_tools (simplificado, sem Docker)
- Tipos de evento: `EventAgentMessage`, `EventToolUse`, `EventToolResult`, `EventStatusIdle`

### Store (`store.py`)
Dicts em memória: `_agents`, `_sessions`, `_events`, `_queues`. CRUD síncrono simples. Supabase pode ser adicionado como camada opcional futura.

### Toolset (`toolset.py`)
- `bash` — `asyncio.create_subprocess_shell`, timeout 30s
- `write` — `aiofiles.open(path, "w")`
- `read` — `aiofiles.open(path, "r")`, limite 50KB
- `web_search` — delega para `guard_gemini.web_search` via `asyncio.to_thread`

### Runtime (`runtime.py`)
Loop assíncrono com `httpx.AsyncClient`:
1. Recebe mensagem do usuário
2. Chama OpenRouter com `tools` habilitadas
3. Se `tool_calls`: executa ferramenta → envia `tool_result` → repete
4. Emite eventos no `asyncio.Queue` da sessão
5. Emite `session.status_idle`

Usa `httpx` async (novo) para não conflitar com `hermes_client.py` sync (existente).

### Agentes Pré-registrados (`startup.py`)
- `hermes` — nousresearch/hermes-3-llama-3.1-70b, todas as ferramentas
- `gemini-guard` — google/gemini-2.5-flash via OpenRouter, web_search + read
- `deepseek-guard` — deepseek/deepseek-chat via OpenRouter, read + write

---

## Mudanças nos arquivos existentes

### `api.py` (mínimo)
```python
# Adicionar lifespan com seed_preset_agents()
# Incluir managed_router
# Todo o resto permanece intocado
```

### `cli.py` (mínimo)
```python
# Adicionar flag --managed / positional "api"
# Quando presente: uvicorn.run("jarvas.api:app", ...)
```

### `commands.py` (adição)
```python
# Novo elif para /session list|new|send
# Usa httpx (sync) para localhost:8000
```

### `pyproject.toml`
Adicionar: `httpx`, `aiofiles`, `uvicorn[standard]`

---

## Verificação End-to-End

```bash
# 1. Iniciar servidor
jarvas --managed

# 2. Listar agentes pré-registrados
curl http://localhost:8000/v1/agents

# 3. Criar sessão com hermes
curl -XPOST http://localhost:8000/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "<HERMES_ID>", "title": "teste"}'

# 4. Abrir stream SSE
curl -N http://localhost:8000/v1/sessions/<SESSION_ID>/stream &

# 5. Enviar mensagem
curl -XPOST http://localhost:8000/v1/sessions/<SESSION_ID>/events \
  -H "Content-Type: application/json" \
  -d '{"content": "Quanto é 2+2?"}'

# 6. Verificar que REPL continua funcionando
jarvas
você > /g hello
você > /debate Python vs JS
você > /hmem status
```

---

## Fora do Escopo
- Docker/containers reais para environments
- Streaming de tokens (token-by-token) — SSE emite eventos por etapa lógica
- Supabase persistence para managed state (v1 usa memória)
- `callable_agents` (multi-agent orquestrado via API)
