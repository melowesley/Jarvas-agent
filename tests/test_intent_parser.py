from jarvas.intent_parser import parse, Intent


def test_intent_is_dataclass():
    i = Intent(type="CHAT", raw="oi")
    assert i.type == "CHAT"
    assert i.raw == "oi"
    assert i.args == {}


def test_set_project_windows_path():
    i = parse("jarvas trabalharemos em #C:/projetos/ocr")
    assert i.type == "SET_PROJECT"
    assert i.args["path"] == "C:/projetos/ocr"


def test_set_project_unix_path():
    i = parse("vamos trabalhar em #/home/user/projeto")
    assert i.type == "SET_PROJECT"
    assert i.args["path"] == "/home/user/projeto"


def test_attach_pdf():
    i = parse("processe esse arquivo relatorio.pdf e me de um resumo")
    assert i.type == "ATTACH"
    assert "relatorio.pdf" in i.args["path"]
    assert i.args["file_type"] == "pdf"


def test_attach_excel():
    i = parse("analise a planilha dados.xlsx")
    assert i.type == "ATTACH"
    assert i.args["file_type"] == "xlsx"


def test_ocr_image():
    i = parse("ocr nota_fiscal.jpg e gere excel")
    assert i.type == "OCR"
    assert "nota_fiscal.jpg" in i.args["path"]


def test_ocr_extraia_texto():
    i = parse("extraia texto da imagem foto.png")
    assert i.type == "OCR"


def test_file_edit():
    i = parse("edite o arquivo main.py para usar snake_case")
    assert i.type == "FILE_EDIT"
    assert "main.py" in i.args["instruction"]


def test_file_edit_melhore():
    i = parse("melhore o codigo em utils.py")
    assert i.type == "FILE_EDIT"


def test_file_read():
    i = parse("leia o arquivo config.py")
    assert i.type == "FILE_READ"


def test_file_read_mostra():
    i = parse("mostra o arquivo router.py")
    assert i.type == "FILE_READ"


def test_debate():
    i = parse("debate sobre qual banco de dados usar")
    assert i.type == "DEBATE"
    assert "banco de dados" in i.args["topic"]


def test_debate_peca():
    i = parse("jarvas peca um debate sobre python vs javascript")
    assert i.type == "DEBATE"


def test_store_memory():
    i = parse("armazene as ultimas interacoes")
    assert i.type == "STORE_MEMORY"
    assert i.args["scope"] == 5


def test_store_memory_guarda():
    i = parse("guarda isso no mempalace")
    assert i.type == "STORE_MEMORY"


def test_search_web():
    i = parse("pesquise sobre pytesseract no windows")
    assert i.type == "SEARCH_WEB"
    assert "pytesseract" in i.args["query"]


def test_pipeline_code():
    i = parse("escreva um script python para renomear arquivos")
    assert i.type == "PIPELINE"
    assert i.args["task_type"] == "code"


def test_pipeline_analysis():
    i = parse("analise esse trecho de codigo")
    assert i.type == "PIPELINE"
    assert i.args["task_type"] == "analysis"


def test_chat_fallback():
    i = parse("oi tudo bem?")
    assert i.type == "CHAT"


def test_priority_set_project_over_attach():
    # SET_PROJECT tem prioridade sobre ATTACH
    i = parse("trabalhar em #C:/projetos/dados.xlsx")
    assert i.type == "SET_PROJECT"


# Regressão: falsos positivos de FILE_READ (issue com substring matching de "ver", "ler", etc)
def test_chat_conversa_not_file_read():
    # "conversa" contém "ver" como substring, mas não é FILE_READ
    i = parse("qual modelo você utiliza? consegue manter essa conversa?")
    assert i.type == "CHAT"


def test_chat_universo_not_file_read():
    # "universo" contém "ver" como substring
    i = parse("fale sobre o universo")
    assert i.type == "CHAT"


def test_chat_servidor_not_file_read():
    # "servidor" contém "ver" como substring
    i = parse("use o servidor local para testar")
    assert i.type == "CHAT"


def test_chat_converter_not_file_read():
    # "converter" contém "ver" como substring
    i = parse("pode converter isso para JSON?")
    assert i.type == "CHAT"


def test_chat_voce_le_not_file_read():
    # "você lê" contém "lê", mas sem menção a arquivo
    i = parse("você lê bem? qual sua opinião?")
    assert i.type == "CHAT"


def test_chat_poder_not_file_read():
    # "poder" contém "der" mas "ler" é substring — sem arquivo, é CHAT
    i = parse("qual o poder dessa linguagem?")
    assert i.type == "CHAT"


def test_file_read_with_arquivo_keyword():
    # Verdadeiro positivo: FILE_READ com "arquivo"
    i = parse("mostre o arquivo de configuração")
    assert i.type == "FILE_READ"


def test_file_read_extension():
    # Verdadeiro positivo: FILE_READ detectado pelo bloco 2 (extensão)
    i = parse("leia o arquivo README.md")
    assert i.type == "FILE_READ"
    assert "README.md" in i.args.get("path", i.args.get("instruction", ""))
