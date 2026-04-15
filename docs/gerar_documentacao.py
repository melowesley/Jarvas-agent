"""Gera a documentação completa do Jarvas em PDF."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import ListFlowable, ListItem
import os

OUTPUT = os.path.join(os.path.dirname(__file__), "Jarvas_Documentacao_v0.4.0.pdf")

# ─── Estilos ──────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

DARK_BG   = colors.HexColor("#1a1a2e")
BLUE      = colors.HexColor("#7eb8f7")
LIGHT_BG  = colors.HexColor("#f0f4ff")
CODE_BG   = colors.HexColor("#1e1e2e")
CODE_FG   = colors.HexColor("#a6e3a1")
GRAY      = colors.HexColor("#555555")
DARK_GRAY = colors.HexColor("#333333")
WHITE     = colors.white

title_style = ParagraphStyle(
    "JTitle",
    fontName="Helvetica-Bold",
    fontSize=28,
    textColor=WHITE,
    alignment=TA_CENTER,
    spaceAfter=6,
)
subtitle_style = ParagraphStyle(
    "JSubtitle",
    fontName="Helvetica",
    fontSize=13,
    textColor=BLUE,
    alignment=TA_CENTER,
    spaceAfter=4,
)
version_style = ParagraphStyle(
    "JVersion",
    fontName="Helvetica-Oblique",
    fontSize=10,
    textColor=colors.HexColor("#aaaaaa"),
    alignment=TA_CENTER,
    spaceAfter=20,
)
h1_style = ParagraphStyle(
    "JH1",
    fontName="Helvetica-Bold",
    fontSize=18,
    textColor=DARK_BG,
    spaceBefore=20,
    spaceAfter=8,
    borderPad=4,
)
h2_style = ParagraphStyle(
    "JH2",
    fontName="Helvetica-Bold",
    fontSize=13,
    textColor=colors.HexColor("#1e3a5f"),
    spaceBefore=14,
    spaceAfter=6,
)
h3_style = ParagraphStyle(
    "JH3",
    fontName="Helvetica-Bold",
    fontSize=11,
    textColor=DARK_GRAY,
    spaceBefore=10,
    spaceAfter=4,
)
body_style = ParagraphStyle(
    "JBody",
    fontName="Helvetica",
    fontSize=10,
    textColor=DARK_GRAY,
    leading=16,
    alignment=TA_JUSTIFY,
    spaceAfter=6,
)
bullet_style = ParagraphStyle(
    "JBullet",
    fontName="Helvetica",
    fontSize=10,
    textColor=DARK_GRAY,
    leading=15,
    leftIndent=16,
    spaceAfter=3,
)
code_style = ParagraphStyle(
    "JCode",
    fontName="Courier",
    fontSize=8.5,
    textColor=CODE_FG,
    backColor=CODE_BG,
    leading=13,
    leftIndent=10,
    rightIndent=10,
    spaceBefore=6,
    spaceAfter=6,
    borderPad=6,
)
note_style = ParagraphStyle(
    "JNote",
    fontName="Helvetica-Oblique",
    fontSize=9,
    textColor=colors.HexColor("#1e3a5f"),
    backColor=LIGHT_BG,
    leading=14,
    leftIndent=10,
    rightIndent=10,
    spaceBefore=4,
    spaceAfter=4,
    borderPad=6,
)

def H(text, level=1):
    s = {1: h1_style, 2: h2_style, 3: h3_style}[level]
    return Paragraph(text, s)

def P(text):
    return Paragraph(text, body_style)

def B(text):
    return Paragraph(f"&bull; {text}", bullet_style)

def Code(text):
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, code_style)

def Note(text):
    return Paragraph(f"<b>Nota:</b> {text}", note_style)

def HR():
    return HRFlowable(width="100%", thickness=1, color=colors.HexColor("#ddddee"), spaceAfter=8)

def table_style_base():
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, -1), LIGHT_BG),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ccccdd")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])


# ─── Construir documento ──────────────────────────────────────────────────────

def build_pdf():
    W, H_page = A4
    margin = 2 * cm

    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=A4,
        rightMargin=margin,
        leftMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
        title="Jarvas — Documentação Oficial v0.4.0",
        author="Wesley Melo de Oliveira",
        subject="Assistente de IA Distribuído",
    )

    story = []

    # ── Capa ──────────────────────────────────────────────────────────────────
    cover_table = Table(
        [[
            Paragraph("JARVAS", title_style),
        ]],
        colWidths=[W - 2 * margin],
    )
    cover_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK_BG),
        ("TOPPADDING", (0, 0), (-1, -1), 40),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
        ("LEFTPADDING", (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
    ]))

    story.append(Spacer(1, 2 * cm))
    story.append(cover_table)
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Assistente de IA Distribuído", subtitle_style))
    story.append(Paragraph("Documentação Oficial — Versão 0.4.0", version_style))
    story.append(Paragraph("Wesley Melo de Oliveira &bull; 2026", version_style))
    story.append(Spacer(1, 1 * cm))

    # Resumo na capa
    intro_box = Table(
        [[P(
            "Jarvas é um sistema de IA colaborativo que combina múltiplos modelos de linguagem "
            "em uma única interface inteligente. Ele detecta automaticamente a intenção de cada "
            "mensagem, aciona os modelos corretos, edita arquivos de código, processa documentos "
            "e aprende com cada interação — armazenando o conhecimento no MemPalace e no Supabase."
        )]],
        colWidths=[W - 2 * margin],
    )
    intro_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("BOX", (0, 0), (-1, -1), 1.5, BLUE),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))
    story.append(intro_box)
    story.append(PageBreak())

    # ── 1. O que é o Jarvas ───────────────────────────────────────────────────
    story.append(H("1. O que é o Jarvas"))
    story.append(HR())
    story.append(P(
        "O Jarvas é um assistente de IA distribuído criado para ser simultaneamente um "
        "<b>professor de código</b> e um <b>aluno que aprende com você</b>. Ao contrário de um "
        "chatbot único, o Jarvas orquestra múltiplos modelos de linguagem em paralelo, debate "
        "entre eles e armazena os aprendizados para uso em sessões futuras."
    ))
    story.append(Spacer(1, 0.3 * cm))

    story.append(H("A Metáfora Central", 2))
    meta_data = [
        ["Componente", "Papel", "Tecnologia"],
        ["Jarvas", "Roteador e Mensageiro", "OpenRouter (Hermes)"],
        ["Gemini", "Guarda / Soldado 1", "Google Gemini"],
        ["DeepSeek", "Guarda / Soldado 2", "DeepSeek via OpenRouter"],
        ["MemPalace", "Cerebro — Memória Persistente", "mempalace (local)"],
        ["Supabase", "Arquivo Historico Completo", "Supabase PostgreSQL"],
    ]
    meta_table = Table(meta_data, colWidths=[4 * cm, 6 * cm, 5.5 * cm])
    meta_table.setStyle(table_style_base())
    story.append(meta_table)
    story.append(Spacer(1, 0.5 * cm))

    story.append(H("O que o Jarvas faz por voce", 2))
    for item in [
        "Detecta automaticamente se voce esta falando de codigo, analise ou conversa normal",
        "Consulta Gemini e DeepSeek em paralelo e sintetiza um consenso",
        "Le e edita arquivos do seu projeto diretamente no disco",
        "Processa PDF, Excel, Word, CSV e imagens guiado pelo seu prompt",
        "Extrai texto de imagens via OCR e gera arquivos Excel organizados",
        "Armazena aprendizados no MemPalace ao comando 'armazene'",
        "Guarda todo o historico de conversas, debates e edicoes no Supabase",
        "Oferece interface web com botoes de acao rapida na porta 8080",
    ]:
        story.append(B(item))
    story.append(PageBreak())

    # ── 2. Arquitetura ────────────────────────────────────────────────────────
    story.append(H("2. Arquitetura do Sistema"))
    story.append(HR())

    story.append(H("Fluxo Principal", 2))
    story.append(P(
        "Toda mensagem — seja no terminal ou na interface web — percorre o mesmo caminho:"
    ))
    story.append(Spacer(1, 0.2 * cm))

    flow_data = [
        ["Etapa", "Modulo", "Descricao"],
        ["1", "intent_parser.py", "Classifica a mensagem em um dos 10 tipos de Intent"],
        ["2", "orchestrator.py", "Despacha o Intent para o handler especifico"],
        ["3", "Handler especifico", "Executa a logica (chat, pipeline, debate, edicao, etc.)"],
        ["4", "Supabase / MemPalace", "Persiste resultado conforme o tipo de operacao"],
        ["5", "Terminal ou Web UI", "Exibe resposta formatada ao usuario"],
    ]
    flow_table = Table(flow_data, colWidths=[1.5 * cm, 4.5 * cm, 9.5 * cm])
    flow_table.setStyle(table_style_base())
    story.append(flow_table)
    story.append(Spacer(1, 0.5 * cm))

    story.append(H("Tipos de Intent (o que o Jarvas reconhece)", 2))
    intent_data = [
        ["Intent", "Exemplos de mensagem", "Acao"],
        ["CHAT", "'oi tudo bem?', 'o que e um loop?'", "Resposta direta do Hermes"],
        ["PIPELINE", "'escreva um script python', 'analise esse codigo'", "3 guardas em paralelo + sintese"],
        ["DEBATE", "'debate sobre SQL vs NoSQL'", "Gemini vs DeepSeek, consenso final"],
        ["FILE_READ", "'leia o arquivo main.py'", "Le arquivo do projeto"],
        ["FILE_EDIT", "'edite utils.py para snake_case'", "Edita e salva no disco"],
        ["SET_PROJECT", "'trabalhar em #C:/projetos/ocr'", "Define pasta do projeto ativo"],
        ["STORE_MEMORY", "'armazene as ultimas interacoes'", "Grava insights no MemPalace"],
        ["ATTACH", "'analise relatorio.pdf'", "Extrai e processa o arquivo"],
        ["OCR", "'ocr nota.jpg gere excel'", "OCR da imagem, salva em Excel"],
        ["SEARCH_WEB", "'pesquise sobre pytesseract'", "Busca web via Gemini"],
    ]
    intent_table = Table(intent_data, colWidths=[2.8 * cm, 5.5 * cm, 7.2 * cm])
    intent_table.setStyle(table_style_base())
    story.append(intent_table)
    story.append(Spacer(1, 0.5 * cm))

    story.append(H("Modulos do Projeto", 2))
    mod_data = [
        ["Arquivo", "Responsabilidade"],
        ["intent_parser.py", "Classifica mensagens em Intent tipado"],
        ["orchestrator.py", "Tabela de dispatch: Intent -> Handler"],
        ["context.py", "SessionContext — estado da sessao (projeto, historico)"],
        ["guard_pipeline.py", "Pipeline paralelo: Hermes + Gemini + DeepSeek + sintese"],
        ["file_editor.py", "Le e edita arquivos no disco com bloqueio de seguranca"],
        ["memory_writer.py", "Extrai insights e grava no MemPalace + Supabase"],
        ["file_processor.py", "Processa PDF/Excel/Word/CSV/imagem guiado por prompt"],
        ["hermes_client.py", "Cliente OpenRouter (modelo principal)"],
        ["guard_gemini.py", "Cliente Google Gemini (guarda 1)"],
        ["guard_deepseek.py", "Cliente DeepSeek via OpenRouter (guarda 2)"],
        ["debate.py", "Orquestrador de debate multi-rodada + consenso"],
        ["mempalace_client.py", "Interface com o MemPalace (tool_add_drawer, etc.)"],
        ["supabase_client.py", "Persistencia no Supabase (todas as tabelas)"],
        ["router.py", "Deteccao de tipo de tarefa por palavras-chave"],
        ["cli.py", "REPL interativo do terminal"],
        ["api.py", "FastAPI — endpoints REST + serve web UI na porta 8080"],
        ["static/chat.html", "Interface web com botoes de acao rapida"],
    ]
    mod_table = Table(mod_data, colWidths=[5 * cm, 10.5 * cm])
    mod_table.setStyle(table_style_base())
    story.append(mod_table)
    story.append(PageBreak())

    # ── 3. Instalacao e Configuracao ──────────────────────────────────────────
    story.append(H("3. Instalacao e Configuracao"))
    story.append(HR())

    story.append(H("Requisitos do Sistema", 2))
    for item in [
        "Python 3.11 ou superior",
        "Windows 10/11 (testado) ou Linux/macOS",
        "Tesseract OCR instalado (para funcionalidade de imagens)",
        "Acesso a internet para os modelos de IA",
        "Conta no Supabase com projeto configurado",
    ]:
        story.append(B(item))
    story.append(Spacer(1, 0.3 * cm))

    story.append(H("Instalacao do Jarvas", 2))
    story.append(Code(
        "# 1. Clonar ou baixar o projeto\n"
        "cd C:\\seu\\diretorio\n"
        "git clone https://github.com/melowesley/Jarvas-agent\n"
        "cd Jarvas-agent\n\n"
        "# 2. Instalar dependencias Python\n"
        "pip install -e .\n\n"
        "# 3. Instalar dependencias de processamento de arquivos\n"
        "pip install pymupdf openpyxl python-docx Pillow pytesseract reportlab\n\n"
        "# 4. Instalar Tesseract OCR (Windows)\n"
        "# Baixe em: https://github.com/UB-Mannheim/tesseract/wiki\n"
        "# Adicione ao PATH do sistema apos instalacao"
    ))

    story.append(H("Configuracao do .env", 2))
    story.append(P("Crie um arquivo <b>.env</b> na raiz do projeto com as seguintes chaves:"))
    story.append(Code(
        "# Modelos de IA\n"
        "OPENROUTER_API_KEY=sk-or-v1-...\n"
        "GEMINI_API_KEY=AIza...\n"
        "DEEPSEEK_API_KEY=sk-...\n\n"
        "# Supabase\n"
        "SUPABASE_URL=https://SEU-PROJETO.supabase.co\n"
        "SUPABASE_KEY=eyJhb..."
    ))
    story.append(Note(
        "O arquivo .env NUNCA deve ser enviado ao git. "
        "Ele ja esta no .gitignore por padrao."
    ))
    story.append(Spacer(1, 0.3 * cm))

    story.append(H("Configuracao do Supabase", 2))
    story.append(P("Execute este SQL no SQL Editor do seu projeto Supabase:"))
    story.append(Code(
        "CREATE TABLE conversations (\n"
        "  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,\n"
        "  session_id text, role text, content text,\n"
        "  model text, task_type text,\n"
        "  created_at timestamptz DEFAULT now()\n"
        ");\n\n"
        "CREATE TABLE pipeline_results (\n"
        "  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,\n"
        "  session_id text, user_message text, task_type text,\n"
        "  hermes text, gemini text, deepseek text, sintese text,\n"
        "  created_at timestamptz DEFAULT now()\n"
        ");\n\n"
        "CREATE TABLE debate_logs (\n"
        "  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,\n"
        "  topic text, rounds jsonb, consensus text,\n"
        "  created_at timestamptz DEFAULT now()\n"
        ");\n\n"
        "CREATE TABLE file_edits (\n"
        "  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,\n"
        "  session_id text, file_path text, instruction text,\n"
        "  original_content text, edited_content text, diff text,\n"
        "  created_at timestamptz DEFAULT now()\n"
        ");\n\n"
        "CREATE TABLE attachments (\n"
        "  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,\n"
        "  session_id text, file_name text, file_type text,\n"
        "  extracted_content text, analysis text,\n"
        "  created_at timestamptz DEFAULT now()\n"
        ");\n\n"
        "CREATE TABLE memory_logs (\n"
        "  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,\n"
        "  session_id text, wing text, room text,\n"
        "  content text, drawer_id text,\n"
        "  created_at timestamptz DEFAULT now()\n"
        ");"
    ))
    story.append(PageBreak())

    # ── 4. Como usar — Terminal ───────────────────────────────────────────────
    story.append(H("4. Como Usar — Terminal (REPL)"))
    story.append(HR())

    story.append(H("Iniciando o Jarvas", 2))
    story.append(Code(
        "# Modo interativo (REPL)\n"
        "jarvas\n\n"
        "# Pergunta direta (uma mensagem)\n"
        "jarvas \"qual e a diferenca entre list e tuple em python?\"\n\n"
        "# Verificar versao\n"
        "jarvas --version"
    ))

    story.append(H("Definindo um Projeto de Trabalho", 2))
    story.append(P(
        "Para trabalhar em um projeto especifico, envie o caminho precedido de <b>#</b>. "
        "A partir dai, o Jarvas sabe onde ler e editar arquivos:"
    ))
    story.append(Code(
        "voce > jarvas hoje vamos trabalhar em #C:/projetos/meu-app\n"
        "Jarvas > Projeto definido: C:/projetos/meu-app\n\n"
        "voce > leia o arquivo main.py\n"
        "Jarvas > [exibe o conteudo de C:/projetos/meu-app/main.py]\n\n"
        "voce > edite main.py para usar snake_case em todas as funcoes\n"
        "Jarvas > [edita e salva o arquivo, exibe o diff]"
    ))

    story.append(H("Conversas Tecnicas — Pipeline Automatico", 2))
    story.append(P(
        "Quando o Jarvas detecta que o assunto e tecnico (codigo, analise), "
        "ele automaticamente consulta Hermes, Gemini e DeepSeek em paralelo e "
        "apresenta uma sintese:"
    ))
    story.append(Code(
        "voce > escreva uma funcao python para calcular fibonacci\n"
        "Jarvas > [sintese dos 3 modelos]\n\n"
        "# No Supabase ficam salvas as 3 respostas individuais + sintese"
    ))

    story.append(H("Debates", 2))
    story.append(Code(
        "voce > debate sobre usar SQLite vs PostgreSQL em producao\n"
        "Jarvas >\n"
        "  Debate: SQLite vs PostgreSQL (3 rodadas)\n"
        "  Rodada 1 — Gemini: ...\n"
        "  Rodada 1 — DeepSeek: ...\n"
        "  ...\n"
        "  Consenso: [sintese objetiva em 2-3 paragrafos]"
    ))

    story.append(H("Armazenar no MemPalace", 2))
    story.append(Code(
        "voce > armazene as ultimas interacoes\n"
        "Jarvas > [analisa as ultimas 5 mensagens e o debate]\n"
        "         [grava insights em wing_code/nome-do-projeto]\n"
        "         [confirma: Drawer adicionado com ID xxxxx]"
    ))

    story.append(H("Retomar uma Sessao Anterior", 2))
    story.append(Code(
        "jarvas continuar ontem 15h\n"
        "# Carrega o historico mais proximo de ontem as 15h do Supabase"
    ))

    story.append(H("Slash Commands Manuais", 2))
    cmd_data = [
        ["Comando", "Descricao"],
        ["/g <prompt>", "Chama o Gemini diretamente"],
        ["/g web <busca>", "Gemini com busca na web"],
        ["/d <prompt>", "Chama o DeepSeek diretamente"],
        ["/d web <busca>", "DeepSeek com busca na web"],
        ["/debate <topico>", "Inicia debate Gemini vs DeepSeek"],
        ["/hopen <model-id>", "Forca modelo especifico para a proxima mensagem"],
        ["/hmem status", "Status do MemPalace"],
        ["/hmem search <busca>", "Busca semantica no MemPalace"],
        ["/hmem add <wing> <room> <conteudo>", "Adiciona memoria manualmente"],
        ["/hmem list", "Lista todas as wings"],
        ["/hmem kg <entidade>", "Consulta o knowledge graph"],
        ["/help", "Exibe todos os comandos"],
    ]
    cmd_table = Table(cmd_data, colWidths=[6.5 * cm, 9 * cm])
    cmd_table.setStyle(table_style_base())
    story.append(cmd_table)
    story.append(PageBreak())

    # ── 5. Como usar — Interface Web ─────────────────────────────────────────
    story.append(H("5. Como Usar — Interface Web (Porta 8080)"))
    story.append(HR())

    story.append(H("Iniciando o Servidor Web", 2))
    story.append(Code(
        "# Inicia a API + Web UI na porta 8080\n"
        "jarvas --managed\n\n"
        "# Porta customizada\n"
        "jarvas --managed --port 9000\n\n"
        "# Acesse no browser:\n"
        "http://localhost:8080"
    ))

    story.append(H("Botoes de Acao Rapida", 2))
    story.append(P(
        "A interface web possui botoes que preenchem o campo de texto com "
        "templates prontos — util quando a deteccao automatica nao e suficiente "
        "ou quando voce quer acionar um comando especifico:"
    ))
    btn_data = [
        ["Botao", "Template inserido", "Para que serve"],
        ["Pipeline", "analise o codigo: ", "Forca consulta aos 3 guardas"],
        ["Debate", "debate sobre: ", "Inicia um debate"],
        ["Armazene", "armazene as ultimas interacoes", "Grava no MemPalace"],
        ["Projeto", "#", "Define pasta do projeto (complete o caminho)"],
        ["Ler Arquivo", "leia o arquivo: ", "Le arquivo do projeto"],
        ["Editar", "edite o arquivo: ", "Edita arquivo no disco"],
        ["Anexar", "abre seletor de arquivo", "Insere caminho no campo"],
        ["OCR->XLS", "ocr: ", "OCR de imagem para Excel"],
        ["Web Search", "pesquise: ", "Busca web via Gemini"],
    ]
    btn_table = Table(btn_data, colWidths=[2.8 * cm, 4.5 * cm, 8.2 * cm])
    btn_table.setStyle(table_style_base())
    story.append(btn_table)
    story.append(Spacer(1, 0.4 * cm))

    story.append(H("Endpoints da API REST", 2))
    api_data = [
        ["Metodo", "Rota", "Descricao"],
        ["POST", "/chat", "Chat principal — roteado pelo orchestrator"],
        ["POST", "/pipeline", "Guard pipeline completo (3 guardas + sintese)"],
        ["POST", "/g", "Chat direto com Gemini"],
        ["POST", "/d", "Chat direto com DeepSeek"],
        ["POST", "/debate", "Debate Gemini vs DeepSeek"],
        ["POST", "/file/read", "Le arquivo do projeto"],
        ["POST", "/file/edit", "Edita arquivo no disco"],
        ["POST", "/memory/store", "Grava no MemPalace"],
        ["POST", "/attach", "Processa anexo (PDF/Excel/Word/CSV/imagem)"],
        ["POST", "/context/project", "Define projeto da sessao web"],
        ["GET", "/context", "Retorna estado da sessao web"],
        ["GET", "/health", "Status da API"],
        ["GET", "/status", "Verifica backends disponiveis"],
    ]
    api_table = Table(api_data, colWidths=[1.8 * cm, 4 * cm, 9.7 * cm])
    api_table.setStyle(table_style_base())
    story.append(api_table)
    story.append(PageBreak())

    # ── 6. MemPalace — O Cerebro ──────────────────────────────────────────────
    story.append(H("6. MemPalace — A Memoria Persistente"))
    story.append(HR())

    story.append(P(
        "O MemPalace e um banco de memoria local estruturado — nao e um agente nem um robo. "
        "E uma biblioteca Python que funciona como um 'arquivo inteligente' onde o Jarvas "
        "grava e recupera conhecimento entre sessoes. "
        "A metafora e o 'palacio da memoria', tecnica mnemonica usada por seres humanos."
    ))

    story.append(H("Estrutura do MemPalace", 2))
    story.append(Code(
        "~/.mempalace/palace/\n"
        "  wing_code/             <- asa tematica: codigo\n"
        "    room_meu-projeto/    <- sala: nome do projeto\n"
        "      drawer_xxx.md      <- gaveta: uma memoria individual\n"
        "  wing_user/             <- asa: comportamento do usuario\n"
        "    room_general/\n"
        "      drawer_yyy.md"
    ))

    story.append(H("Inicializando o MemPalace", 2))
    story.append(Code(
        "# 1. Criar o diretorio\n"
        "mkdir .mempalace\n\n"
        "# 2. Inicializar\n"
        "mempalace init .mempalace\n\n"
        "# 3. Minerar (processa arquivos existentes)\n"
        "mempalace mine .mempalace\n\n"
        "# 4. Verificar status\n"
        "jarvas /hmem status"
    ))

    story.append(H("Como o Jarvas usa o MemPalace", 2))
    mp_data = [
        ["Acao", "Quando acontece", "O que e salvo"],
        ["Gravar", "Voce diz 'armazene'", "Acertos, erros, decisoes, padroes da sessao"],
        ["Buscar", "Antes de responder (futuro)", "Conhecimento acumulado de sessoes anteriores"],
        ["Consultar", "/hmem search <busca>", "Busca semantica no historico de aprendizado"],
        ["Grafo", "/hmem kg <entidade>", "Relacoes entre entidades (projetos, decisoes)"],
    ]
    mp_table = Table(mp_data, colWidths=[3 * cm, 5 * cm, 7.5 * cm])
    mp_table.setStyle(table_style_base())
    story.append(mp_table)

    story.append(Spacer(1, 0.4 * cm))
    story.append(Note(
        "O MemPalace requer Python 3.12 no Windows (limitacao do pacote chroma-hnswlib). "
        "No Python 3.13 ele funciona em modo degradado (sem busca semantica vetorial). "
        "Os comandos /hmem funcionam normalmente."
    ))
    story.append(PageBreak())

    # ── 7. Processamento de Arquivos ──────────────────────────────────────────
    story.append(H("7. Processamento de Arquivos"))
    story.append(HR())

    story.append(P(
        "O Jarvas processa qualquer tipo de arquivo de forma <b>guiada pelo seu prompt</b>. "
        "Voce diz o que quer extrair ou transformar — o arquivo e o insumo, "
        "o prompt e a instrucao."
    ))

    story.append(H("Tipos Suportados", 2))
    file_data = [
        ["Extensao", "Biblioteca", "Uso tipico"],
        [".pdf", "pymupdf (fitz)", "Extrair texto, resumir, analisar contratos"],
        [".xlsx / .xls", "openpyxl", "Ler planilhas, transformar colunas, filtrar dados"],
        [".csv", "stdlib csv", "Importar dados, reorganizar colunas"],
        [".docx", "python-docx", "Extrair texto de documentos Word"],
        [".txt", "stdlib", "Processar texto simples"],
        [".jpg / .jpeg / .png", "Pillow + pytesseract", "OCR, extrair texto, gerar Excel"],
    ]
    file_table = Table(file_data, colWidths=[3.5 * cm, 4 * cm, 8 * cm])
    file_table.setStyle(table_style_base())
    story.append(file_table)
    story.append(Spacer(1, 0.4 * cm))

    story.append(H("Exemplos de Uso", 2))
    story.append(Code(
        "# Extrair colunas especificas de uma imagem\n"
        "voce > ocr nota_fiscal.jpg extraia: numero, data, valor total\n"
        "       mas renomeie para ID, Emissao, Montante\n"
        "Jarvas > Arquivo processado: jarvas_outputs/excel/nota_fiscal_resultado.xlsx\n\n"
        "# Resumir um PDF\n"
        "voce > analise contrato.pdf e liste as clausulas de rescisao\n"
        "Jarvas > [lista as clausulas encontradas]\n\n"
        "# Transformar planilha\n"
        "voce > planilha.xlsx filtre apenas linhas onde valor > 1000\n"
        "       e exporte em csv\n"
        "Jarvas > Arquivo processado: jarvas_outputs/csv/planilha_resultado.csv"
    ))

    story.append(H("Organizacao de Saida", 2))
    story.append(Code(
        "jarvas_outputs/      <- na raiz do projeto atual\n"
        "  excel/             <- .xlsx gerados\n"
        "  csv/               <- .csv exportados\n"
        "  pdf/               <- PDFs gerados\n"
        "  docs/              <- Word/texto gerados\n"
        "  images/            <- imagens processadas"
    ))
    story.append(PageBreak())

    # ── 8. Supabase — Historico Completo ──────────────────────────────────────
    story.append(H("8. Supabase — Historico Completo"))
    story.append(HR())

    story.append(P(
        "O Supabase e o arquivo historico do Jarvas. Tudo que acontece na sessao "
        "e salvo la — conversas, debates, edicoes de arquivos, resultados do pipeline "
        "e o log do MemPalace."
    ))

    story.append(H("Tabelas", 2))
    tb_data = [
        ["Tabela", "O que guarda"],
        ["conversations", "Todas as mensagens de chat (usuario + assistente)"],
        ["pipeline_results", "Resposta do Hermes, Gemini, DeepSeek e sintese por mensagem"],
        ["debate_logs", "Topico, rodadas e consenso de cada debate"],
        ["guard_logs", "Interacoes diretas com cada guarda (/g, /d)"],
        ["file_edits", "Arquivo original, editado e diff de cada edicao"],
        ["attachments", "Conteudo extraido e analise de cada arquivo processado"],
        ["memory_logs", "Registro de cada gravacao no MemPalace (wing, room, drawer_id)"],
    ]
    tb_table = Table(tb_data, colWidths=[4.5 * cm, 11 * cm])
    tb_table.setStyle(table_style_base())
    story.append(tb_table)
    story.append(PageBreak())

    # ── 9. Referencia de Configuracao ────────────────────────────────────────
    story.append(H("9. Referencia de Configuracao"))
    story.append(HR())

    story.append(H("Modelos de IA Disponiveis", 2))
    model_data = [
        ["Tipo de Tarefa", "Modelo", "Via"],
        ["Chat (padrao)", "nousresearch/hermes-3-llama-3.1-70b", "OpenRouter"],
        ["Codigo", "meta-llama/llama-3.3-70b-instruct", "OpenRouter"],
        ["Analise", "anthropic/claude-3.5-sonnet", "OpenRouter"],
        ["Visao", "openai/gpt-4o", "OpenRouter"],
        ["Guarda 1", "Google Gemini Flash", "Google AI API"],
        ["Guarda 2", "deepseek-chat", "OpenRouter"],
    ]
    model_table = Table(model_data, colWidths=[3.5 * cm, 7 * cm, 5 * cm])
    model_table.setStyle(table_style_base())
    story.append(model_table)
    story.append(Spacer(1, 0.4 * cm))

    story.append(H("Forcar Modelo Especifico", 2))
    story.append(Code(
        "# Terminal — usar modelo especifico na proxima mensagem\n"
        "voce > /hopen openai/gpt-4o\n"
        "Jarvas > Proxima mensagem usara o modelo: openai/gpt-4o\n\n"
        "# API — especificar modelo no payload\n"
        "POST /chat\n"
        '{\"mensagem\": \"minha pergunta\", \"modelo\": \"openai/gpt-4o\"}'
    ))

    story.append(H("Prioridade de Deteccao de Intent", 2))
    priority_data = [
        ["Prioridade", "Intent", "Regra de deteccao"],
        ["1 (maior)", "SET_PROJECT", "Padrao #/caminho ou #C:/caminho"],
        ["2", "ATTACH / OCR", "Extensao de arquivo no texto (.pdf, .xlsx, .jpg...)"],
        ["3", "FILE_EDIT", "Palavras: edite, melhore, corrija, reescreva, refatore"],
        ["4", "FILE_READ", "Palavras: leia, mostra, abra, ver o arquivo"],
        ["5", "DEBATE", "Palavras: debate, peca um debate, debate sobre"],
        ["6", "STORE_MEMORY", "Palavras: armazene, guarda isso, salva isso, memorize"],
        ["7", "SEARCH_WEB", "Palavras: pesquise, busque na web, procure sobre"],
        ["8", "PIPELINE", "detect_task_type() retorna code/analysis/vision"],
        ["9 (menor)", "CHAT", "Tudo que nao se encaixa acima"],
    ]
    priority_table = Table(priority_data, colWidths=[2 * cm, 3.5 * cm, 10 * cm])
    priority_table.setStyle(table_style_base())
    story.append(priority_table)
    story.append(PageBreak())

    # ── 10. Guia Rapido ───────────────────────────────────────────────────────
    story.append(H("10. Guia Rapido de Uso"))
    story.append(HR())

    story.append(H("Dia 1 — Primeiros passos", 2))
    for step in [
        "Instale o Jarvas e configure o .env com suas chaves de API",
        "Execute 'mempalace init .mempalace' e 'mempalace mine .mempalace'",
        "Abra o terminal e digite: jarvas",
        "Diga oi e explore — o Jarvas detecta a intencao automaticamente",
        "Use /help para ver todos os comandos disponíveis",
    ]:
        story.append(B(step))

    story.append(Spacer(1, 0.3 * cm))
    story.append(H("Fluxo tipico de trabalho com codigo", 2))
    story.append(Code(
        "1. jarvas\n"
        "2. voce > trabalharemos em #C:/projetos/meu-app\n"
        "3. voce > leia o arquivo main.py\n"
        "4. voce > edite main.py para adicionar tratamento de erro\n"
        "5. [testa no terminal]\n"
        "6. voce > debate sobre a melhor estrategia de logging\n"
        "7. voce > armazene as ultimas interacoes\n"
        "8. [amanha: jarvas continuar ontem 15h]"
    ))

    story.append(Spacer(1, 0.3 * cm))
    story.append(H("Fluxo tipico com documentos", 2))
    story.append(Code(
        "1. jarvas\n"
        "2. voce > trabalharemos em #C:/extrações\n"
        "3. voce > ocr nota_fiscal.jpg extraia: numero, data, valor\n"
        "          renomeie para ID, Data_Emissao, Valor_Total\n"
        "4. Jarvas > Arquivo: jarvas_outputs/excel/nota_fiscal_resultado.xlsx\n"
        "5. [abre o Excel gerado e verifica]\n"
        "6. voce > armazene — o OCR desta nota funcionou bem"
    ))
    story.append(Spacer(1, 0.5 * cm))

    story.append(H("Dicas Importantes", 2))
    for dica in [
        "O Jarvas aprende com voce — diga 'armazene' ao final de sessoes produtivas",
        "Para debates, quanto mais especifico o topico, melhor o consenso",
        "O pipeline automatico (3 guardas) so e acionado para topicos tecnicos",
        "Arquivos .env, .pem e .key nunca sao lidos ou editados pelo Jarvas",
        "A interface web (porta 8080) e o terminal sao independentes — podem rodar ao mesmo tempo",
        "Use /hmem search para recuperar aprendizados de sessoes anteriores",
        "O Supabase guarda tudo — voce pode consultar via SQL Editor quando precisar",
    ]:
        story.append(B(dica))
    story.append(PageBreak())

    # ── Rodape / Versao ───────────────────────────────────────────────────────
    story.append(H("Sobre o Jarvas"))
    story.append(HR())

    ver_data = [
        ["Campo", "Valor"],
        ["Versao", "0.4.0 (versao oficial final)"],
        ["Repositorio", "github.com/melowesley/Jarvas-agent"],
        ["Autor", "Wesley Melo de Oliveira"],
        ["Data", "2026-04-15"],
        ["Licenca", "MIT"],
    ]
    ver_table = Table(ver_data, colWidths=[4 * cm, 11.5 * cm])
    ver_table.setStyle(table_style_base())
    story.append(ver_table)
    story.append(Spacer(1, 0.5 * cm))

    story.append(P(
        "O Jarvas e um projeto pessoal de IA distribuida criado para demonstrar como "
        "multiplos modelos de linguagem podem colaborar de forma estruturada, aprender "
        "com as interacoes e se tornar progressivamente mais uteis. "
        "A versao 0.4.0 marca a conclusao da arquitetura base — o 'primeiro neuronio' "
        "de um sistema que continuara evoluindo."
    ))

    # Build
    doc.build(story)
    print(f"PDF gerado: {OUTPUT}")


if __name__ == "__main__":
    build_pdf()
