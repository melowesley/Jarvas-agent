# Jarvas 0.4.0 — Design Spec

**Data:** 2026-04-15  
**Versão alvo:** 0.4.0 (versão oficial final)  
**Autor:** Wesley Melo de Oliveira

---

## 1. Visão Geral

Jarvas 0.4.0 transforma o assistente de IA distribuído em um sistema completo de aprendizado colaborativo. O usuário dialoga pelo terminal ou pela interface web — o Jarvas detecta automaticamente a intenção de cada mensagem, aciona os modelos corretos, edita arquivos do projeto, armazena aprendizados no MemPalace e persiste tudo no Supabase.

A metáfora central: **Jarvas é o roteador e mensageiro. Gemini e DeepSeek são os guardas. MemPalace é o cérebro que aprende. Supabase é o arquivo histórico.**

---

## 2. Arquitetura

### 2.1 Fluxo principal

```
Usuário (terminal ou web)
         ↓
   [intent_parser.py]
   Classifica a mensagem em um Intent tipado
         ↓
   [orchestrator.py]
   Tabela de dispatch: Intent → Handler
         ↓
┌────────────────────────────────────────────────────────┐
│ INTENT          │ HANDLER                              │
├────────────────────────────────────────────────────────┤
│ CHAT            │ hermes_client.chat()                 │
│ PIPELINE        │ guard_pipeline.run()                 │
│ DEBATE          │ debate.run_debate()                  │
│ FILE_READ       │ file_editor.read()                   │
│ FILE_EDIT       │ file_editor.edit()                   │
│ SET_PROJECT     │ context.set_project()                │
│ STORE_MEMORY    │ memory_writer.store()                │
│ ATTACH          │ attachment_handler.process()         │
│ OCR             │ ocr_agent.run()                      │
│ SEARCH_WEB      │ guard_gemini.web_search()            │
└────────────────────────────────────────────────────────┘
         ↓
   Resultado → terminal (rich) ou web (JSON via FastAPI)
         ↓
   Persistência → Supabase + MemPalace (conforme o tipo)
```

### 2.2 Camadas

```
jarvas/
  intent_parser.py      ← NEW: classifica intenção
  orchestrator.py       ← NEW: despacha para handler
  guard_pipeline.py     ← NEW: Hermes+Gemini+DeepSeek paralelo + síntese
  file_editor.py        ← NEW: lê/edita/escreve arquivos no disco
  memory_writer.py      ← NEW: extrai insights e grava no MemPalace
  attachment_handler.py ← NEW: PDF, Excel, Word, imagem
  ocr_agent.py          ← NEW: OCR de imagem → Excel
  context.py            ← NEW: estado global da sessão (projeto atual, histórico)
  cli.py                ← MODIFICADO: usa orchestrator
  api.py                ← MODIFICADO: novos endpoints, porta 8080, novos schemas
  supabase_client.py    ← MODIFICADO: novas tabelas
  static/chat.html      ← MODIFICADO: novo UI com botões de ação
  router.py             ← SEM ALTERAÇÃO
  debate.py             ← SEM ALTERAÇÃO
  hermes_client.py      ← SEM ALTERAÇÃO
  guard_gemini.py       ← SEM ALTERAÇÃO
  guard_deepseek.py     ← SEM ALTERAÇÃO
  mempalace_client.py   ← SEM ALTERAÇÃO
```

---

## 3. Intent Parser (`jarvas/intent_parser.py`)

### 3.1 Tipos de Intent

```python
@dataclass
class Intent:
    type: str           # ver lista abaixo
    raw: str            # mensagem original
    args: dict          # argumentos extraídos
```

| Tipo | Padrões detectados | args extraídos |
|------|-------------------|----------------|
| `SET_PROJECT` | `#/path`, `#C:/path`, `trabalhar em #` | `path` |
| `FILE_READ` | `leia`, `mostra`, `abra`, `ver o arquivo` + extensão | `path` (relativo ou absoluto) |
| `FILE_EDIT` | `edite`, `melhore`, `corrija`, `reescreva`, `refatore` + path/arquivo | `path`, `instruction` |
| `DEBATE` | `debate`, `peça um debate`, `debate sobre` | `topic` |
| `STORE_MEMORY` | `armazene`, `guarda isso`, `salva isso`, `memorize` | `scope` (padrão: últimas 5 msgs) |
| `ATTACH` | extensão `.pdf .xlsx .docx .jpg .jpeg .png` no texto | `path`, `file_type` |
| `OCR` | `ocr`, `extraia texto`, `leia a imagem`, `gere excel` | `path`, `output_path` |
| `SEARCH_WEB` | `pesquise`, `busque na web`, `procure sobre` | `query` |
| `PIPELINE` | `code`, `vision`, `analysis` (router.detect_task_type ≠ chat) | `task_type` |
| `CHAT` | tudo que não se encaixa acima | — |

### 3.2 Prioridade de detecção

```
SET_PROJECT > ATTACH > OCR > FILE_EDIT > FILE_READ > DEBATE > STORE_MEMORY > SEARCH_WEB > PIPELINE > CHAT
```

### 3.3 Interface

```python
def parse(mensagem: str, project_ctx: str | None) -> Intent:
    """Retorna o Intent mais específico para a mensagem."""
```

---

## 4. Orchestrator (`jarvas/orchestrator.py`)

Tabela de dispatch estática. Cada handler recebe `(intent, session_ctx)` e retorna `str` (resposta formatada para exibição).

```python
_HANDLERS: dict[str, Callable] = {
    "CHAT":         handle_chat,
    "PIPELINE":     handle_pipeline,
    "DEBATE":       handle_debate,
    "FILE_READ":    handle_file_read,
    "FILE_EDIT":    handle_file_edit,
    "SET_PROJECT":  handle_set_project,
    "STORE_MEMORY": handle_store_memory,
    "ATTACH":       handle_attach,
    "OCR":          handle_ocr,
    "SEARCH_WEB":   handle_search_web,
}

def process(mensagem: str, session_ctx: SessionContext) -> str:
    intent = parse(mensagem, session_ctx.project_path)
    handler = _HANDLERS[intent.type]
    return handler(intent, session_ctx)
```

---

## 5. Context Global (`jarvas/context.py`)

Estado da sessão compartilhado entre terminal e web:

```python
@dataclass
class SessionContext:
    session_id: str
    project_path: str | None       # seta via SET_PROJECT
    historico: list[dict]          # histórico de mensagens
    last_pipeline_result: dict | None   # último resultado do pipeline
    last_debate_result: dict | None     # último debate
```

---

## 6. Guard Pipeline (`jarvas/guard_pipeline.py`)

### 6.1 Comportamento

Acionado quando `intent.type == "PIPELINE"` (código, análise, visão técnica).

Executa **em paralelo** via `concurrent.futures.ThreadPoolExecutor`:

1. `hermes_client.chat(mensagem)` → `resp_hermes`
2. `guard_gemini.chat(mensagem)` → `resp_gemini`
3. `guard_deepseek.chat(mensagem)` → `resp_deepseek`

Depois, chama Hermes novamente para sintetizar:

```
prompt_sintese = f"""
Você recebeu 3 perspectivas sobre: "{mensagem}"

Hermes: {resp_hermes}
Gemini: {resp_gemini}
DeepSeek: {resp_deepseek}

Sintetize em uma resposta única, clara e objetiva. Aponte divergências se houver.
"""
sintese = hermes_client.chat(prompt_sintese)
```

### 6.2 Retorno

- **Terminal:** exibe apenas a síntese (Rich markdown)
- **Web:** retorna JSON com os 4 campos (`hermes`, `gemini`, `deepseek`, `sintese`) — UI exibe a síntese por padrão, com botão "Ver detalhes" que expande os três

### 6.3 Persistência

Salva na tabela `pipeline_results` (Supabase).

---

## 7. File Editor (`jarvas/file_editor.py`)

### 7.1 Leitura

```python
def read_file(path: str, project_base: str | None) -> str:
    """Lê arquivo relativo ao projeto ou absoluto. Retorna conteúdo."""
```

Resolve caminho: se `path` for relativo e `project_base` estiver definido, combina. Se não encontrar, retorna erro claro.

### 7.2 Edição

```python
def edit_file(path: str, instruction: str, project_base: str | None) -> dict:
    """
    1. Lê o arquivo
    2. Envia para guard_pipeline com a instrução de edição
    3. Aplica a versão editada direto no disco (sobrescreve)
    4. Gera diff (difflib.unified_diff)
    5. Salva em file_edits (Supabase)
    Retorna: {path, original, edited, diff}
    """
```

**Não cria backup automático.** O usuário testa e, se não funcionar, decide o próximo passo usando as ferramentas do Jarvas (debate, guards, pesquisa web).

### 7.3 Segurança

- Só lê/edita dentro do `project_path` definido ou caminhos absolutos explícitos
- Nunca edita arquivos `.env`, `.git/`, `*.key`, `*.pem`

---

## 8. Memory Writer (`jarvas/memory_writer.py`)

Acionado quando `intent.type == "STORE_MEMORY"`.

### 8.1 Processo

1. Pega as últimas N mensagens do `historico` (padrão N=5, configurável)
2. Inclui `last_pipeline_result` e `last_debate_result` se existirem
3. Envia para Hermes com prompt de extração:

```
Analise essas interações e extraia:
- O que funcionou bem
- O que falhou e por quê
- Decisões tomadas
- Padrões observados

Formato: JSON com chaves "acertos", "erros", "decisoes", "padroes"
```

4. Grava no MemPalace:
   - `wing`: `wing_code` se técnico, `wing_user` se comportamental
   - `room`: slug do nome do projeto atual (ou `general`)
   - `content`: resumo extraído em formato AAAK comprimido

5. Salva também na tabela `memory_logs` (Supabase)

---

## 9. Attachment Handler (`jarvas/attachment_handler.py`)

### 9.1 Tipos suportados

| Extensão | Biblioteca | Ação |
|----------|-----------|------|
| `.pdf` | `pymupdf` (fitz) | Extrai texto por página |
| `.xlsx`, `.xls` | `openpyxl` | Lê células e estrutura |
| `.docx` | `python-docx` | Extrai parágrafos e tabelas |
| `.jpg`, `.jpeg`, `.png` | `Pillow` | Prepara para OCR ou análise visual |

### 9.2 Fluxo

1. Detecta extensão → chama extrator correto
2. Envia conteúdo extraído para guard_pipeline com contexto do arquivo
3. Retorna análise
4. Salva na tabela `attachments` (Supabase)

---

## 10. OCR Agent (`jarvas/ocr_agent.py`)

### 10.1 Fluxo

1. Recebe caminho de imagem (`.jpg`, `.jpeg`, `.png`)
2. Usa `pytesseract` para extrair texto (requer Tesseract instalado no sistema)
3. Envia texto para Hermes para estruturação
4. Gera arquivo `.xlsx` no mesmo diretório da imagem com o texto estruturado
5. Retorna caminho do arquivo gerado

### 10.2 Dependências de sistema

```
Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki
Idiomas: por + eng
```

---

## 11. Web UI (`jarvas/static/chat.html`)

### 11.1 Layout

Interface de chat com dois painéis:

```
┌──────────────────────────────────────┐
│  JARVAS  v0.4.0          [status: ●] │
├──────────────────────────────────────┤
│  [Área de mensagens — scroll]        │
│                                      │
│  Mensagem do usuário                 │
│  ─────────────────────               │
│  ► Jarvas (síntese)                  │
│    [Ver detalhes ▼]                  │
│      Hermes: ...                     │
│      Gemini: ...                     │
│      DeepSeek: ...                   │
├──────────────────────────────────────┤
│  [Barra de ações rápidas]            │
│  🛡️Pipeline  ⚔️Debate  💾Armazene    │
│  📁Projeto  📄Ler  ✏️Editar          │
│  📎Anexar  🔍OCR→XLS  🌐WebSearch    │
├──────────────────────────────────────┤
│  [input text field]      [Enviar]    │
└──────────────────────────────────────┘
```

### 11.2 Comportamento dos botões

Cada botão preenche o campo de input com um template e foca no campo:

| Botão | Template inserido |
|-------|------------------|
| 🛡️ Pipeline | `analise o código: ` |
| ⚔️ Debate | `debate sobre: ` |
| 💾 Armazene | `armazene as últimas interações` |
| 📁 Projeto | `#` (usuário completa com o caminho) |
| 📄 Ler | `leia o arquivo: ` |
| ✏️ Editar | `edite o arquivo: ` |
| 📎 Anexar | abre file picker → insere caminho no input |
| 🔍 OCR→XLS | `ocr: ` (usuário completa com caminho da imagem) |
| 🌐 WebSearch | `pesquise: ` |

### 11.3 Porta

**Porta 8080** (`jarvas --managed --port 8080` ou padrão quando `--managed` for usado).

Terminal REPL (`jarvas` sem flags) permanece sem porta — CLI puro.

---

## 12. Supabase — Novas Tabelas

Executar no SQL Editor do Supabase:

```sql
-- Resultados do guard pipeline
CREATE TABLE pipeline_results (
  id          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  session_id  text        NOT NULL,
  user_message text       NOT NULL,
  task_type   text,
  hermes      text,
  gemini      text,
  deepseek    text,
  sintese     text,
  created_at  timestamptz DEFAULT now()
);

-- Edições de arquivo
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

-- Anexos processados
CREATE TABLE attachments (
  id                uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  session_id        text        NOT NULL,
  file_name         text        NOT NULL,
  file_type         text,
  extracted_content text,
  analysis          text,
  created_at        timestamptz DEFAULT now()
);

-- Log do MemPalace
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

---

## 13. Novos Endpoints API (`jarvas/api.py`)

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/pipeline` | Guard pipeline completo |
| `POST` | `/file/read` | Lê arquivo do projeto |
| `POST` | `/file/edit` | Edita arquivo no disco |
| `POST` | `/memory/store` | Grava no MemPalace |
| `POST` | `/attach` | Processa anexo |
| `POST` | `/ocr` | OCR de imagem → Excel |
| `GET`  | `/context` | Estado atual da sessão |
| `POST` | `/context/project` | Define projeto atual |

---

## 14. Dependências Novas

Adicionar ao `pyproject.toml` / `requirements.txt`:

```
pymupdf          # PDF
openpyxl         # Excel
python-docx      # Word
Pillow           # imagens
pytesseract      # OCR (wrapper Python)
difflib          # stdlib, sem adicionar
concurrent.futures # stdlib, sem adicionar
```

**Tesseract** deve ser instalado separadamente no Windows:
- Download: https://github.com/UB-Mannheim/tesseract/wiki
- Adicionar ao PATH
- Instalar pacotes de idioma `por` e `eng`

---

## 15. Mudanças em Arquivos Existentes

### `jarvas/cli.py`
- `_processar_mensagem` passa a chamar `orchestrator.process(mensagem, session_ctx)`
- Remove import direto de `commands.dispatch` para mensagens normais (slash commands continuam)
- Adiciona `SessionContext` global

### `jarvas/api.py`
- Porta padrão muda para **8080**
- Adiciona novos endpoints (seção 13)
- `POST /chat` passa a chamar `orchestrator.process()`

### `jarvas/supabase_client.py`
- Adiciona: `save_pipeline_result()`, `save_file_edit()`, `save_attachment()`, `save_memory_log()`

### `jarvas/commands.py`
- Sem alteração estrutural — slash commands continuam funcionando
- `dispatch()` continua como fallback para `/g`, `/d`, `/debate`, `/hmem`, `/session`

---

## 16. Versão e Identidade

```python
# cli.py e api.py
version = "0.4.0"
```

---

## 17. O que NÃO está neste escopo

- Interface gráfica desktop (além do HTML)
- Autenticação/multi-usuário
- Deploy em cloud (tudo roda local)
- Agente secretário para organizar MemPalace (Jarvas 0.5.0)
