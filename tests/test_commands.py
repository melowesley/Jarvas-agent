from unittest.mock import patch


def test_comando_help():
    from jarvas.commands import dispatch
    resultado = dispatch("/help", [])
    assert resultado is not None
    assert "/g" in resultado


def test_comando_desconhecido():
    from jarvas.commands import dispatch
    resultado = dispatch("/xyz", [])
    assert "desconhecido" in resultado.lower() or "não" in resultado.lower()


def test_comando_g_chama_gemini():
    with patch("jarvas.commands.gemini_chat", return_value="resp gemini") as mock_g:
        from jarvas.commands import dispatch
        resultado = dispatch("/g olá gemini", [])
    mock_g.assert_called_once_with("olá gemini")
    assert "resp gemini" in resultado


def test_comando_d_chama_deepseek():
    with patch("jarvas.commands.deepseek_chat", return_value="resp deepseek") as mock_d:
        from jarvas.commands import dispatch
        resultado = dispatch("/d olá deepseek", [])
    mock_d.assert_called_once_with("olá deepseek")
    assert "resp deepseek" in resultado


def test_comando_debate():
    with patch("jarvas.commands.run_debate") as mock_debate, \
         patch("jarvas.commands.format_debate_result", return_value="resultado formatado"):
        mock_debate.return_value = {"topic": "t", "rounds": [], "consensus": "c"}
        from jarvas.commands import dispatch
        resultado = dispatch("/debate python vs rust", [])
    mock_debate.assert_called_once_with("python vs rust")
    assert "resultado formatado" in resultado
