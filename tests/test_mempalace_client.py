from unittest.mock import patch, MagicMock


def test_hmem_status():
    mock_tools = MagicMock()
    mock_tools.tool_status.return_value = {"total": 42, "wings": 3}

    with patch("jarvas.mempalace_client._get_tools", return_value=mock_tools):
        from jarvas.mempalace_client import handle_hmem
        resultado = handle_hmem("status")

    assert "42" in resultado or "status" in resultado.lower()


def test_hmem_search():
    mock_tools = MagicMock()
    mock_tools.tool_search.return_value = [{"id": "abc", "content": "resultado encontrado"}]

    with patch("jarvas.mempalace_client._get_tools", return_value=mock_tools):
        from jarvas.mempalace_client import handle_hmem
        resultado = handle_hmem("search python")

    assert "resultado encontrado" in resultado or "abc" in resultado


def test_hmem_subcomando_desconhecido():
    from jarvas.mempalace_client import handle_hmem
    resultado = handle_hmem("xyz")
    assert "desconhecido" in resultado.lower() or "uso" in resultado.lower()
