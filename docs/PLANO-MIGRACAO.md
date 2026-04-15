# 🔄 Plano de Migração: DeepSeek → Gemini

**Data:** 2026-04-14  
**Status:** ✅ Planejado  
**Owner:** [A designar]  
**Repositório:** `github.com/org/guarda-migration`

---

## 📊 Visão Geral Executiva

### Objetivo
**Permitir que o Guarda Gemini execute a mesma lógica de processamento do DeepSeek**, adicionando redundância, flexibilidade e otimizando custos/latência.

### Benefícios Esperados
- ✅ Redundância: Ambos os guardas disponíveis em produção
- ✅ Flexibilidade: Escolher melhor modelo por caso de uso
- ✅ Eficiência: Otimizar custo/latência por tarefa
- ✅ Resiliência: Fallback automático em caso de falha

### Risco x Benefício
| Benefício | Risco |
|-----------|-------|
| Redundância de guardas | Resultados podem diferir (modelos distintos) |
| Otimização de custos | Maior complexidade operacional |
| Melhor resiliência | Duplicação de custos inicial |
| Flexibilidade de roteamento | Validação exigente |

---

## 💭 Feedback Crítico & Ajustes

### 1. "Lógica-Fonte" é Ambígua

**Problema:** DeepSeek é um modelo de IA, não código determinístico.

**O que você realmente quer extrair?**

| Opção | O quê | Dificuldade | Portabilidade |
|-------|-------|-------------|---------------|
| **A: Regras de Negócio** | if/then, parsers, lógica determinística | 🟢 Fácil | ⭐⭐⭐ |
| **B: Prompts (RECOMENDADO)** | System prompts, instruções que funcionam bem | 🟡 Médio | ⭐⭐⭐ |
| **C: Padrões de Processamento** | Parsing, classificação, steps sequenciais | 🟠 Complexo | ⭐⭐ |

**Recomendação:** Comece por **B (Prompts)** - é mais fácil de versionar e portável entre modelos.

### 2. Métrica "95% Matching" Não é Realista

**Problema:** Gemini e DeepSeek são modelos diferentes. Esperar respostas idênticas é ilusório.

**Métricas Realistas:**
- ✅ **Acuracidade na tarefa** (ex: classificação correta)
- ✅ **Satisfação do usuário** (sim/não, NPS)
- ✅ **Tempo de resposta** (p50, p95, p99)
- ✅ **Taxa de erro** (timeouts, mal-formado)
- ✅ **Custo por token** (impacto financeiro)

### 3. Falta Análise de Custo

**Problema:** DeepSeek é mais barato que Gemini. Precisa de business case.

```
Custo por 1000 tokens (2026):
  DeepSeek Chat:  $0.14 (input) + $0.56 (output)
  Gemini 2.5:     $0.075 (input) + $0.30 (output)

Volume esperado: 10k requisições/dia
  DeepSeek: ~$420/mês
  Gemini:   ~$225/mês

Delta: -$195/mês (economiza, não gasta mais)
```

### ✅ Ajustes Implementados
- [x] Foco em Prompts (não regras/código complexo)
- [x] Métricas realistas (acuracidade, não matching textual)
- [x] Análise de custo/ROI
- [x] Timeline mais agressiva (semana 1: decisão rápida)
- [x] Dashboard essencial (sucesso, latência, custo, fallback)

---

## 🎯 Fase 1: Definição & Isolamento da Lógica-Fonte

### Artefato 1: Catálogo de Prompts Efetivos

Em vez de especificação técnica complexa, criar um repositório versionado de prompts que funcionam bem.

```
deepseek_prompts/
├── classification/
│   ├── detect_intent.md (v1.2)
│   │   - Prompt original
│   │   - Taxa de sucesso: 94%
│   │   - Tempo médio: 250ms
│   │   - Casos de borda: 3 (list)
│   │
│   ├── extract_entities.md (v1.0)
│   └── score_confidence.md (v1.1)
│
├── generation/
│   ├── generate_response.md (v2.0)
│   └── format_output.md (v1.0)
│
└── CATALOG.md (índice com histórico)
```

### Artefato 2: Template para Cada Prompt

```markdown
# detect_intent.md

## Versão
v1.2 (atualizado 2026-04-14)

## Prompt Original
[Instrução exata usada no DeepSeek]

## Versão Otimizada
[Refinamentos para melhor portabilidade]

## Métricas
- Taxa de acerto: 94%
- Tempo médio: 250ms
- Casos falhando: 3 (ambiguous_intent, multi_intent, special_chars)

## Casos de Borda
- Intent vago: fallback para "general"
- Multi-intent: retornar top 3 ordenados por confiança
- Caracteres especiais: sanitizar antes de processar
- Input vazio: retornar erro estruturado
```

### Checklist Fase 1
- [ ] Extrair 15-20 prompts principais do DeepSeek
- [ ] Documentar cada um com template acima
- [ ] Medir taxa atual de sucesso para cada prompt
- [ ] Identificar pontos críticos (alta latência, baixa acuracidade)
- [ ] Versionar em Git com histórico de mudanças

---

## 🔍 Fase 2: Análise do Ambiente-Alvo (Gemini)

### Artefato 1: Comparativo DeepSeek vs Gemini

| Aspecto | DeepSeek | Gemini 2.5 Flash | Observação |
|---------|----------|------------------|------------|
| **Latência** | 150-300ms | 100-200ms | Gemini é mais rápido ⚡ |
| **Contexto Máximo** | 4k-8k tokens | 1M tokens | Gemini muito maior 📊 |
| **Web Search** | ❌ Não nativo | ✅ Nativo | Vantagem Gemini 🌐 |
| **Custo/1k tokens** | $0.14 input | $0.075 input | DeepSeek 2x mais barato 💰 |
| **Função Calling** | ✅ Sim | ✅ Sim | Ambos suportam ✅ |
| **JSON Mode** | ✅ Nativo | ⚠️ Experimental | DeepSeek mais confiável |

### Artefato 2: Limitações Conhecidas

#### Rate Limiting Gemini
```
Limite: 60 req/min (free tier)
        600 req/min (paid tier)

Estratégia de mitigação:
  1. Queue de requisições (Redis/RabbitMQ)
  2. Backoff exponencial (1s, 2s, 4s, 8s)
  3. Fallback para DeepSeek se timeout > 5s
  4. Circuit breaker (desativa após 10 erros)
```

#### Diferenças em Parsing de JSON
```
Problema: Gemini às vezes retorna JSON mal-formado

Solução:
  1. Usar JSON mode (experimental)
  2. Validar resposta com JSON Schema
  3. Retry com instrução mais clara ("ONLY OUTPUT JSON")
  4. Fallback para parsing manual com regex
```

#### Sensibilidade a Prompts
```
Gemini pode ser mais sensível à formulação do prompt.

Solução:
  1. Testar variações (5-10 versões)
  2. Usar exemplos few-shot mais explícitos
  3. Adicionar "thinking" steps (Chain of Thought)
  4. Ajustar temperatura conforme necessário
```

---

## 🗺️ Fase 3: Mapeamento & Arquitetura

### Artefato 1: Matriz de Compatibilidade

| Componente | Jarvas/DeepSeek | Equivalente Gemini | Gap | Solução |
|------------|-----------------|-------------------|-----|---------|
| Parser Query | Função Python | Prompt + regex | Sem equivalente direto | Abstrair em classe comum |
| Classificador | DeepSeek direto | Gemini + prompt | Respostas podem diferir | Normalizar output (enum) |
| Gerador Resposta | Template + DeepSeek | Template + Gemini | Qualidade pode variar | A/B test com usuários |
| Ranking/Scoring | Função Python | Prompt estruturado | Perda de precisão | Validar com threshold |
| Validação | Regex + lógica | Mesmo Regex + lógica | Perfeitamente mapeável | Reuso de código |

### Artefato 2: Arquitetura Proposta

```
┌─────────────────────────────────────────────────────────┐
│              CAMADA 1: NÚCLEO LÓGICO COMUM              │
│  ┌──────────────────────────────────────────────────┐  │
│  │ • query_processor.py (abstrato)                  │  │
│  │ • response_normalizer.py                         │  │
│  │ • common_schemas.py (Pydantic models)            │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│            CAMADA 2: ADAPTADORES DE PLATAFORMA          │
│  ┌──────────────────┐         ┌──────────────────────┐ │
│  │ deepseek_adapter │         │  gemini_adapter      │ │
│  │ (existente)      │         │  (novo)              │ │
│  │                  │         │ • prompt transformer │ │
│  │                  │         │ • response validator │ │
│  │                  │         │ • error handler      │ │
│  └──────────────────┘         └──────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│           CAMADA 3: ORQUESTRAÇÃO & ROTEAMENTO           │
│  ┌──────────────────────────────────────────────────┐  │
│  │ • router.py (escolhe DeepSeek ou Gemini)        │  │
│  │ • fallback.py (estratégia de fallback)          │  │
│  │ • circuit_breaker.py (proteção contra falhas)   │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│            CAMADA 4: OBSERVABILIDADE & LOGS             │
│  ┌──────────────────────────────────────────────────┐  │
│  │ • Prometheus (métricas)                          │  │
│  │ • Elasticsearch (logs estruturados)              │  │
│  │ • Grafana (dashboard)                            │  │
│  │ • Datadog/NewRelic (APM)                         │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## ⚙️ Fase 4: Implementação Iterativa

### Passo 1: Extrair Interface Comum

```python
# common/interface.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class QueryProcessor(ABC):
    """Interface comum para ambos adaptadores"""
    
    @abstractmethod
    async def parse_query(self, input_text: str) -> Dict[str, Any]:
        """
        Normalizar entrada do usuário
        
        Returns:
            {
                "original": "...",
                "cleaned": "...",
                "tokens": 42,
                "language": "pt-BR"
            }
        """
        pass

    @abstractmethod
    async def classify(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classificar intent/tipo de tarefa
        
        Returns:
            {
                "intent": "analysis|code|vision|chat",
                "confidence": 0.94,
                "entities": [...]
            }
        """
        pass

    @abstractmethod
    async def generate(self, classified: Dict[str, Any]) -> str:
        """
        Gerar resposta final
        
        Returns:
            Texto da resposta
        """
        pass

    @abstractmethod
    async def validate_output(self, output: str) -> bool:
        """Validar qualidade da resposta"""
        pass
```

### Passo 2: Adaptador Gemini

```python
# gemini_adapter/adapter.py

import asyncio
import json
from typing import Dict, Any
import google.generativeai as genai
from common.interface import QueryProcessor
from common.schemas import ParsedQuery, Classification

class GeminiAdapter(QueryProcessor):
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.max_retries = 3
        self.timeout = 10.0

    async def parse_query(self, input_text: str) -> Dict[str, Any]:
        """Parse usando Gemini com fallback para regex"""
        prompt = f"""
Analise a seguinte consulta do usuário e extraia:
- Texto original
- Texto limpo (sem especiais)
- Idioma detectado
- Número de tokens

Retorne como JSON válido.

Consulta: {input_text}
"""
        
        try:
            response = await asyncio.wait_for(
                self._call_gemini(prompt),
                timeout=self.timeout
            )
            parsed = json.loads(response)
            return ParsedQuery(**parsed).dict()
        except (json.JSONDecodeError, asyncio.TimeoutError) as e:
            # Fallback: parsing manual
            return self._parse_fallback(input_text)

    async def classify(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Classificar usando Gemini"""
        prompt = f"""
Classifique a seguinte consulta em uma destas categorias:
- analysis: análise de dados, insights
- code: programação, debugging
- vision: análise de imagens
- chat: conversas gerais

Retorne JSON com: {{"intent": "...", "confidence": 0.XX}}

Consulta: {parsed['cleaned']}
"""
        
        for attempt in range(self.max_retries):
            try:
                response = await self._call_gemini(prompt)
                result = json.loads(response)
                return Classification(**result).dict()
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Backoff exponencial

    async def generate(self, classified: Dict[str, Any]) -> str:
        """Gerar resposta com template"""
        prompt = self._build_generate_prompt(classified)
        
        try:
            response = await self._call_gemini(prompt)
            return response
        except Exception as e:
            raise RuntimeError(f"Gemini generation failed: {e}")

    async def validate_output(self, output: str) -> bool:
        """Validar saída"""
        # Checks básicos
        if not output or len(output) < 10:
            return False
        if output.count('\n') > 100:  # Muito quebra de linha
            return False
        return True

    async def _call_gemini(self, prompt: str) -> str:
        """Wrapper para chamar Gemini com tratamento de erro"""
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    top_p=0.9,
                    max_output_tokens=2048
                )
            )
            return response.text
        except Exception as e:
            raise RuntimeError(f"Gemini API error: {e}")

    def _parse_fallback(self, input_text: str) -> Dict[str, Any]:
        """Fallback para parsing com regex"""
        import re
        return {
            "original": input_text,
            "cleaned": re.sub(r'[^a-zA-Z0-9\s]', '', input_text),
            "tokens": len(input_text.split()),
            "language": "pt-BR"  # TODO: detectar realmente
        }

    def _build_generate_prompt(self, classified: Dict) -> str:
        """Construir prompt de geração baseado em classificação"""
        # Lógica aqui...
        pass
```

### Passo 3: Orquestrador com Fallback

```python
# router/orchestrator.py

import asyncio
from enum import Enum
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class Model(Enum):
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"

class GuardaOrchestrator:
    def __init__(self, deepseek_adapter, gemini_adapter, metrics):
        self.ds = deepseek_adapter
        self.gm = gemini_adapter
        self.metrics = metrics
        self.circuit_breaker = {
            Model.DEEPSEEK: 0,
            Model.GEMINI: 0
        }

    async def process(
        self,
        query: str,
        prefer_model: Optional[Model] = None,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Processar query com fallback automático
        
        Args:
            query: Consulta do usuário
            prefer_model: Preferência (None = automático)
            max_retries: Quantas vezes tentar fallback
            
        Returns:
            {
                "result": "...",
                "model_used": "deepseek|gemini",
                "latency_ms": 123,
                "fallback_occurred": bool,
                "success": bool
            }
        """
        
        start_time = asyncio.get_event_loop().time()
        
        # Escolher modelo
        model = prefer_model or self._choose_model_smart(query)
        
        # Tentar com fallback
        for attempt in range(max_retries):
            try:
                adapter = self.ds if model == Model.DEEPSEEK else self.gm
                
                # Verificar circuit breaker
                if self.circuit_breaker[model] > 5:
                    logger.warning(f"{model.value} circuit breaker ativo")
                    model = Model.DEEPSEEK if model == Model.GEMINI else Model.GEMINI
                    continue
                
                # Processar
                parsed = await adapter.parse_query(query)
                classified = await adapter.classify(parsed)
                result = await adapter.generate(classified)
                
                # Validar
                is_valid = await adapter.validate_output(result)
                if not is_valid:
                    raise ValueError("Validação falhou")
                
                # Sucesso!
                elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
                self.metrics.record_success(model.value, elapsed)
                self.circuit_breaker[model] = 0  # Reset
                
                return {
                    "result": result,
                    "model_used": model.value,
                    "latency_ms": int(elapsed),
                    "fallback_occurred": attempt > 0,
                    "success": True
                }
                
            except Exception as e:
                logger.error(f"Erro no {model.value}: {e}")
                self.circuit_breaker[model] += 1
                self.metrics.record_error(model.value, str(e))
                
                if attempt < max_retries - 1:
                    # Fallback
                    model = Model.DEEPSEEK if model == Model.GEMINI else Model.GEMINI
                    await asyncio.sleep(2 ** attempt)
                else:
                    # Falhou tudo
                    return {
                        "result": None,
                        "model_used": None,
                        "latency_ms": int((asyncio.get_event_loop().time() - start_time) * 1000),
                        "fallback_occurred": attempt > 0,
                        "success": False,
                        "error": str(e)
                    }

    def _choose_model_smart(self, query: str) -> Model:
        """
        Lógica inteligente de roteamento
        
        - Classificação simples → Gemini (mais barato)
        - Código → DeepSeek (melhor em programação)
        - Análise → DeepSeek (mais preciso)
        - Chat geral → Gemini (suficiente)
        """
        
        # Heurísticas simples
        query_lower = query.lower()
        
        if any(keyword in query_lower for keyword in ['code', 'function', 'bug', 'debug']):
            return Model.DEEPSEEK  # Bom em código
        
        if any(keyword in query_lower for keyword in ['what', 'why', 'how', 'explain']):
            return Model.GEMINI  # Chat geral é OK
        
        # Default: Gemini (mais barato)
        return Model.GEMINI
```

---

## ✅ Fase 5: Validação & Monitoramento

### Teste Rápido de Portabilidade

```python
# tests/test_prompt_portability.py

import pytest
import asyncio
from deepseek_adapter import DeepSeekAdapter
from gemini_adapter import GeminiAdapter
from prompts import CATALOG

async def evaluate_response(result: str, expected: str) -> float:
    """
    Avaliar qualidade da resposta
    
    Retorna score 0.0-1.0 onde:
    - 1.0 = Excelente match
    - 0.5 = Parcialmente correto
    - 0.0 = Completamente errado
    """
    
    # Comparação semântica (usando embeddings ou string similarity)
    from difflib import SequenceMatcher
    ratio = SequenceMatcher(None, result.lower(), expected.lower()).ratio()
    return ratio

@pytest.mark.parametrize("prompt_name,prompt_text,expected_output", [
    ("detect_intent_simple", "Como funciona IA?", "chat"),
    ("detect_intent_code", "Como debugo async/await?", "code"),
    ("detect_intent_analysis", "Qual é a população de São Paulo?", "analysis"),
    # ... mais testes
])
async def test_prompt_portability(prompt_name, prompt_text, expected_output):
    """Testa cada prompt em ambos modelos"""
    
    ds = DeepSeekAdapter(api_key="...")
    gm = GeminiAdapter(api_key="...")
    
    # Testar DeepSeek
    ds_result = await ds.classify({"cleaned": prompt_text})
    ds_score = evaluate_response(ds_result.get("intent"), expected_output)
    
    # Testar Gemini
    gm_result = await gm.classify({"cleaned": prompt_text})
    gm_score = evaluate_response(gm_result.get("intent"), expected_output)
    
    # Relatório
    print(f"\n{prompt_name}")
    print(f"  DeepSeek: {ds_score:.2%}")
    print(f"  Gemini:   {gm_score:.2%}")
    print(f"  Delta:    {abs(ds_score - gm_score):.2%}")
    
    # Alerta se diferença > 10%
    assert abs(ds_score - gm_score) < 0.10, \
        f"Diferença > 10% em {prompt_name}: DS={ds_score:.2%}, GM={gm_score:.2%}"

@pytest.mark.asyncio
async def test_latency():
    """Verificar se latência está dentro dos limites"""
    
    # Setup
    gm = GeminiAdapter(api_key="...")
    queries = ["Como funciona?"] * 10
    
    # Medir
    latencies = []
    for q in queries:
        start = time.time()
        await gm.process(q)
        latencies.append((time.time() - start) * 1000)
    
    p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    
    print(f"Latência p95: {p95:.0f}ms")
    assert p95 < 300, f"Latência p95={p95:.0f}ms > 300ms"
```

### Critérios de Aceitação

```
✅ SUCESSO = Todos Estes:

1. Acuracidade Gemini ≥ 90%
   (vs 95% DeepSeek - margem aceitável)

2. Latência < 200ms adicional
   (Gemini é rápido, não deve piorar)

3. Taxa de erro < 1%
   (Timeouts, mal-formado, etc)

4. Custo ≤ orçamento
   (Não ultrapassar limite acordado)

5. Satisfação NPS ≥ baseline
   (Usuários não reclamam de qualidade)
```

---

## 📅 Timeline Ajustada & Realista

### Semana 1: Validação Rápida (MVP)

#### Segunda: Extração de Prompts
- **Atividade:** Identificar e documentar 15-20 prompts críticos do DeepSeek
- **Output:** Pasta `prompts/` com template `.md` para cada um
- **Responsável:** [Owner]
- **Duração:** 4-6 horas

#### Terça-Quarta: Teste Paralelo
- **Atividade:** Executar cada prompt em DeepSeek e Gemini
- **Medir:** Acuracidade, latência, custo
- **Output:** `test_results.csv` com comparativo
- **Responsável:** [Owner]
- **Duração:** 8 horas

#### Quinta: Análise de Gap
- **Atividade:** Identificar prompts que falharam no Gemini
- **Priorizar:** Por impacto (quantos usuários?)
- **Output:** `gaps.md` com problemas identificados
- **Responsável:** [Owner]
- **Duração:** 2-3 horas

#### Sexta: Decisão Go/No-Go
- **Pergunta:** Gemini consegue fazer 90%+ do trabalho?
- **Go:** ✅ Próxima fase (Semana 2)
- **No-Go:** ❌ Reverter ou ajustar escopo
- **Responsável:** [Stakeholder]

### Semana 2: Implementação

#### Segunda-Terça: Interface Comum
- **Atividade:** Extrair `QueryProcessor` abstrato
- **Implementar:** Adaptadores DeepSeek e Gemini
- **Output:** Classes Python com testes unitários
- **Duração:** 8 horas

#### Quarta-Quinta: Orquestrador
- **Atividade:** Router com fallback, métricas, logging
- **Implementar:** Circuit breaker, retry logic
- **Output:** Módulo `orchestrator.py` com testes
- **Duração:** 8 horas

#### Sexta: Testes Unitários
- **Cobertura:** >80%
- **Mock:** APIs externas (não chamar Gemini/DeepSeek realmente)
- **Output:** `coverage_report.html`
- **Duração:** 4 horas

### Semana 3: Validação em Staging

#### Segunda-Quarta: A/B Test
- **Deploy:** em staging (não produção)
- **Rotear:** 50% para Gemini, 50% para DeepSeek
- **Coletar:** Métricas de ambos
- **Output:** Dashboard Grafana com dados
- **Duração:** 24 horas (rodar em background)

#### Quinta: Revisão
- **Análise:** Resultados do A/B test
- **Ajustes:** Se necessário, refinar prompts
- **Output:** Report com recomendação
- **Duração:** 2 horas

#### Sexta: Go Live (Produção)
- **Rollout Gradual:**
  - 10% tráfego → Gemini (4 horas observação)
  - 50% tráfego → Gemini (24 horas)
  - 100% tráfego → Gemini (ou manter fallback)
- **Monitoring:** 24/7 por 1 semana
- **Rollback:** Plano B se algo der errado

---

## 📈 Métricas & Dashboard Essencial

### Métricas CRÍTICAS (Monitorar Sempre)

| Métrica | Alvo | Alerta | Ferramenta | Frequência |
|---------|------|--------|-----------|-----------|
| **Taxa de Sucesso** | ≥90% | <90% | Prometheus | 1min |
| **Latência p95** | <200ms | >300ms | Datadog | 1min |
| **Custo/Mês** | <$200 | >$300 | Planilha + API | 1h |
| **Taxa de Erro** | <1% | >2% | Prometheus | 1min |
| **Fallback Rate** | <5% | >10% | Logs (ELK) | 15min |
| **Queue Size** | <100 | >500 | Prometheus | 5min |

### Dashboard Grafana Template

```
┌─ JARVAS GUARDER MIGRATION ──────────────────┐
│                                             │
│  Status Geral: 🟢 HEALTHY                  │
│  Última atualização: Agora                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                             │
│  Taxa de Sucesso           Latência p95     │
│  ┌─────────────────────┐   ┌──────────────┐│
│  │ DeepSeek: 94% ✅    │   │ DS: 150ms    ││
│  │ Gemini:   89% ⚠️    │   │ GM: 175ms ✅ ││
│  │ Fallback: 2% ✅     │   │ Alvo: <200ms ││
│  └─────────────────────┘   └──────────────┘│
│                                             │
│  Custo Diário              Fila & Taxa Erro│
│  ┌─────────────────────┐   ┌──────────────┐│
│  │ DeepSeek: $13.50    │   │ Queue: 23 ✅ ││
│  │ Gemini:   $8.20     │   │ Taxa erro: 0.3%
│  │ Total:    $21.70    │   │ (Target: <1%)││
│  │ Budget:   $30/dia   │   └──────────────┘│
│  └─────────────────────┘                   │
│                                             │
│  Alertas Ativos: 1 ⚠️                      │
│  └─ Gemini taxa caiu para 87%             │
│                                             │
└─────────────────────────────────────────────┘
```

### Alertas Automáticos

```python
# alerts/rules.yaml

groups:
  - name: guarda_migration
    rules:
      # Taxa de sucesso baixa
      - alert: GeminiTaxaBaixa
        expr: gemini_success_rate < 0.85
        for: 5m
        annotations:
          summary: "Gemini taxa abaixo de 85%"
          action: "Ativar fallback 100% DeepSeek"

      # Latência alta
      - alert: LatenciaAlta
        expr: latency_p95_ms > 300
        for: 10m
        annotations:
          summary: "Latência p95 acima de 300ms"
          action: "Investigar queue, rate limit, modelo"

      # Custo alto
      - alert: CustoAlto
        expr: daily_cost_usd > 30
        for: 1h
        annotations:
          summary: "Custo diário acima de $30"
          action: "Revisar volume ou otimizar prompts"
```

---

## ❓ Questões Críticas a Responder

### 1. Qual é o Objetivo Real?

#### 💰 Se é **ECONOMIZAR**
```
Estratégia:
  • Usar Gemini como fallback (mais barato)
  • Priorizar: classificação simples → Gemini
  • Fallback para DeepSeek se Gemini falhar
  • Cachear respostas (Redis)
  • Batch processing para grandes volumes

Impacto:
  • -30% de custo (se ~5% taxa de erro aceita)
  • +$150/mês economizado
```

#### ⚡ Se é **REDUNDÂNCIA**
```
Estratégia:
  • Ambos em produção simultaneamente
  • Health check contínuo (healthcheck endpoints)
  • Fallback automático em timeout
  • Circuit breaker por modelo
  • Monitoramento 24/7

Impacto:
  • 99.99% uptime (vs 99% com um só)
  • +$1.200/mês adicional
```

#### 🎯 Se é **FLEXIBILIDADE**
```
Estratégia:
  • Expor ambos os modelos ao usuário
  • Deixar escolher: /g (Gemini) ou /d (DeepSeek)
  • A/B testing para otimizar por caso
  • Documentar trade-offs (custo vs qualidade)

Impacto:
  • Melhor UX (usuário no controle)
  • Facilita experimentação
```

**⚠️ DECISÃO NECESSÁRIA:** Qual é o objetivo? Esta resposta muda toda a estratégia.

### 2. Qual é o Escopo Realista?

#### 🎯 **MVP (2 semanas)**
```
O mínimo para validar a ideia:
  • Adaptador Gemini para 5 prompts críticos
  • Fallback automático
  • Métricas básicas
  • A/B test em staging
  • Sem produção ainda

Risco: Baixo
Tempo: 2 semanas
Custo: $0 (testes)
```

#### 🚀 **COMPLETO (6 semanas)**
```
Migração total:
  • Todos os prompts do DeepSeek
  • Load balancing inteligente
  • Caching distribuído
  • Dashboard Grafana completo
  • Documentação + runbooks
  • Produção com rollout gradual

Risco: Médio
Tempo: 6 semanas
Custo: +$200-500 (API calls)
```

### 3. Qual é o Orçamento?

```
Cenário A: DeepSeek (atual)
  • 10k req/dia × 30 dias = 300k req/mês
  • Custo: ~$1.500/mês
  • Uptime: 99% SLA

Cenário B: Gemini (fallback) ← RECOMENDADO
  • 90% via Gemini: ~$1.200/mês
  • 10% DeepSeek: ~$150/mês
  • Total: ~$1.350/mês
  • Economia: $150/mês (10%)
  • Uptime: 99.5%

Cenário C: Ambos (redundância)
  • 50% cada: ~$1.500 + 1.200 = $2.700/mês
  • Premium: +$1.200/mês
  • Uptime: 99.99%
  • Apenas se uptime crítico

RECOMENDAÇÃO: Cenário B (Gemini como fallback)
```

---

## 📝 TL;DR & Próximos Passos

### Resume Executivo

**O que mudou do plano original:**

1. ✅ **Foco:** Prompts (não código/arquitetura complexa)
2. ✅ **Validação:** Acuracidade realista (90%, não 95%)
3. ✅ **Timeline:** Semana 1 = decisão rápida (Go/No-Go)
4. ✅ **Custo:** Análise de impacto financeiro incluída
5. ✅ **Risk:** Fallback automático (não "tudo ou nada")

### Próximos Passos (Próximos 3 dias)

#### Hoje: Decisão Estratégica
- [ ] Confirmar objetivo (economizar? redundância? flexibilidade?)
- [ ] Validar orçamento máximo
- [ ] Designar owner (quem lidera?)
- [ ] Agendar kickoff com time

#### Amanhã: Setup Inicial
- [ ] Criar repo: `github.com/org/guarda-migration`
- [ ] Setup CI/CD pipeline (GitHub Actions)
- [ ] Provisionar Gemini API key + quota aumentada
- [ ] Criar canal Slack #guarda-migration

#### Em 2 dias: Começar Semana 1
- [ ] Extrair prompts do DeepSeek (issue #1)
- [ ] Configurar teste paralelo (script)
- [ ] Agendar reunião Go/No-Go para sexta
- [ ] Criar dashboard Grafana básico

### Checklist Final

- [x] Plano estruturado em 5 fases
- [x] Feedback crítico endereçado
- [x] Timeline realista (3 semanas MVP)
- [x] Métricas mensuráveis
- [x] Análise de risco/custo
- [ ] ⬅️ Decisão sobre objetivo
- [ ] ⬅️ Aprovação para começar
- [ ] ⬅️ Designação de owner

### Êxito = Estes 3 Critérios

| Critério | Descrição | Métrica |
|----------|-----------|---------|
| **🎯 Funcional** | Gemini consegue fazer 90%+ do trabalho de forma confiável | Acuracidade ≥ 90% |
| **💰 Viável** | Custo ≤ orçamento. ROI positivo em < 6 meses | Custo < $1.500/mês |
| **🚀 Operacional** | Fallback automático. Zero manual intervention | Fallback rate < 5% |

---

## 📚 Referências & Links

- [Gemini API Docs](https://ai.google.dev/docs)
- [DeepSeek API Docs](https://platform.deepseek.com/docs)
- [Prometheus Alerting](https://prometheus.io/docs/alerting/latest/overview/)
- [Grafana Dashboard](https://grafana.com/docs/grafana/latest/dashboards/)

---

**Documento criado em:** 2026-04-14  
**Versão:** 1.0  
**Status:** ✅ Pronto para Implementação  
**Próxima revisão:** Após decisão estratégica