# 🚀 Plano de Implementação: Integração Jarvas com Moltbook

**Status**: ✅ EXPERIMENTAL POC  
**Data**: 2026-04-18  
**Complexidade**: Baixa (~450 linhas)  
**Dependências**: httpx (já existe), apscheduler (novo)

---

## 📋 Resumo Executivo

Integração experimental do Jarvas com Moltbook (rede social para IAs):

- **Posts minerados**: 2x ao dia (08:00 + 20:00) com conteúdo do MemPalace
- **Heartbeat**: 2x ao dia em horários aleatórios distribuídos
- **Comando manual**: `/moltbook-post` (flexível: com/sem argumentos)
- **Rastreamento**: Status em MemPalace (não duplica posts)

---

## 🎯 Especificação Final

| Aspecto | Detalhes |
|---------|----------|
| **Tipo** | Experimental (POC) |
| **Conteúdo** | Posts mineados de aprendizados do MemPalace |
| **Frequência de Posts** | 2x/dia: 08:00 (aprendizados de ontem) + 20:00 (aprendizados de hoje) |
| **Heartbeat** | 2x/dia: manhã (06:00-09:00 aleatório) + noite (18:00-21:00 aleatório) |
| **Disparo Manual** | `/moltbook-post [periodo]` (com argumentos ou menu interativo) |
| **Status** | `/moltbook-status` (mostra stats e próximos eventos) |
| **Rastreamento** | Marca em MemPalace: `status: "posted"`, `posted_date`, `moltbook_post_id` |

---

## 🏗️ Arquitetura

```
┌─ SCHEDULER (APScheduler) ────────────────────┐
│                                               │
│ ├─ 06:00-09:00: Random Heartbeat            │
│ ├─ 08:00: Post learnings_yesterday          │
│ ├─ 18:00-21:00: Random Heartbeat            │
│ └─ 20:00: Post learnings_yesterday          │
│                                               │
└─────────────────────────────────────────────┘
           │
           ↓ Supervisor
           │
    ┌──────────────────────────┐
    │   MoltbookAgent (novo)   │
    │ ├─ publish_learning()    │
    │ ├─ send_heartbeat()      │
    │ └─ format_post()         │
    └──────────────────────────┘
           │
           ├─ MemPalace (busca + update)
           └─ Moltbook API (POST /feed, /heartbeat)
```

---

## 📦 Arquivos a Criar/Modificar

### 1️⃣ NOVO: `jarvas/agents/adapters/moltbook.py` (~180 linhas)

```python
"""MoltbookAgent - Publica aprendizados minerados no Moltbook"""
import os
import random
from datetime import datetime
from typing import Optional

from jarvas.agents.base import AgentProtocol, AgentResult
from jarvas.mempalace_client import get_mempalace_client
import httpx

class MoltbookAgent(AgentProtocol):
    name = "moltbook_publisher"
    role = "Publica aprendizados minerados no Moltbook e envia heartbeat"
    model = "moltbook_api/v1"
    
    def __init__(self):
        self.api_key = os.getenv("MOLTBOOK_API_KEY")
        self.user_id = os.getenv("MOLTBOOK_USER_ID", "Weslei_3423")
        self.base_url = os.getenv("MOLTBOOK_BASE_URL", "https://moltbook.com/api")
        self.mempalace = get_mempalace_client()
        
        if not self.api_key:
            raise ValueError("MOLTBOOK_API_KEY not configured in .env")
    
    async def run(self, message: str, ctx) -> AgentResult:
        """
        Executa operações Moltbook
        
        message examples:
        - "publish_learning:learnings_today"
        - "publish_learning:learnings_yesterday"
        - "send_heartbeat"
        """
        try:
            if message.startswith("publish_learning"):
                _, periodo = message.split(":")
                result = await self._publish_learning(periodo)
            elif message == "send_heartbeat":
                result = await self._send_heartbeat()
            else:
                result = {"error": f"Unknown command: {message}"}
            
            return AgentResult(
                content=result.get("message", "Operação Moltbook concluída"),
                model=self.model,
                agent_name=self.name,
                metadata=result
            )
        except Exception as e:
            return AgentResult(
                content=f"❌ Erro ao executar operação Moltbook: {str(e)}",
                model=self.model,
                agent_name=self.name,
                metadata={"error": str(e), "error_type": type(e).__name__}
            )
    
    async def _publish_learning(self, periodo: str) -> dict:
        """Publica aprendizados de um período específico"""
        # 1. Busca aprendizados em MemPalace
        learnings = self.mempalace.get_learnings_by_period(
            wing="jarvas",
            periodo=periodo,
            status_filter="not_posted"  # Só não postados
        )
        
        if not learnings:
            return {"message": f"Nenhum aprendizado não-postado em '{periodo}'"}
        
        # 2. Formata post
        post_text = self._format_post(learnings)
        
        # 3. Posta no Moltbook
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/feed",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "content": post_text,
                    "tags": ["learning", "jarvas", periodo],
                    "visibility": "public"
                },
                timeout=10.0
            )
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Moltbook API error: {response.status_code} - {response.text}")
        
        post_data = response.json()
        post_id = post_data.get("id")
        karma_gained = post_data.get("karma", 0)
        
        # 4. Marca aprendizados como postados em MemPalace
        for learning in learnings:
            self.mempalace.update_learning(
                learning["id"],
                {
                    "status": "posted",
                    "posted_date": datetime.now().isoformat(),
                    "moltbook_post_id": post_id
                }
            )
        
        return {
            "message": f"✅ Post criado com {len(learnings)} aprendizados!",
            "post_id": post_id,
            "learnings_posted": len(learnings),
            "karma_gained": karma_gained,
            "periodo": periodo
        }
    
    async def _send_heartbeat(self) -> dict:
        """Envia sinal de vida (heartbeat) para Moltbook"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/heartbeat",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "agent_id": "Jarvas",
                    "status": "online",
                    "timestamp": datetime.now().isoformat(),
                    "user_id": self.user_id
                },
                timeout=5.0
            )
        
        if response.status_code not in [200, 201, 204]:
            raise Exception(f"Heartbeat failed: {response.status_code}")
        
        return {
            "message": "💚 Heartbeat enviado com sucesso!",
            "status": "online",
            "timestamp": datetime.now().isoformat()
        }
    
    def _format_post(self, learnings: list) -> str:
        """Formata lista de aprendizados como post legível"""
        title = f"🧠 Aprendizados do Dia - {datetime.now().strftime('%d/%m')}"
        
        items = []
        for learning in learnings[:5]:  # Top 5
            confidence = learning.get("confidence", 0.8)
            emoji = "✅" if confidence > 0.7 else "⚠️"
            items.append(f"{emoji} {learning['titulo']}")
        
        body = "\n".join(items)
        footer = "#jarvas #learning #ia"
        
        return f"{title}\n\n{body}\n\n{footer}"
```

---

### 2️⃣ NOVO: `jarvas/moltbook_scheduler.py` (~120 linhas)

```python
"""Scheduler para Moltbook: posts 2x/dia + heartbeat 2x/dia distribuído"""
import os
import random
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

logger = logging.getLogger(__name__)

def create_moltbook_scheduler():
    """Cria scheduler com todos os jobs Moltbook"""
    scheduler = BackgroundScheduler()
    
    # ════════════════════════════════════════════════════════════
    # POSTS: 08:00 + 20:00
    # ════════════════════════════════════════════════════════════
    
    scheduler.add_job(
        _trigger_post,
        'cron',
        hour=8, minute=0,
        args=["learnings_yesterday"],
        id="moltbook_post_morning",
        name="Moltbook: Post matinal"
    )
    
    scheduler.add_job(
        _trigger_post,
        'cron',
        hour=20, minute=0,
        args=["learnings_yesterday"],
        id="moltbook_post_night",
        name="Moltbook: Post noturno"
    )
    
    # ════════════════════════════════════════════════════════════
    # HEARTBEAT: aleatório 06:00-09:00 + 18:00-21:00
    # ════════════════════════════════════════════════════════════
    
    hora_manha = random.randint(6, 8)
    minuto_manha = random.randint(0, 59)
    scheduler.add_job(
        _trigger_heartbeat,
        'cron',
        hour=hora_manha, minute=minuto_manha,
        id="moltbook_heartbeat_morning",
        name=f"Moltbook: Heartbeat manhã"
    )
    
    hora_noite = random.randint(18, 20)
    minuto_noite = random.randint(0, 59)
    scheduler.add_job(
        _trigger_heartbeat,
        'cron',
        hour=hora_noite, minute=minuto_noite,
        id="moltbook_heartbeat_night",
        name=f"Moltbook: Heartbeat noite"
    )
    
    scheduler.start()
    logger.info("✅ Moltbook scheduler iniciado")
    logger.info(f"  Posts: 08:00 + 20:00")
    logger.info(f"  Heartbeat: {hora_manha:02d}:{minuto_manha:02d} + {hora_noite:02d}:{minuto_noite:02d}")
    
    return scheduler

def _trigger_post(periodo: str):
    """Dispara publicação de aprendizados"""
    from jarvas.agents.supervisor import get_supervisor
    
    supervisor = get_supervisor()
    logger.info(f"📤 Disparando post Moltbook: {periodo}")
    
    try:
        result = supervisor.process(
            f"publish_learning:{periodo}",
            target_agent="moltbook_publisher"
        )
        logger.info(f"✅ Post concluído: {result.metadata}")
    except Exception as e:
        logger.error(f"❌ Erro ao postar: {e}")

def _trigger_heartbeat():
    """Dispara heartbeat"""
    from jarvas.agents.supervisor import get_supervisor
    
    supervisor = get_supervisor()
    logger.info("💚 Disparando heartbeat Moltbook")
    
    try:
        result = supervisor.process(
            "send_heartbeat",
            target_agent="moltbook_publisher"
        )
        logger.info(f"✅ Heartbeat enviado")
    except Exception as e:
        logger.error(f"❌ Erro ao enviar heartbeat: {e}")
```

---

### 3️⃣ NOVO: `jarvas/commands/moltbook_commands.py` (~100 linhas)

```python
"""Slash commands para Moltbook"""
from jarvas import commands
from jarvas.session import get_session
from jarvas.agents.supervisor import get_supervisor
import logging

logger = logging.getLogger(__name__)

PERIODOS_DISPONIVEIS = [
    ("learnings_today", "Aprendizados de hoje"),
    ("learnings_yesterday", "Aprendizados de ontem"),
    ("learnings_this_week", "Aprendizados da semana"),
    ("learnings_this_month", "Aprendizados do mês"),
]

@commands.register("/moltbook-post")
async def cmd_moltbook_post(session: get_session(), args: str = ""):
    """
    Publica aprendizados no Moltbook
    
    Uso:
      /moltbook-post learnings_today       # Direto
      /moltbook-post                       # Menu interativo
    """
    supervisor = get_supervisor()
    
    if args.strip():
        periodo = args.strip()
        if not any(p[0] == periodo for p in PERIODOS_DISPONIVEIS):
            opcoes = ', '.join(p[0] for p in PERIODOS_DISPONIVEIS)
            return f"❌ Período desconhecido: {periodo}\nOpções: {opcoes}"
    else:
        print("\n📋 Qual período quer postar?")
        for i, (periodo, descricao) in enumerate(PERIODOS_DISPONIVEIS, 1):
            print(f"  {i}. {descricao}")
        
        choice = input("Digite o número: ").strip()
        try:
            periodo = PERIODOS_DISPONIVEIS[int(choice) - 1][0]
        except (ValueError, IndexError):
            return "❌ Escolha inválida"
    
    try:
        result = supervisor.process(
            f"publish_learning:{periodo}",
            target_agent="moltbook_publisher"
        )
        return f"✅ {result.content}\n📊 Detalhes: {result.metadata}"
    except Exception as e:
        return f"❌ Erro ao publicar: {e}"

@commands.register("/moltbook-status")
async def cmd_moltbook_status(session: get_session()):
    """Mostra status de Jarvas no Moltbook"""
    from jarvas.mempalace_client import get_mempalace_client
    
    mempalace = get_mempalace_client()
    
    all_learnings = mempalace.get_learnings_by_period(
        wing="jarvas",
        periodo="all_time"
    )
    posted = [l for l in all_learnings if l.get("status") == "posted"]
    
    return f"""
🤖 Status Jarvas no Moltbook
━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 Total de aprendizados: {len(all_learnings)}
📤 Já postados: {len(posted)}
⏳ Aguardando publicação: {len(all_learnings) - len(posted)}

⏰ Próximos eventos:
  • 08:00: Post matinal
  • 20:00: Post noturno
  • Heartbeat: distribuído manhã + noite
"""
```

---

### 4️⃣ UPDATE: `.env`

Adicionar:

```bash
# Moltbook Integration
MOLTBOOK_API_KEY=sk-mb-xxxxxxxxxxxxx
MOLTBOOK_USER_ID=Weslei_3423
MOLTBOOK_BASE_URL=https://moltbook.com/api
```

---

### 5️⃣ UPDATE: `jarvas/agents/registry.py`

Registrar o novo adapter:

```python
from jarvas.agents.adapters.moltbook import MoltbookAgent

AGENTS_REGISTRY = {
    "hermes": HermesAgent(),
    "gemini_analyst": GeminiAnalystAgent(),
    "deepseek_coder": DeepSeekCoderAgent(),
    "moltbook_publisher": MoltbookAgent(),  # ← NOVO
    # ... resto
}
```

---

### 6️⃣ UPDATE: `jarvas/mempalace_client.py`

Adicionar 2 métodos:

```python
def get_learnings_by_period(self, wing: str, periodo: str, status_filter: str = None) -> list:
    """
    Busca aprendizados de período específico
    
    periodo: "today", "yesterday", "this_week", "this_month", "all_time"
    status_filter: "posted", "not_posted", None (qualquer um)
    """
    # Implementação que busca do ChromaDB/MemPalace com filtros de data
    # Retorna: [{"id": "...", "titulo": "...", "confidence": 0.8, "status": "not_posted"}, ...]
    ...

def update_learning(self, learning_id: str, updates: dict) -> None:
    """
    Atualiza aprendizado (ex: marcar como postado)
    
    updates: {"status": "posted", "posted_date": "2026-04-18T...", "moltbook_post_id": "..."}
    """
    # Implementação que atualiza registro em ChromaDB/MemPalace
    ...
```

---

### 7️⃣ UPDATE: `jarvas/api.py` ou `jarvas/cli.py`

Na inicialização, adicionar:

```python
from jarvas.moltbook_scheduler import create_moltbook_scheduler

# Na função de startup:
if os.getenv("MOLTBOOK_API_KEY"):
    create_moltbook_scheduler()
```

---

## 🚀 Passos de Implementação (Ordem)

1. ✅ Criar `jarvas/agents/adapters/moltbook.py` com MoltbookAgent
2. ✅ Atualizar `jarvas/agents/registry.py` para registrar
3. ✅ Criar `jarvas/moltbook_scheduler.py` com APScheduler
4. ✅ Criar `jarvas/commands/moltbook_commands.py` com slash commands
5. ✅ Atualizar `jarvas/mempalace_client.py` (2 novos métodos)
6. ✅ Atualizar `.env` com credenciais Moltbook
7. ✅ Integrar scheduler em `api.py` ou `cli.py`

---

## ✅ Checklist de Testes

- [ ] Validar que `apscheduler` está no `pyproject.toml`
- [ ] Testar `/moltbook-post learnings_today` (comando direto)
- [ ] Testar `/moltbook-post` (menu interativo)
- [ ] Testar `/moltbook-status` (mostra stats)
- [ ] Validar que aprendizados são marcados como "posted" em MemPalace
- [ ] Validar que scheduler acorda nos horários certos (logs)
- [ ] Testar heartbeat com mock se API não está pronta
- [ ] Validar que não há posts duplicados
- [ ] Testar erros 401/403 (são capturados e logados)

---

## 📦 Dependências

**Já existentes:**
- `httpx` ✅
- `python-dotenv` ✅

**Novo:**
- `apscheduler` - Adicionar ao `pyproject.toml` se não existir:
  ```toml
  apscheduler = "^3.10"
  ```

Validar:
```bash
pip list | grep apscheduler
```

---

## 🎯 Fluxo de Uso

### Automático (Scheduler)

```
08:00 AM → Scheduler acorda
       → Busca aprendizados de "learnings_yesterday"
       → Posta no Moltbook
       → Marca como "posted" em MemPalace

20:00 PM → Scheduler acorda
       → Busca aprendizados de "learnings_yesterday"
       → Posta no Moltbook
       → Marca como "posted" em MemPalace

06:xx AM (aleatório) → Heartbeat manhã
18:xx PM (aleatório) → Heartbeat noite
```

### Manual (Comandos REPL)

```bash
# Opção 1: Direto
jarvas > /moltbook-post learnings_today
✅ Post criado com 3 aprendizados!

# Opção 2: Menu
jarvas > /moltbook-post
📋 Qual período quer postar?
  1. Aprendizados de hoje
  2. Aprendizados de ontem
  3. Aprendizados da semana
  4. Aprendizados do mês
Digite o número: 1
✅ Post criado com 3 aprendizados!

# Status
jarvas > /moltbook-status
🤖 Status Jarvas no Moltbook
━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 Total de aprendizados: 42
📤 Já postados: 28
⏳ Aguardando publicação: 14
```

---

## 🚨 Notas Importantes

1. **Chave API**: Solicitar a `MOLTBOOK_API_KEY` antes de implementar
2. **Endpoints do Moltbook**: Confirmar que existem:
   - `POST /feed` (criar post)
   - `POST /heartbeat` (enviar sinal de vida)
3. **Rate Limiting**: Checar limites da API do Moltbook (posts/hour, etc)
4. **Qualidade**: Posts gerados (via aprendizados minerados) afetam Karma

---

## 📞 Próximas Ações

1. ✅ Analisar viabilidade (FEITO)
2. ⏳ Obter/validar `MOLTBOOK_API_KEY`
3. ⏳ Mapear endpoints exatos de Moltbook
4. ⏳ Implementar conforme plano acima
5. ⏳ Testar scheduler e comandos
6. ⏳ Deploy em branch `claude/jarvas-moltbook-analysis-aFwx5`

---

**Pronto para implementação! 🚀**
