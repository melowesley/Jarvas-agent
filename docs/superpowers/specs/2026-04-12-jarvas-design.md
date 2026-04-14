# Jarvas — Design Specification

**Date:** 2026-04-12  
**Status:** Approved

---

## 1. Overview

Jarvas is a distributed AI assistant system — described by the user as "the first neuron of a distributed AI brain." It wraps the existing `hermes-agent` CLI (already installed) and extends it with:
- Supabase-based persistent memory (all data in the cloud, nothing local)
- Two autonomous guard agents (Gemini + DeepSeek) that process and organize memory even when the user is offline
- MemPalace as the semantic organizational layer used by the guards
- A unified command surface accessible from PowerShell 7 and VSCode

---

## 2. Components

| Component | Role | Model / API |
|-----------|------|-------------|
| **Jarvas CLI** | Entry point, command dispatcher | Python CLI (`jarvas` command) |
| **Hermes** | Surface interface — user's primary conversation partner | OpenRouter → best model per task type |
| **Gemini Guard** | Semantic memory guard — finds patterns, organizes by meaning | `google/gemini-2.0-flash-exp` via Gemini API |
| **DeepSeek Guard** | Archivist guard — structures, deduplicates, indexes | `deepseek-chat` via DeepSeek API |
| **MemPalace** | Organizational library used by guards to structure Supabase data | ChromaDB-based local library |
| **Supabase** | Cloud persistent storage — ALL data goes here | Supabase REST + Postgres |

---

## 3. Hermes Model Routing (via OpenRouter)

Hermes detects task type from keywords and routes to the best model:

| Keywords detected | Task type | Model |
|-------------------|-----------|-------|
| html, python, javascript, código, kotlin, criar site, botia | `code` | `meta-llama/llama-3.3-70b-instruct` |
| imagem, ocr, foto, extrair texto, ler imagem | `vision` | `openai/gpt-4o` |
| analise, compare, explica, resumo | `analysis` | `anthropic/claude-3.5-sonnet` |
| *(default / chat)* | `chat` | `nousresearch/hermes-3-llama-3.1-70b` |

---

## 4. Command Reference

All commands start from the `jarvas` shell command:

```
jarvas                          → start interactive Hermes session
jarvas "mensagem"               → single-shot query to Hermes
jarvas continuar [data] [hora]  → resume session context from Supabase by timestamp
```

Inside the interactive session, these slash commands are available:

| Command | Routes to | Description |
|---------|-----------|-------------|
| `/g <prompt>` | Gemini Guard directly | Talk to Gemini without going through Hermes pipeline |
| `/g web <query>` | Gemini + web | Gemini performs web search, returns result |
| `/d <prompt>` | DeepSeek Guard directly | Talk to DeepSeek directly |
| `/d web <query>` | DeepSeek + web | DeepSeek performs web search |
| `/debate <topic>` | Gemini + DeepSeek | Both guards debate topic, reach consensus, report to Hermes |
| `/hopen <model>` | Hermes → specific OpenRouter model | Force-select a specific model for this turn |
| `/hmem status` | MemPalace | Show palace status (total drawers, wing breakdown) |
| `/hmem list` | MemPalace | List all wings |
| `/hmem search <query>` | MemPalace | Semantic search across palace |
| `/hmem add <wing> <room> <content>` | MemPalace | File content into palace |
| `/hmem get <id>` | MemPalace | Retrieve a specific drawer by ID |
| `/hmem del <id>` | MemPalace | Delete a drawer |
| `/hmem graph` | MemPalace | Show knowledge graph stats |
| `/hmem kg <query>` | MemPalace | Query knowledge graph |

---

## 5. Data Flow

### Normal user message
```
User → jarvas → Hermes (OpenRouter, model chosen by keyword) → response shown
                    ↓
              Supabase (conversation stored)
                    ↓ (async, background)
         Gemini Guard + DeepSeek Guard (MemPalace organizes) → Supabase
```

### Direct guard call (`/g` or `/d`)
```
User → jarvas → Guard API directly → response shown
                    ↓
              Supabase (guard conversation stored)
```

### Debate (`/debate`)
```
User → jarvas → Gemini + DeepSeek simultaneously debate
                    ↓
               Consensus reached (max 3 rounds)
                    ↓
               Report returned to Hermes → shown to user
                    ↓
               Supabase (debate log stored)
```

### Background processing (guards autonomous)
```
Supabase (new data detected) → Guards poll every N minutes
                    ↓
          MemPalace organizes data into wings/rooms/drawers
                    ↓
          Structured data written back to Supabase
```

---

## 6. Supabase Schema (5 tables)

| Table | Content |
|-------|---------|
| `conversations` | All Hermes chat turns (user + assistant messages) |
| `guard_logs` | Guard agent processing logs and outputs |
| `debate_logs` | Full debate transcripts between Gemini and DeepSeek |
| `memory_items` | MemPalace-organized structured knowledge |
| `session_contexts` | Timestamped session snapshots for `jarvas continuar` |

---

## 7. Interfaces

### PowerShell 7 (PS7)
- `jarvas` command available in PS7 after `pip install -e .` from project root
- Works as interactive REPL or single-shot `jarvas "query"`

### VSCode Panel
- Deferred to end of project (user already added a skill for this)
- Will be a webview panel with the same command surface

---

## 8. Project Structure

```
jarvas/                          ← root (c:\Users\Computador\OneDrive\Desktop\jarvas\)
├── .env                         ← API keys (never committed)
├── pyproject.toml               ← installs `jarvas` command
├── jarvas/                      ← main Python package
│   ├── __init__.py
│   ├── cli.py                   ← entry point, REPL, command dispatcher
│   ├── router.py                ← keyword detection + model selection for Hermes
│   ├── hermes_client.py         ← OpenRouter API calls
│   ├── guard_gemini.py          ← Gemini guard: direct calls + background processing
│   ├── guard_deepseek.py        ← DeepSeek guard: direct calls + background processing
│   ├── debate.py                ← multi-agent debate orchestration
│   ├── supabase_client.py       ← Supabase read/write wrapper
│   ├── mempalace_client.py      ← MemPalace tool wrappers for /hmem commands
│   └── commands.py              ← /slash command handler registry
├── docs/
│   └── superpowers/
│       ├── specs/               ← this file
│       └── plans/               ← implementation plan
├── hermes-agent/                ← existing (not modified)
└── mempalace-develop/           ← existing (not modified)
```

---

## 9. Key Design Decisions

1. **Jarvas does NOT modify hermes-agent or mempalace source** — it uses them as libraries/dependencies
2. **MemPalace is used by guards only** — the user accesses MemPalace via `/hmem` commands, but the guards use it autonomously to organize data
3. **All persistence goes to Supabase** — MemPalace's ChromaDB is used as a transient organizational layer; the final structured output goes to Supabase
4. **Background processing is polling-based** — guards check Supabase for unprocessed items on a schedule (configurable interval, default 5 min)
5. **Debate is synchronous** — `/debate` blocks until consensus is reached (max 3 rounds), then returns result
6. **No local JSON memory** — the guide's `memories.json` approach is replaced entirely by Supabase
