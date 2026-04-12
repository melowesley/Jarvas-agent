# tests/test_router.py
from jarvas.router import detect_task_type, choose_model


def test_detecta_codigo():
    assert detect_task_type("cria um site html") == "code"
    assert detect_task_type("escreve um python script") == "code"
    assert detect_task_type("kotlin app") == "code"


def test_detecta_visao():
    assert detect_task_type("extrai texto da imagem") == "vision"
    assert detect_task_type("lê essa foto") == "vision"


def test_detecta_analise():
    assert detect_task_type("analise esse código") == "analysis"
    assert detect_task_type("compare as duas opções") == "analysis"


def test_chat_padrao():
    assert detect_task_type("oi como você está") == "chat"
    assert detect_task_type("qual é a capital da França") == "chat"


def test_modelo_codigo():
    assert choose_model("code") == "meta-llama/llama-3.3-70b-instruct"


def test_modelo_visao():
    assert choose_model("vision") == "openai/gpt-4o"


def test_modelo_analise():
    assert choose_model("analysis") == "anthropic/claude-3.5-sonnet"


def test_modelo_chat():
    assert choose_model("chat") == "nousresearch/hermes-3-llama-3.1-70b"
