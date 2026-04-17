# Plano: Jarvas v0.5.0 — Multi-Agente Formal (versão final)

**Escopo:** Fase 1-4 (completo) · **Framework:** custom + Pydantic · **Versão alvo:** 0.5.0 (final)

---

## 1. Contexto

Jarvas hoje já é multi-modelo (Hermes, Gemini, DeepSeek, agents Ollama locais) mas com duas bases desconectadas:

- **Legacy**: `orchestrator.py` usa um dict `_HANDLERS` hardcoded; guards chamam LLMs direto via cliente; pipeline e debate são funções soltas.
- **Managed**: `jarvas/managed/` já tem o modelo certo — `AgentRecord` (Pydantic), `store`, `runtime.py` com loop de tool-calling, `call_agent` com `MAX_DEPTH=3`, SSE.

A v0.5.0 unifica os dois mundos num **registry único de Agents**, aplica o hardening do `logica refatorada Jarvas.md` (Pydantic, idempotência, sandbox, observabilidade) uma vez só, e fecha o ciclo do projeto. Depois disso, novos especialistas (autoescola, UI/UX, futuros domínios) plugam sem tocar no dispatcher.

**Resultado esperado:** um único ponto de entrada (`Supervisor`), um único contrato de Agent, um único registry de tools com preview/whitelist, um único formato de resultado (`AgentResult`/`ToolResult`).

---

## 2. Arquitetura alvo

```
Intent (parser atual) ──► Supervisor ──► Agent.run() ──► AgentResult
                             │
                             ├─ resolve por nome via Registry
                             ├─ pode invocar Strategies (pipeline/debate) como tools
                             └─ respeita MAX_DEPTH/MAX_CYCLES (reusa runtime)

Agent (contrato único)
 ├─ name, role, model, tools[], memory_scope, can_delegate_to[]
 ├─ .run(message, ctx) -> AgentResult
 └─ persistido em managed/store.py como AgentRecord

Tools (registry único em managed/toolset.py)
 ├─ bash, vscode_edit, vscode_open, vscode_terminal (já existem)
 ├─ file_read, file_edit, file_process (migrados de file_editor.py/file_processor.py)
 ├─ web_search (migrado de guard_gemini.py)
 ├─ call_strategy (pipeline|debate — envolvendo guard_pipeline.py e debate.py)
 └─ call_agent (já existe, passa a funcionar pra todos)

Todos os tools passam por:
 - Pydantic input/output schema
 - tool_call_id idempotente
 - preview + require_confirm quando destrutivo
 - whitelist por Environment
 - logs estruturados (agent_name, session_id, turn_id, tool_name, duration_ms, cost)
```

---

## 3. Contrato Agent (Pydantic)

Novo arquivo mínimo em `jarvas/agents/base.py`:

```python
class AgentResult(BaseModel):
    content: str
    model: str
    tool_calls: list[ToolCallRecord] = []
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    confidence: float | None = None   # pro miner/análise
    metadata: dict = {}

class AgentProtocol(Protocol):
    name: str
    role: str                          # system_prompt canônico
    model: str
    tools: list[str]
    memory_scope: Literal["session","project","global"] = "session"
    can_delegate_to: list[str] = []
    def run(self, message: str, ctx: SessionContext) -> AgentResult: ...
```

`AgentRecord` em `managed/models.py` é estendido com `memory_scope` e `role` (alias de `system_prompt`), mantendo compatibilidade.

---

## 4. Agents formalizados (adapters finos, ~30 linhas cada)

Registry em `jarvas/agents/registry.py`. Cada adapter envolve código existente sem reescrever:

| name | fonte da lógica | tools |
|---|---|---|
| `hermes` | `jarvas/hermes_client.py` | `call_agent`, `call_strategy`, `web_search` |
| `gemini_analyst` | `jarvas/guard_gemini.py` | `web_search`, `file_read` |
| `deepseek_coder` | `jarvas/guard_deepseek.py` | `file_read`, `file_edit`, `bash` |
| `autoescola_specialist` | `jarvas/routes/autoescola_router.py` + `autoescola_data.py` | `file_read` |
| `uiux_specialist` | skill externa `ui-ux-pro-max-skill-main/` (carregada via `AgentRecord.skills`) | `file_read`, `file_edit` |
| `memory_miner` | `jarvas/miners/conversation_miner.py` | `mempalace_add` |
| `vscode_executor` | já existe em `managed/runtime.py` | `vscode_*`, `bash` |
| `file_editor` | `jarvas/file_editor.py` + `file_processor.py` | `file_read`, `file_edit` |

---

## 5. Fases (cada uma é um PR reversível via feature flag)

### Fase 1 — Contrato Agent + Registry (sem mudar comportamento)

**Entregável:** criar `jarvas/agents/{base,registry}.py` + `jarvas/agents/adapters/*.py`. Orchestrator continua com `_HANDLERS`.

- Novos arquivos:
  - `jarvas/agents/base.py` (`AgentProtocol`, `AgentResult`, `ToolCallRecord`)
  - `jarvas/agents/registry.py` (`get_agent(name)`, `register(agent)`, lista default)
  - `jarvas/agents/adapters/hermes.py`, `gemini_analyst.py`, `deepseek_coder.py`, `memory_miner.py`, `file_editor.py`, `autoescola.py`, `uiux.py`
- Sem edição em `orchestrator.py` ainda.
- **Testes**: `tests/test_agents_registry.py`, `tests/test_agent_adapters.py`.
- **Aceite**: `get_agent("hermes").run("oi", ctx)` produz mesma saída que `hermes_chat("oi")`.

### Fase 2 — Supervisor dispatcher (feature flag `JARVAS_USE_SUPERVISOR`)

**Entregável:** `jarvas/agents/supervisor.py`; `orchestrator.process()` passa a chamar supervisor quando flag ligada.

- Supervisor mapeia Intent → agent name:
  - `CHAT` → `hermes` · `PIPELINE` → `hermes` com tool `call_strategy("pipeline")` · `DEBATE` → `hermes` com tool `call_strategy("debate")` · `FILE_READ/EDIT` → `file_editor` · `ATTACH/OCR` → `file_editor` · `SEARCH_WEB` → `gemini_analyst` · `STORE_MEMORY` → `memory_miner` · `SET_PROJECT` → contexto direto (sem agent).
- Flag `JARVAS_USE_SUPERVISOR=0` preserva 100% comportamento antigo.
- **Testes**: `tests/test_supervisor.py` (intent → agent correto), snapshots do orchestrator antes/depois devem bater.
- **Aceite**: todos os testes atuais em `/tests/` passam sem edição, com flag ligada e desligada.

### Fase 3 — Unificação com `managed/` (registro persistido)

**Entregável:** guards registrados como `AgentRecord` em `managed/store.py`; strategies viram tools.

- Migração única em `managed/startup.py`: registra `hermes`, `gemini_analyst`, `deepseek_coder`, `memory_miner`, `autoescola_specialist`, `uiux_specialist`, `file_editor` como `AgentRecord` persistidos.
- `jarvas/guard_pipeline.py` exposto como `PipelineStrategy` + registrado como tool `call_strategy` em `managed/toolset.py`.
- `jarvas/debate.py` exposto como `DebateStrategy` + tool `call_strategy`.
- API REST `/v1/sessions` passa a aceitar qualquer agent registrado (não só Ollama).
- **Testes**: `tests/test_managed_unification.py` (cria sessão com `hermes` via REST, valida SSE), `tests/test_strategies.py` (call_strategy pipeline/debate).
- **Aceite**: `POST /v1/sessions {agent_id: hermes_id}` + `POST /messages` funciona end-to-end com streaming.

### Fase 4 — Tool execution unificada + hardening

**Entregável:** todas as ferramentas passam pelo registry único `managed/toolset.py` com Pydantic, idempotência, preview, whitelist, sandbox.

- Migrar `file_editor.py`, `file_processor.py`, `web_search` para `managed/toolset.py` como tools Pydantic.
- Cada tool ganha:
  - Schema Pydantic de input/output.
  - `tool_call_id` determinístico (hash do call) para idempotência.
  - `require_confirm: bool` e `preview` (diff/artifact) em tools destrutivas (`file_edit`, `vscode_edit`, `bash`, `vscode_terminal`).
  - `allowed_tools` por `EnvironmentRecord` (whitelist).
  - Detecção de padrões sensíveis (regex credenciais/tokens) em conteúdo lido.
  - Timeout configurável por tool (`timeout_s`), cancelamento via `/v1/sessions/{id}/tool_cancel`.
- Logs estruturados: `agent_name`, `session_id`, `turn_id`, `tool_name`, `duration_ms`, `is_error`, `workspace_path`, `cost_usd`.
- Endpoint de debug: `/v1/sessions/{id}/dump` (histórico, tool calls, delegations).
- MemPalace: adicionar metadados `agent_name`, `delegation_path`, `confidence`, `hash_conteudo` no `/hmem add`.
- **Testes**: `tests/test_toolset_hardened.py` (preview, whitelist, idempotência, sandbox), `tests/test_security_sensitive_patterns.py`.
- **Aceite**: `file_edit` sem `require_confirm=true` falha em ambiente default; credenciais detectadas são mascaradas; retry de callback VSCode é idempotente.

---

## 6. Arquivos críticos

**Modificar:**
- `/home/user/Jarvas-agent/jarvas/orchestrator.py` — entry point usa supervisor
- `/home/user/Jarvas-agent/jarvas/managed/models.py` — estender `AgentRecord` com `memory_scope`
- `/home/user/Jarvas-agent/jarvas/managed/runtime.py` — aceitar strategies como tools
- `/home/user/Jarvas-agent/jarvas/managed/toolset.py` — registry unificado, hardening
- `/home/user/Jarvas-agent/jarvas/managed/startup.py` — registrar agents default
- `/home/user/Jarvas-agent/jarvas/guard_pipeline.py` — expor como `PipelineStrategy`
- `/home/user/Jarvas-agent/jarvas/debate.py` — expor como `DebateStrategy`
- `/home/user/Jarvas-agent/jarvas/mempalace_client.py` — metadados ricos no add
- `/home/user/Jarvas-agent/pyproject.toml` — bump para 0.5.0

**Criar (mínimos):**
- `/home/user/Jarvas-agent/jarvas/agents/__init__.py`
- `/home/user/Jarvas-agent/jarvas/agents/base.py`
- `/home/user/Jarvas-agent/jarvas/agents/registry.py`
- `/home/user/Jarvas-agent/jarvas/agents/supervisor.py`
- `/home/user/Jarvas-agent/jarvas/agents/strategies.py` (Pipeline + Debate wrappers)
- `/home/user/Jarvas-agent/jarvas/agents/adapters/{hermes,gemini_analyst,deepseek_coder,memory_miner,file_editor,autoescola,uiux,vscode_executor}.py`

**Reusar (sem alterar interface):**
- `jarvas/hermes_client.py`, `guard_gemini.py`, `guard_deepseek.py`, `miners/conversation_miner.py`, `routes/autoescola_router.py`, `file_editor.py`, `file_processor.py`, `intent_parser.py`.

---

## 7. Integração com `logica refatorada Jarvas.md`

A formalização multi-agente é o **veículo** do hardening proposto naquele plano — tudo aplicado uma vez:

| Item do plano refatorado | Onde cai na v0.5.0 |
|---|---|
| Pydantic `LearningsOut`, schemas validados | `AgentResult` + `ToolCallRecord` em `agents/base.py` (Fase 1) |
| Idempotência de `tool_call_id`, retry/backoff | `managed/toolset.py` unificado (Fase 4) |
| Preview + `require_confirm` em `vscode_edit` | tool registry hardened (Fase 4) |
| Whitelist `bash`/terminal por workspace | `EnvironmentRecord.allowed_tools` (Fase 4) |
| Detecção de segredos antes de minerar/salvar | tool hook em `file_read`/`memory_miner` (Fase 4) |
| Metadados ricos no MemPalace | `mempalace_client.py` (Fase 4) |
| Logs estruturados, `/sessions/{id}/dump` | observabilidade (Fase 4) |
| Tool discovery dinâmica pro Gemma | `toolset.list_tools()` com metadados (Fase 4) |
| Confidence + evidence no miner | `AgentResult.confidence` + `metadata.evidence` (Fase 1+4) |

---

## 8. Riscos e mitigações

- **Latência (N agents = N chamadas)**: supervisor decide single-agent por padrão; pipeline é opt-in via intent. `ThreadPoolExecutor` atual preservado na `PipelineStrategy`.
- **Custo OpenRouter**: classificação de intent continua local (`intent_parser.py` por regex); só chama LLM quando necessário. Adicionar cache semântico de resposta (hash do prompt+modelo) em Fase 4.
- **Loops de delegação**: reusar `MAX_DEPTH=3` e `MAX_CYCLES=10` já em `runtime.py`; supervisor aplica os mesmos limites.
- **Regressão de comportamento**: feature flag `JARVAS_USE_SUPERVISOR` em Fase 2; snapshots dos testes atuais devem bater byte-a-byte com flag off.
- **Migração de dados Supabase** (Fase 3): script idempotente em `managed/startup.py` — se agent default já existe por `name`, não duplica.
- **Debug difícil**: endpoint `/v1/sessions/{id}/dump` + logs com `session_id`+`turn_id`+`agent_name` (Fase 4).
- **Over-engineering**: nenhuma dependência nova; sem framework; adapters são ~30 linhas cada.

---

## 9. Verificação

**Testes existentes que devem continuar passando sem edição** (regressão):
- `tests/test_orchestrator.py`
- `tests/test_intent_parser.py`
- `tests/test_guard_pipeline.py`
- `tests/test_debate.py`
- `tests/test_router.py`
- `tests/test_hermes_client.py`
- `tests/test_guard_gemini.py`
- `tests/test_guard_deepseek.py`
- `tests/test_file_editor.py`
- `tests/test_file_processor.py`
- `tests/test_memory_writer.py`
- `tests/test_mempalace_client.py`
- `tests/test_cli.py`
- `tests/test_commands.py`
- `tests/test_context.py`

**Novos testes por fase:**
- Fase 1: `test_agents_registry.py`, `test_agent_adapters.py`
- Fase 2: `test_supervisor.py`, `test_orchestrator_with_supervisor.py`
- Fase 3: `test_managed_unification.py`, `test_strategies.py`
- Fase 4: `test_toolset_hardened.py`, `test_security_sensitive_patterns.py`, `test_idempotency.py`, `test_preview_confirm.py`

**Smoke tests end-to-end:**
- `python -m jarvas` → mensagens de cada intent (`"oi"`, `"debate sobre X"`, `"edite arquivo foo.py"`, `"#/caminho/projeto"`, `"pesquise sobre Y"`, `"armazene isso"`) — saída igual antes/depois em cada fase.
- `JARVAS_USE_SUPERVISOR=0 pytest -q` → tudo verde.
- `JARVAS_USE_SUPERVISOR=1 pytest -q` → tudo verde.
- REST: `POST /v1/sessions` + `POST /v1/sessions/{id}/messages` com `agent_id=hermes_id`, validar SSE stream com `agent.tool_use` e `tool_result`.
- VSCode extension (`jarvas-vscode/`): callback de tool continua funcionando; retry idempotente não duplica edit.

---

## 10. Critérios de aceite da v0.5.0 (final)

- [ ] Um único `AgentProtocol` e `AgentResult` Pydantic usados em todo o sistema.
- [ ] `orchestrator.process()` delega ao Supervisor; `_HANDLERS` removido.
- [ ] `hermes`, `gemini_analyst`, `deepseek_coder`, `memory_miner`, `file_editor`, `autoescola_specialist`, `uiux_specialist`, `vscode_executor` registrados como `AgentRecord` persistidos.
- [ ] `PipelineStrategy` e `DebateStrategy` invocáveis via tool `call_strategy`.
- [ ] Todas as ferramentas passam por `managed/toolset.py` com Pydantic, idempotência, preview/whitelist.
- [ ] Detecção de segredos ativa em `file_read` e `memory_miner`.
- [ ] MemPalace recebe `agent_name`, `delegation_path`, `confidence`, `hash_conteudo`.
- [ ] `/v1/sessions/{id}/dump` disponível; logs estruturados com `agent_name`+`session_id`+`turn_id`.
- [ ] `pyproject.toml` em `0.5.0`; `README.md` e `docs/jarvas-manual.html` atualizados.
- [ ] Todos os testes (antigos + novos) verdes.
- [ ] Feature flag removida na tag final — `v0.5.0` já roda 100% via supervisor.
