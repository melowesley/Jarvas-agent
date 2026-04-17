# Proximos Passos - Jarvas v0.5.0 -> AgendaVet

**Data:** 17 de abril de 2026  
**Objetivo:** sair de uma base estruturalmente valida para uma release operacionalmente limpa

---

## 1. Estado atual resumido

- versao do pacote confirmada em `0.5.0`
- branch atual: `claude/jarvas-multi-agent-ldGTT`
- `HEAD` esta `3` commits a frente de `origin/main`
- worktree local tem pendencias operacionais
- existe `69` diretorios `__pycache__`
- existe `.git/.MERGE_MSG.swp`
- existe `hermes-agent/.git/index.lock`
- `26` arquivos de teste foram encontrados, mas a suite ainda nao foi executada nesta rodada

---

## 2. Acoes imediatas

### 2.1 Executar a validacao local

```powershell
.\VALIDAR_SINCRONIZACAO.ps1
```

O script gera um relatorio `.txt` na raiz do repositorio com:

- score estrutural
- status de Git
- contagem de `__pycache__`
- versao do pacote
- observacoes operacionais

### 2.2 Limpar pendencias do worktree

```powershell
git status --short --branch
```

Revisar principalmente:

- alteracoes locais em codigo
- residuos de `.pytest_tmp`
- arquivos nao rastreados criados nesta rodada

### 2.3 Resolver residuos de operacao anterior

Somente se voce confirmar que nao ha editor ou processo Git usando esses arquivos:

```powershell
if (Test-Path .git\.MERGE_MSG.swp) {
    Remove-Item .git\.MERGE_MSG.swp -Force
}

if (Test-Path hermes-agent\.git\index.lock) {
    Remove-Item hermes-agent\.git\index.lock -Force
}
```

### 2.4 Limpar cache e temporarios

```powershell
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force
```

Se quiser tratar os temporarios de teste, revise antes:

```powershell
git status --short
```

### 2.5 Executar testes

```powershell
pytest tests/ -v
```

---

## 3. Sequencia recomendada para esta semana

### Dia 1 - Higiene e confirmacao

- executar `.\VALIDAR_SINCRONIZACAO.ps1`
- revisar `git status --short --branch`
- limpar `__pycache__`
- remover residuos como `.MERGE_MSG.swp` e `index.lock` apenas se forem locks residuais

### Dia 2 - Testes e estabilidade

- rodar `pytest tests/ -v`
- anotar falhas
- confirmar se o estado atual da feature branch esta pronto para PR

### Dia 3 - Contexto AgendaVet

- decidir se `autoescola` permanece como legado documentado
- ou abrir uma refatoracao especifica para renomeacao e imports

### Dia 4 - Revisao de merge

- comparar com `origin/main`
- revisar os arquivos alterados nesta feature
- preparar mensagem de release/PR

```powershell
git diff --name-only origin/main...HEAD
git diff origin/main...HEAD
```

### Dia 5 - Fechamento

- criar PR para `main` se a suite passar
- atualizar release notes
- validar readiness para staging

---

## 4. Checklist pre-release

### Codigo e testes

- [ ] `pytest tests/ -v` executado
- [ ] falhas corrigidas ou justificadas
- [ ] worktree limpo antes do commit final

### Git e historico

- [ ] branch atual revisada contra `origin/main`
- [ ] residuos de merge removidos
- [ ] locks residuais removidos
- [ ] nenhum arquivo temporario entrou por engano

### Documentacao

- [ ] analise de sincronizacao atualizada
- [ ] resumo executivo em `v0.5.0`
- [ ] decisao documentada sobre o legado `autoescola`

### AgendaVet

- [ ] confirmar se a nomenclatura atual pode seguir para staging
- [ ] se nao puder, abrir task de refatoracao dedicada

---

## 5. Problemas conhecidos e acao segura

### Git sujo

Sintoma:

- `git status` mostra muitos arquivos modificados ou deletados

Acao segura:

```powershell
git status --short
git diff
```

Revisar antes de apagar ou commitar qualquer coisa.

### Cache Python alto

Sintoma:

- muitos `__pycache__`

Acao segura:

```powershell
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__"
```

Depois limpar conscientemente.

### Residuo de merge

Sintoma:

- arquivo `.git/.MERGE_MSG.swp`

Acao segura:

- confirmar que nao ha Vim, editor ou operacao Git aberta
- remover apenas o arquivo residual

### Lock em repo aninhado

Sintoma:

- `hermes-agent/.git/index.lock`

Acao segura:

- verificar se nao ha processo Git em execucao nesse subrepositorio
- remover apenas se for lock residual

---

## 6. Definicao de pronto para release

A `v0.5.0` fica pronta para seguir para staging quando:

1. o repositorio estiver limpo
2. os testes estiverem executados
3. a feature branch estiver revisada contra `main`
4. a documentacao estiver coerente com o estado real da base
5. a decisao sobre `autoescola` vs. AgendaVet estiver registrada

---

## 7. Fechamento

O projeto ja esta numa fase de consolidacao, nao de descoberta. O foco agora e simples:

- limpar o ambiente local
- validar com testes
- decidir a estrategia de nomenclatura
- preparar a passagem da feature branch para `main`
