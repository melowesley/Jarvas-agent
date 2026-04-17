"""Smoke: 1 chamada real ao OpenRouter via hermes_client."""
import pytest


@pytest.mark.usefixtures("require_openrouter")
def test_hermes_chat_real():
    from jarvas.hermes_client import chat

    resposta, modelo = chat("Responda apenas a palavra OK.", historico=[])

    assert isinstance(resposta, str) and resposta.strip()
    assert "/" in modelo, f"modelo inesperado: {modelo}"
