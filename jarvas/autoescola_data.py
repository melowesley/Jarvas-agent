"""
Curriculum completo da Autoescola Jarvas.
Cada aula tem cenário, passos numerados, outputs esperados e validações.
"""

LESSONS = [
    {
        "id": 1,
        "name": "Primeira Marcha",
        "scenario": """Você está começando a "dirigir" o Jarvas. Ninguém quer um carro que não sabe como ligar.
Vamos explorar os comandos básicos e ver como o Jarvas roteia automaticamente sua pergunta para o modelo certo.""",
        "diagram": """Você digita → Jarvas roteia → IA responde
             ↓
        (Hermes, Gemini, etc)""",
        "steps": [
            {
                "instruction": "Digite /help para explorar todos os comandos",
                "expectedRegex": r"^/help$",
                "expectedOutput": "contém lista de comandos com cores",
                "hint": "Comece com /help",
                "checkpoint": "Você consegue listar todos os comandos disponíveis?",
                "warning": "Não digite /help web — esse comando não existe"
            },
            {
                "instruction": "Faça uma pergunta simples (ex: 'Qual é a capital da França?')",
                "expectedRegex": r"^[^/]",
                "expectedOutput": "contém resposta coerente sobre França ou Paris",
                "hint": "Digite uma pergunta que comece com uma letra, não um /",
                "checkpoint": "O Jarvas respondeu corretamente?",
                "warning": "Evite perguntas muito complexas na primeira marcha"
            },
            {
                "instruction": "Observe qual modelo foi usado (procure por (Hermes), (Gemini), etc)",
                "expectedRegex": r".*",
                "expectedOutput": "mostra qual modelo foi selecionado",
                "hint": "Veja o nome do modelo entre parênteses",
                "checkpoint": "Você consegue identificar qual IA respondeu?",
                "warning": "O roteamento automático escolhe baseado no tipo de pergunta"
            }
        ]
    },
    {
        "id": 2,
        "name": "Trocando Marchas",
        "scenario": """Agora você quer mais controle. Não quer depender do roteamento automático.
Os "guardas" deixam você escolher diretamente qual especialista quer ouvir: Gemini (web search) ou DeepSeek (análise lógica).""",
        "diagram": """        você digita
       /            \\
      /g (Gemini)   /d (DeepSeek)
      ↓              ↓
   web search    análise lógica""",
        "steps": [
            {
                "instruction": "Digite /g qual é o resultado da eleição nos EUA 2024?",
                "expectedRegex": r"^/g .+",
                "expectedOutput": "resposta de Gemini com dados sobre eleições",
                "hint": "Formato: /g [sua pergunta]",
                "checkpoint": "Gemini respondeu com informações recentes?",
                "warning": "/g busca automáticamente na web se necessário"
            },
            {
                "instruction": "Digite /d qual é a diferença entre LLMs e AGI?",
                "expectedRegex": r"^/d .+",
                "expectedOutput": "análise técnica de DeepSeek sobre LLMs vs AGI",
                "hint": "Formato: /d [sua pergunta]",
                "checkpoint": "DeepSeek forneceu uma análise técnica profunda?",
                "warning": "DeepSeek é especializado em análise lógica, não web search"
            },
            {
                "instruction": "Compare os estilos: qual resposta foi mais teórica? Qual foi mais prática?",
                "expectedRegex": r".*",
                "expectedOutput": "você reconheceu estilos diferentes entre as duas",
                "hint": "Gemini = prático/web; DeepSeek = teórico/lógico",
                "checkpoint": "Você vê a diferença entre os dois especialistas?",
                "warning": None
            },
            {
                "instruction": "Digite /g web \"tendências AI 2025\" para busca web explícita",
                "expectedRegex": r"^/g web .+",
                "expectedOutput": "links e resumos sobre tendências de AI em 2025",
                "hint": "Formato: /g web [sua busca]",
                "checkpoint": "Gemini retornou links e resumos confiáveis?",
                "warning": "Use /g web para buscas que precisam de informações atualizadas"
            }
        ]
    },
    {
        "id": 3,
        "name": "Cruzamento Decisivo",
        "scenario": """Você tem uma questão polêmica ou complexa. Quer ouvir dois lados: Gemini e DeepSeek debatendo até chegar em um consenso.
Este é o "cruzamento decisivo" — o ponto onde você toma a melhor decisão porque tem múltiplas perspectivas.""",
        "diagram": """/debate questão
  ↓
Gemini propõe
  ↓
DeepSeek critica
  ↓
Síntese final
  ↓
/hmem add para salvar""",
        "steps": [
            {
                "instruction": "Digite /debate SQL vs NoSQL - qual escolher em 2025?",
                "expectedRegex": r"^/debate .+",
                "expectedOutput": "debate formatado com múltiplas rodadas",
                "hint": "Formato: /debate [questão polêmica]",
                "checkpoint": "O debate começou e você vê argumentos dos dois lados?",
                "warning": "Debater leva mais tempo que uma resposta normal"
            },
            {
                "instruction": "Leia as 3 rodadas: proposta (Gemini), crítica (DeepSeek), síntese",
                "expectedRegex": r".*",
                "expectedOutput": "você reconheceu as 3 fases do debate",
                "hint": "Rodada 1 = Gemini; Rodada 2 = DeepSeek; Rodada 3 = síntese",
                "checkpoint": "A síntese final foi justa com os dois argumentos?",
                "warning": None
            },
            {
                "instruction": "Agora salve a conclusão: /hmem add SQL vs NoSQL 2025 - [sua síntese]",
                "expectedRegex": r"^/hmem add .+",
                "expectedOutput": "confirmação 'Memória adicionada'",
                "hint": "Sinterize a conclusão em 1-2 frases",
                "checkpoint": "A memória foi salva com sucesso?",
                "warning": "Não salve o debate inteiro — sinterize em conclusão"
            },
            {
                "instruction": "Verifique: /hmem search SQL (busca a memória que salvou)",
                "expectedRegex": r"^/hmem search .+",
                "expectedOutput": "resultado da busca mostrando sua memória salvada",
                "hint": "Formato: /hmem search [palavra-chave]",
                "checkpoint": "Você recuperou a memória que salvou?",
                "warning": "/hmem search usa palavra-chave, não busca exata"
            }
        ]
    },
    {
        "id": 4,
        "name": "Estacionando Memorias",
        "scenario": """Você não quer esquecer insights importantes. O MemPalace é sua "biblioteca pessoal" — salve, busque, organize e até veja conexões entre ideias.
"Estacionando" significa que você vai guardar seus aprendizados para consulta futura.""",
        "diagram": """/hmem add → /hmem search → /hmem graph
   ↓           ↓              ↓
Salva      Busca          Conexões
            (3x)""",
        "steps": [
            {
                "instruction": "Salve 3 fatos sobre Python: /hmem add Python - tipos dinâmicos e duck typing",
                "expectedRegex": r"^/hmem add .+",
                "expectedOutput": "confirmação 'Memória adicionada'",
                "hint": "Salve 3 memórias diferentes sobre Python",
                "checkpoint": "Você salvou pelo menos uma memória sobre Python?",
                "warning": "Não salve frases muito longas — sinterize"
            },
            {
                "instruction": "Salve mais duas: /hmem add Python - list comprehensions e /hmem add Python - decorators",
                "expectedRegex": r"^/hmem add .+",
                "expectedOutput": "confirmação de mais 2 memórias adicionadas",
                "hint": "Adicione as duas memórias restantes",
                "checkpoint": "Você agora tem 3+ memórias sobre Python?",
                "warning": None
            },
            {
                "instruction": "Busque todas: /hmem search Python (mostra 3+ resultados)",
                "expectedRegex": r"^/hmem search .+",
                "expectedOutput": "lista com 3+ itens sobre Python",
                "hint": "Formato: /hmem search [palavra-chave]",
                "checkpoint": "Você consegue recuperar todas as 3 memórias?",
                "warning": "A busca mostra um resumo de cada memória"
            },
            {
                "instruction": "Veja conexões: /hmem graph (mostra grafo de relacionamentos)",
                "expectedRegex": r"^/hmem graph",
                "expectedOutput": "grafo visual mostrando conexões entre conceitos",
                "hint": "Sem argumentos: /hmem graph",
                "checkpoint": "Você consegue ver conexões entre suas ideias?",
                "warning": "O grafo mostra como seus conceitos se relacionam"
            },
            {
                "instruction": "Delete uma memória: /hmem del [ID-da-memória]",
                "expectedRegex": r"^/hmem del .+",
                "expectedOutput": "confirmação 'Memória deletada'",
                "hint": "Copie um ID da busca anterior",
                "checkpoint": "Você conseguiu deletar uma memória?",
                "warning": "Deletar é permanente — cuidado!"
            },
            {
                "instruction": "Verifique: /hmem search Python novamente (agora mostra 2)",
                "expectedRegex": r"^/hmem search .+",
                "expectedOutput": "lista agora com 2 itens (1 foi deletado)",
                "hint": "A busca deve retornar menos resultados",
                "checkpoint": "A contagem diminuiu após o delete?",
                "warning": None
            }
        ]
    },
    {
        "id": 5,
        "name": "Piloto Automático",
        "scenario": """Você quer delegar uma tarefa complexa a um agente especialista que trabalha de forma autônoma.
As "sessões gerenciadas" criam um "co-piloto" que pode rodar código, editar arquivos, fazer buscas — tudo sem sua intervenção.""",
        "diagram": """/session new
    ↓
/session send "tarefa 1"
    ↓ (agente trabalha)
/session history
    ↓
/session send "tarefa 2"
    ↓ (agente trabalha)""",
        "steps": [
            {
                "instruction": "Crie nova sessão: /session new meu-assistente",
                "expectedRegex": r"^/session new .+",
                "expectedOutput": "ID da sessão criada (ex: session-abc123)",
                "hint": "Formato: /session new [nome]",
                "checkpoint": "Uma sessão foi criada com um ID único?",
                "warning": "/session new cria isolamento para seu agente"
            },
            {
                "instruction": "Envie comando: /session send \"Resuma em 3 pontos o que é Jarvas\"",
                "expectedRegex": r"^/session send .+",
                "expectedOutput": "confirmação 'Mensagem enviada para agente'",
                "hint": "Use aspas para incluir espaços",
                "checkpoint": "Sua mensagem foi entregue ao agente?",
                "warning": "O agente trabalha em background"
            },
            {
                "instruction": "Aguarde e verifique: /session history (vê o progresso/saída)",
                "expectedRegex": r"^/session history",
                "expectedOutput": "histórico com output do agente",
                "hint": "Sem argumentos: /session history",
                "checkpoint": "O agente completou a tarefa?",
                "warning": "Pode levar alguns segundos — agente está processando"
            },
            {
                "instruction": "Envie mais um comando: /session send \"Crie um arquivo TODO.md com 5 tarefas\"",
                "expectedRegex": r"^/session send .+",
                "expectedOutput": "confirmação de envio",
                "hint": "Formato: /session send [tarefa]",
                "checkpoint": "Segunda tarefa foi enviada?",
                "warning": None
            },
            {
                "instruction": "Verifique novamente: /session history (mostra ambas respostas)",
                "expectedRegex": r"^/session history",
                "expectedOutput": "histórico com 2+ resposta do agente",
                "hint": "O histórico deve crescer",
                "checkpoint": "Você vê ambas as respostas do agente?",
                "warning": "O histórico é acumulativo"
            }
        ]
    },
    {
        "id": 6,
        "name": "Rally Completo",
        "scenario": """Você é um analista que precisa entender um tópico complexo. Vai usar TUDO o que aprendeu:
pesquisa com Gemini, debate com DeepSeek, salvamento em MemPalace e delegação a agentes.
Isso é o "Rally" — o teste final de "dirigir" o Jarvas combinando todas as marchas.""",
        "diagram": """/g web (pesquisa)
    ↓
/debate (análise)
    ↓
/hmem add (memória)
    ↓
/session new + send (delegação)
    ↓
/hmem add (referência)""",
        "steps": [
            {
                "instruction": "Pesquise com Gemini: /g web \"Python 3.13 release features\"",
                "expectedRegex": r"^/g web .+",
                "expectedOutput": "artigos/notícias sobre Python 3.13",
                "hint": "Use aspas para multi-palavra",
                "checkpoint": "Você coletou dados atualizados sobre Python 3.13?",
                "warning": "/g web acessa internet para informações frescas"
            },
            {
                "instruction": "Inicie debate: /debate Python 3.13 - impacto positivo vs riscos",
                "expectedRegex": r"^/debate .+",
                "expectedOutput": "debate estruturado com múltiplas rodadas",
                "hint": "Formato: /debate [questão]",
                "checkpoint": "Você viu argumentos dos dois lados?",
                "warning": "Debates lançam perspectivas conflitantes"
            },
            {
                "instruction": "Salve conclusão: /hmem add Python 3.13 - vantagens para DS e desafios",
                "expectedRegex": r"^/hmem add .+",
                "expectedOutput": "confirmação 'Memória adicionada'",
                "hint": "Sinterize a conclusão do debate",
                "checkpoint": "Sua síntese foi salva?",
                "warning": None
            },
            {
                "instruction": "Crie sessão de análise: /session new data-science-analysis",
                "expectedRegex": r"^/session new .+",
                "expectedOutput": "ID da sessão criada",
                "hint": "Formato: /session new [nome]",
                "checkpoint": "Sessão de análise criada?",
                "warning": None
            },
            {
                "instruction": "Delegue relatório: /session send \"Analise Python 3.13 e gere relatório markdown com: benefícios, riscos, recomendações\"",
                "expectedRegex": r"^/session send .+",
                "expectedOutput": "confirmação de envio",
                "hint": "Seja específico com o que quer",
                "checkpoint": "Tarefa delegada?",
                "warning": "Tarefas complexas levam mais tempo"
            },
            {
                "instruction": "Verifique relatório: /session history",
                "expectedRegex": r"^/session history",
                "expectedOutput": "relatório markdown completo",
                "hint": "Sem argumentos: /session history",
                "checkpoint": "O relatório foi gerado com todas as seções?",
                "warning": "O agente pode levar tempo para processar"
            },
            {
                "instruction": "Salve referência final: /hmem add data-science-report - análise de Python 3.13",
                "expectedRegex": r"^/hmem add .+",
                "expectedOutput": "confirmação 'Memória adicionada'",
                "hint": "Inclua um resumo ou link",
                "checkpoint": "Referência salva?",
                "warning": None
            },
            {
                "instruction": "Parabéns! Você completou o Rally. Use /hmem graph para ver todas suas aprendizagens conectadas!",
                "expectedRegex": r"^/hmem graph",
                "expectedOutput": "grafo mostrando todas suas memorias e conexões",
                "hint": "Veja o grafo completo de aprendizado",
                "checkpoint": "Você conseguiu usar TODOS os comandos em um fluxo?",
                "warning": "Este é o teste final — você é agora um mestre do Jarvas!"
            }
        ]
    }
]


# VALIDADORES DE PASSO (funções que checam se um passo foi completo)
def validate_step(lesson_id, step_id, user_command, response):
    """
    Valida se um passo foi completado corretamente.

    Args:
        lesson_id (int): ID da aula (1-6)
        step_id (int): ID do passo dentro da aula
        user_command (str): Comando digitado pelo usuário
        response (str): Resposta da API

    Returns:
        dict: {"valid": bool, "hint": str, "message": str}
    """
    if lesson_id < 1 or lesson_id > len(LESSONS):
        return {"valid": False, "message": "Aula inválida"}

    lesson = LESSONS[lesson_id - 1]
    if step_id < 0 or step_id >= len(lesson["steps"]):
        return {"valid": False, "message": "Passo inválido"}

    step = lesson["steps"][step_id]

    # Validar regex
    import re
    if not re.match(step["expectedRegex"], user_command, re.IGNORECASE):
        return {
            "valid": False,
            "hint": step.get("hint", "Tente novamente"),
            "message": f"Comando não corresponde ao esperado"
        }

    # Validar output (simples check por substring)
    if not response or step["expectedOutput"].lower() not in response.lower():
        return {
            "valid": False,
            "hint": step.get("hint", "Tente novamente"),
            "message": f"Output não contém: {step['expectedOutput']}"
        }

    return {
        "valid": True,
        "message": "Passo completo! 🎉",
        "nextStep": step_id + 1 if step_id + 1 < len(lesson["steps"]) else None
    }
