# tests/test_supabase_client.py
from unittest.mock import patch, MagicMock


def test_salvar_mensagem_chama_supabase():
    mock_sb = MagicMock()
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

    with patch("jarvas.supabase_client._get_client", return_value=mock_sb):
        from jarvas.supabase_client import save_message
        save_message(
            session_id="sessao-teste",
            role="user",
            content="olá",
            model="nousresearch/hermes-3-llama-3.1-70b",
            task_type="chat",
        )

    mock_sb.table.assert_called_with("conversations")
    mock_sb.table.return_value.insert.assert_called_once()


def test_carregar_historico_retorna_lista():
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"role": "user", "content": "oi"},
        {"role": "assistant", "content": "olá!"},
    ]

    with patch("jarvas.supabase_client._get_client", return_value=mock_sb):
        from jarvas.supabase_client import load_history
        resultado = load_history("sessao-teste", limit=10)

    assert len(resultado) == 2
    assert resultado[0]["role"] == "user"


def test_salvar_log_guarda():
    mock_sb = MagicMock()
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

    with patch("jarvas.supabase_client._get_client", return_value=mock_sb):
        from jarvas.supabase_client import save_guard_log
        save_guard_log("gemini", "pergunta", "resposta")

    mock_sb.table.assert_called_with("guard_logs")


def test_carregar_sessao_retorna_lista_vazia_sem_dados():
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.lte.return_value.order.return_value.limit.return_value.execute.return_value.data = []

    with patch("jarvas.supabase_client._get_client", return_value=mock_sb):
        from jarvas.supabase_client import load_session_by_time
        resultado = load_session_by_time("ontem", "15h")

    assert resultado == []
