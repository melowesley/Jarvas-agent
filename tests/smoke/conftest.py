"""Smoke tests — chamadas reais a APIs externas.

Pulam automaticamente se a chave correspondente não estiver no ambiente.
Rode com: `pytest tests/smoke/ -v`
"""
import os

import pytest
from dotenv import load_dotenv

load_dotenv()


def _require(var: str) -> None:
    if not os.getenv(var):
        pytest.skip(f"smoke requer {var} no .env")


@pytest.fixture
def require_openrouter():
    _require("OPENROUTER_API_KEY")


@pytest.fixture
def require_gemini():
    _require("GEMINI_API_KEY")


@pytest.fixture
def require_supabase():
    _require("SUPABASE_URL")
    _require("SUPABASE_KEY")
