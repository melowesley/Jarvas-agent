from unittest.mock import patch, MagicMock


def test_deepseek_chat_retorna_string():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = "resposta deepseek"

    with patch("jarvas.guard_deepseek._get_client", return_value=mock_client), \
         patch("jarvas.guard_deepseek.save_guard_log"):
        from jarvas.guard_deepseek import chat
        resultado = chat("olá deepseek")

    assert isinstance(resultado, str)
    assert "resposta deepseek" in resultado


def test_deepseek_chat_salva_no_supabase():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = "resp"

    with patch("jarvas.guard_deepseek._get_client", return_value=mock_client), \
         patch("jarvas.guard_deepseek.save_guard_log") as mock_save:
        from jarvas.guard_deepseek import chat
        chat("teste")

    mock_save.assert_called_once_with("deepseek", "teste", "resp")
