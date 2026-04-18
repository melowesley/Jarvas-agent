# Jarvas

Assistente de IA distribuído com múltiplos guardas especializados, roteamento inteligente de modelos, sistema de agentes gerenciáveis, memória persistente e **mineração automática de progresso**.

---

## Visão Geral

Jarvas é um assistente de linha de comando que orquestra diferentes modelos de IA de acordo com o tipo de tarefa. Em vez de depender de um único modelo, ele roteia cada mensagem para o modelo mais adequado e expõe guardas especializados (Gemini e DeepSeek) para tarefas específicas.

A versão **0.5.0** (final) introduz:
- **Multi-agente formal** — `AgentProtocol` Pydantic, Supervisor único (`jarvas.agents.supervisor`), registry de agentes (`hermes`, `gemini_analyst`, `deepseek_coder`, `memory_miner`, `file_editor`, `autoescola_specialist`, `uiux_specialist`, `vscode_executor`).
- **Estratégias como tools** — `PipelineStrategy` e `DebateStrategy` invocáveis via `call_strategy` no toolset unificado.
- **Tool registry hardened** — `managed/toolset.py` com schemas Pydantic, idempotência (`tool_call_id` determinístico), preview/`require_confirm` em tools destrutivas, whitelist por Environment, detecção/masking de segredos.
- **Observabilidade** — endpoint `GET /v1/sessions/{id}/dump` (snapshot completo de debug) + logs estruturados JSON em stderr (`agent_name`, `session_id`, `turn_id`, `tool_name`, `duration_ms`). Desligável via `JARVAS_STRUCTURED_LOGS=0`.
- **MemPalace enriquecido** — metadados `agent_name`, `delegation_path`, `hash_conteudo` (dedupe), `confidence` em cada aprendizado minerado.

Versões anteriores:
- **0.3.0** — Backend gerenciado (FastAPI) com sessões isoladas e Chat UI; agente local via Ollama/Gemma com ferramentas VSCode nativas; mineração automática de progresso.

```
você > Como funciona o roteamento do Jarvas?
Jarvas (anthropic/claude-3.5-sonnet) — análise automática

você > /g resuma os pontos principais do debate
Gemini: ...

você > /session list
- assistente_ti (id_123)
- analista_dados (id_456)
```

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                      CLI (cli.py)                       │
│               prompt_toolkit + rich                     │
└──────────────────────┬──────────────────────────────────┘
                       │
               ┌───────▼────────┐
               │  Slash command? │
               └───┬────────┬───┘
                  sim      não
                   │        │
                   ▼        ▼
            commands.py  hermes_client.py
            (despachante) (OpenRouter)
                   │
         ┌─────────┴──────────────────────┐
         │                                │
         ▼                                ▼
 guard_gemini.py                 guard_deepseek.py
 (Google Gemini)                 (DeepSeek via API)
 + mine_conversation()           + mine_code()
         │                                │
         └──────────────┬─────────────────┘
                        ▼
                  miners/conversation_miner.py
                  (orquestrador de mineração)
                        │
                        ▼
               mempalace_client.py
               (MemPalace — ChromaDB)
                        │
                        ▼
                  supabase_client.py
                  (logs — Supabase)
```

### Componentes

| Módulo | Responsabilidade |
|---|---|
| `cli.py` | Interface interativa, parsing de argumentos e inicialização do servidor. |
| `api.py` | Servidor REST (FastAPI) com sessões gerenciadas e Chat UI. |
| `router.py` | Detecção de tipo de tarefa, seleção de modelo dinâmico. |
| `hermes_client.py` | Comunicação com OpenRouter (chat principal). |
| `guard_gemini.py` | Guarda Gemini — análise, web search e **mineração de diálogos**. |
| `guard_deepseek.py` | Guarda DeepSeek — estruturação, indexação e **mineração de código**. |
| `miners/conversation_miner.py` | Orquestrador de mineração: aciona Gemini/DeepSeek em background após cada sessão. |
| `miners/models.py` | Modelos Pydantic: `LearningsOut`, `CodeMineOut` — validação do output dos miners. |
| `debate.py` | Debate multi-agente entre Gemini e DeepSeek. |
| `commands.py` | Despachante de slash commands para REPL. |
| `mempalace_client.py` | Cliente do MemPalace (sistema de memória semântica). |
| `supabase_client.py` | Persistência resiliente no Supabase. |
| `managed/` | Agentes gerenciáveis, sessões SSE, ferramentas VSCode nativas. |

---

## Mineração Automática de Progresso

Ao final de cada conversa (sessão gerenciada ou `/chat` legado), o Jarvas dispara em background:

1. **Gemini** analisa o diálogo e extrai aprendizados concretos — o que funcionou, erros com causa, workarounds — com `confidence` score.
2. **DeepSeek** extrai snippets de código, classifica funcionou/falhou e redige credenciais detectadas automaticamente.
3. Os resultados são salvos no **MemPalace** (wing `jarvas`, rooms `learnings` / `code`) com metadados: `session_id`, `timestamp`, `confidence`.

Sessões curtas (< 4 mensagens) e resultados com `confidence < 0.3` são ignorados.

```
conversa encerrada
      │
      ▼
  mine(messages)
      ├── Gemini → LearningsOut {aprendizados, falhas, progresso, confidence}
      │   └── se confidence ≥ 0.3 e progresso ≠ "false"
      │       → hmem add jarvas learnings ...
      │
      └── (se há código) DeepSeek → CodeMineOut {snippets funcionou/falhou}
          └── se confidence ≥ 0.3
              → hmem add jarvas code ...
```

---

## Roteamento de Modelos (via Hermes)

| Tipo | Palavras-chave (exemplos) | Modelo Padrão |
|---|---|---|
| `analysis` | analise, compare, explica, resumo | `anthropic/claude-3.5-sonnet` |
| `vision` | imagem, foto, ocr, screenshot | `openai/gpt-4o` |
| `code` | python, html, código, script, função | `meta-llama/llama-3.3-70b-instruct` |
| `chat` | *(padrão)* | `nousresearch/hermes-3-llama-3.1-70b` |

---

## Requisitos

- Python 3.11+
- Conta no [OpenRouter](https://openrouter.ai) com créditos
- Conta no [Google AI Studio](https://aistudio.google.com) com billing ativado
- Conta no [DeepSeek](https://platform.deepseek.com) com créditos
- Projeto no [Supabase](https://supabase.com) (para persistência)
- **Opcional:** [Ollama](https://ollama.com) com `gemma4` ou `llama3` para agente local

---

## Instalação

```bash
git clone <url-do-repositório>
cd jarvas
pip install -e .
```

---

## Configuração

Crie um arquivo `.env` na raiz do projeto:

```env
# OpenRouter — chat principal e Hermes
OPENROUTER_API_KEY=sk-or-...

# Google Gemini — Guarda Gemini
GEMINI_API_KEY=AIzaSy...

# DeepSeek — Guarda DeepSeek
DEEPSEEK_API_KEY=sk-...

# Supabase — persistência
SUPABASE_URL=https://<projeto>.supabase.co
SUPABASE_KEY=eyJ...
```

### Configuração do Supabase

```sql
CREATE TABLE public.conversations (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id text NOT NULL,
    role text NOT NULL,
    content text NOT NULL,
    model text,
    task_type text,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE public.guard_logs (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    guard text NOT NULL,
    input text NOT NULL,
    output text NOT NULL,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE public.debate_logs (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    topic text NOT NULL,
    rounds jsonb NOT NULL,
    consensus text NOT NULL,
    created_at timestamptz DEFAULT now()
);

ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.guard_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.debate_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_anon_insert_conversations" ON public.conversations FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "allow_anon_insert_guard_logs"    ON public.guard_logs    FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "allow_anon_insert_debate_logs"   ON public.debate_logs   FOR INSERT TO anon WITH CHECK (true);
```

---

## Sintaxe na Superfície (PowerShell / Terminal)

A superfície do Jarvas oferece quatro modos de entrada diretos, sem entrar no REPL:

```bash
jarvas <pergunta>                           # Chat único, retorna resposta
jarvas /help                                # Lista todos os slash commands
jarvas --in C:\caminho\do\projeto          # Abre REPL ancorado no projeto
jarvas continuar <data> <hora>              # Restaura contexto anterior
```

#### Notas importantes

- **Mensagens com quebras de linha no PowerShell:** Se você colar uma mensagem com `\n`, o PowerShell quebra em múltiplas linhas e cada uma vira um comando separado (erro: "O termo 'de' não é reconhecido..."). **Solução:**
  - Envolver em aspas: `jarvas "pergunta com várias linhas"` (PowerShell mantém como 1 argumento)
  - Ou entrar no REPL (`jarvas` + Enter) e colar lá
  - Ou usar `jarvas --in <projeto>` para ficar no REPL interativo

- **Slash commands na superfície:** `jarvas /modelos`, `jarvas /debate sobre X`, etc. funcionam igual ao REPL — eles despacham para o mesmo despachante interno.

#### No interior do REPL

Uma vez dentro do REPL (após `jarvas` + Enter ou `jarvas --in <projeto>`), você tem diálogo contínuo:

```bash
você > sua pergunta aqui
Jarvas (hermes) — resposta...

você > /help
[lista de comandos]

você > /debate sobre Python vs JavaScript
[debate multi-agente]
```

---

## Modos de Uso

### 1. Terminal Interativo (CLI)

```bash
jarvas                            # Modo REPL contínuo
jarvas "Como funciona X?"         # Pergunta direta
jarvas continuar ontem 15h        # Restaurar sessão anterior
jarvas --in C:\caminho\projeto    # REPL ancorado em um projeto
```

### 2. Interface Web e Servidor Gerenciado

```bash
jarvas --managed
# Acesse: http://localhost:8000
```

Você também pode especificar uma porta personalizada:

```bash
jarvas --managed --port 3000
# Acesse: http://127.0.0.1:3000
```

#### Por que isso importa?

- **Conflito de portas**: Se você já tem outro serviço rodando na porta 8000 (como outro servidor local, Docker, etc.), o Jarvas não conseguirá iniciar. Mudar para 3000 (ou outra porta livre) resolve.
- **Firewalls/segurança**: Algumas redes corporativas ou antivírus bloqueiam portas padrão (8000, 8080). Usar uma porta menos comum (ex. 3000, 5000, 8081) pode evitar bloqueios.
- **Organização pessoal**: Se você trabalha com múltiplos projetos locais, pode padronizar: Projeto A → porta 3000, Projeto B → porta 3001, Jarvas → porta 8000 (ou outra).
- **Testes simultâneos**: Pode executar duas instâncias do Jarvas ao mesmo tempo em portas diferentes (ex.: uma para desenvolvimento, outra para testes).

#### Dica extra:
Para verificar portas em uso no Windows: `netstat -ano | findstr :8000`  
No Linux/Mac: `lsof -i :8000`

O Chat UI em `localhost:8000` inclui:
- Seletor de agentes com status de disponibilidade (Ollama / Gemini / OpenRouter)
- Botões de comando para guardas, MemPalace e debate
- Chips de prompt rápido para iniciantes

### 3. Agente Local (Ollama)

```bash
# Instalar Ollama e baixar o modelo
ollama pull gemma4

# O agente "gemma-local" é registrado automaticamente ao iniciar --managed
jarvas --managed
```

O agente `gemma-local` roda inteiramente offline e pode editar arquivos no VSCode diretamente via ferramentas nativas (`vscode_edit`, `vscode_open`, `vscode_terminal`).

### 4. 🎓 Autoescola — Tutoriais Práticos Interativos

Aprenda a "dirigir" o Jarvas através de 6 aulas progressivas e interativas:

```bash
jarvas --managed
# Abra http://localhost:8000/autoescola no navegador
```

**Curriculum:**
1. **Primeira Marcha** — Seu primeiro comando e roteamento automático
2. **Trocando Marchas** — Combinando guardas `/g` e `/d`
3. **Cruzamento Decisivo** — Debate multi-agente (`/debate`)
4. **Estacionando Memorias** — Usando MemPalace (`/hmem`)
5. **Piloto Automático** — Sessões gerenciadas (`/session`)
6. **Rally Completo** — Workflow real: pesquisa + debate + memória + delegação

Cada aula tem:
- **Cenário**: Problema real que motiva o aprendizado
- **Passos numerados**: Comandos exatos com explicações
- **Diagrama visual**: Fluxo de dados pelo sistema
- **Checkpoints**: Perguntas para testar entendimento
- **Armadilhas**: Erros comuns a evitar

O progresso é salvo automaticamente e você pode retomar de onde parou.

### 5. API REST

Com `--managed` ativo:

| Endpoint | Descrição |
|---|---|
| `GET /` | Chat UI |
| `GET /status` | Status dos backends (Ollama, Gemini, OpenRouter) |
| `POST /chat` | Chat principal (Hermes) |
| `POST /g` · `/g/web` | Guarda Gemini |
| `POST /d` · `/d/web` | Guarda DeepSeek |
| `POST /debate` | Debate multi-agente |
| `GET /v1/agents` | Listar agentes registrados |
| `POST /v1/sessions` | Criar sessão |
| `GET /v1/sessions/{id}/stream` | Stream SSE da sessão |

---

## Slash Commands (REPL)

### Guardas

```
/g <prompt>          Chat direto com Gemini
/g web <busca>       Gemini pesquisa e resume um tópico
/d <prompt>          Chat direto com DeepSeek
/d web <busca>       DeepSeek pesquisa e resume um tópico
```

### Sessões Gerenciadas

```
/session list                  Listar agentes disponíveis
/session new <agent>           Criar nova sessão
/session send <id> <msg>       Enviar mensagem para sessão ativa
/session history <id>          Ver histórico da sessão
```

### Orquestrações

```
/debate <tópico>               Debate 3 rodadas Gemini vs DeepSeek
/hopen <model-id>              Forçar modelo específico
```

### MemPalace

```
/hmem status                   Status geral
/hmem list                     Listar wings
/hmem search <busca>           Busca semântica
/hmem add <wing> <room> <txt>  Adicionar memória
/hmem get <id>                 Recuperar drawer
/hmem del <id>                 Deletar drawer
/hmem graph                    Estatísticas do knowledge graph
/hmem kg <busca>               Consultar knowledge graph
```

---

## Detalhes dos Guardas

### Guarda Gemini (`gemini-2.5-flash`)
- **Chat e web search** — análise, síntese, busca em tempo real
- **Minerador de diálogos** — detecta padrões de progresso ("deu certo", "esse erro persiste"), retorna `LearningsOut` com score de confiança

### Guarda DeepSeek (`deepseek-chat`)
- **Chat e web search** — estruturação arquivística, indexação
- **Minerador de código** — classifica snippets funcionou/falhou, redige credenciais detectadas (regex `api_key`, `token`, `bearer`, etc.)

---

## Persistência

| Destino | Conteúdo |
|---|---|
| Supabase `conversations` | Histórico Hermes com session_id, modelo e tipo de tarefa |
| Supabase `guard_logs` | Input/output dos guardas Gemini e DeepSeek |
| Supabase `debate_logs` | Transcrições de debates com consenso |
| MemPalace `jarvas/learnings` | Aprendizados minerados pelo Gemini (confidence ≥ 0.3) |
| MemPalace `jarvas/code` | Snippets minerados pelo DeepSeek (sem credenciais) |

---

## Testes

```bash
pytest tests/
```

| O que testa | Arquivo |
|---|---|
| Parsing CLI, REPL e Uvicorn hook | `test_cli.py` |
| Comandos e roteamento API | `test_commands.py` |
| Comportamento dos guardas | `test_guard_gemini.py`, `test_guard_deepseek.py` |
| Lógica de consenso no debate | `test_debate.py` |
| Roteamento de tarefas | `test_router.py` |
| Falhas silenciosas de DB | `test_supabase_client.py` |

---

## Licença

MIT
