from unittest.mock import patch


def test_debate_retorna_consenso():
    with patch("jarvas.debate.gemini_chat") as mock_g, \
         patch("jarvas.debate.deepseek_chat") as mock_d, \
         patch("jarvas.debate.save_debate_log"):
        mock_g.return_value = "Gemini: Python é melhor por legibilidade."
        mock_d.return_value = "DeepSeek: Python é melhor pelo ecossistema."

        from jarvas.debate import run_debate
        resultado = run_debate("Qual linguagem usar para IA?", max_rounds=1)

    assert "topic" in resultado
    assert "consensus" in resultado
    assert "rounds" in resultado
    assert len(resultado["rounds"]) >= 1


def test_debate_respeita_max_rounds():
    with patch("jarvas.debate.gemini_chat", return_value="gemini"), \
         patch("jarvas.debate.deepseek_chat", return_value="deepseek"), \
         patch("jarvas.debate.save_debate_log"):
        from jarvas.debate import run_debate
        resultado = run_debate("tópico", max_rounds=2)

    assert len(resultado["rounds"]) <= 2
