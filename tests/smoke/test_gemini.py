"""Smoke: web_search real via guard_gemini."""
import pytest


@pytest.mark.usefixtures("require_gemini")
def test_gemini_web_search_real():
    from jarvas.guard_gemini import web_search

    resp = web_search("capital do Brasil")

    assert isinstance(resp, str) and resp.strip(), "web_search retornou vazio"
