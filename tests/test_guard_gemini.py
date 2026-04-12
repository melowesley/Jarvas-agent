from unittest.mock import patch, MagicMock


def test_gemini_chat_retorna_string():
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = "resposta do gemini"

    with patch("jarvas.guard_gemini._get_model", return_value=mock_model), \
         patch("jarvas.guard_gemini.save_guard_log"):
        from jarvas.guard_gemini import chat
        resultado = chat("olá gemini")

    assert isinstance(resultado, str)
    assert "resposta do gemini" in resultado


def test_gemini_chat_salva_no_supabase():
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = "resposta"

    with patch("jarvas.guard_gemini._get_model", return_value=mock_model), \
         patch("jarvas.guard_gemini.save_guard_log") as mock_save:
        from jarvas.guard_gemini import chat
        chat("teste")

    mock_save.assert_called_once_with("gemini", "teste", "resposta")
