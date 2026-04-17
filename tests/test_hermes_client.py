# tests/test_hermes_client.py
from unittest.mock import patch, MagicMock


def test_chat_retorna_resposta_e_modelo():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = "olá, sou Jarvas"

    with patch("jarvas.hermes_client._get_client", return_value=mock_client):
        from jarvas.hermes_client import chat
        resposta, modelo = chat("oi como você está")

    assert isinstance(resposta, str)
    assert "olá" in resposta
    assert modelo == "meta-llama/llama-3.3-70b-instruct"  # chat → llama


def test_chat_usa_modelo_forcado():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = "codigo pronto"

    with patch("jarvas.hermes_client._get_client", return_value=mock_client):
        from jarvas.hermes_client import chat
        resposta, modelo = chat("qualquer coisa", modelo="openai/gpt-4o")

    assert modelo == "openai/gpt-4o"


def test_chat_inclui_historico():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = "resposta"

    historico = [
        {"role": "user", "content": "mensagem anterior"},
        {"role": "assistant", "content": "resposta anterior"},
    ]

    with patch("jarvas.hermes_client._get_client", return_value=mock_client):
        from jarvas.hermes_client import chat
        chat("nova mensagem", historico=historico)

    call_args = mock_client.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    # system + 2 history + current user message = 4
    assert len(messages) == 4
    assert messages[1]["content"] == "mensagem anterior"


def test_chat_codigo_usa_llama():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = "código aqui"

    with patch("jarvas.hermes_client._get_client", return_value=mock_client):
        from jarvas.hermes_client import chat
        _, modelo = chat("cria um script python")

    assert modelo == "meta-llama/llama-3.3-70b-instruct"
