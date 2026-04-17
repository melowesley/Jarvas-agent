"""Testa metadados enriquecidos do conversation_miner v0.5.0."""
from jarvas.miners.conversation_miner import _enriched_meta


def test_enriched_meta_contains_required_fields():
    payload = {"learnings": ["x"], "confidence": 0.8}
    meta = _enriched_meta(
        "sess-123", "2026-04-17T00:00:00Z", 0.8,
        agent_name="gemini_analyst",
        payload=payload,
    )
    assert meta["session_id"] == "sess-123"
    assert meta["timestamp"] == "2026-04-17T00:00:00Z"
    assert meta["confidence"] == 0.8
    assert meta["agent_name"] == "gemini_analyst"
    assert meta["delegation_path"] == ["gemini_analyst"]
    assert len(meta["hash_conteudo"]) == 16


def test_enriched_meta_hash_is_deterministic():
    payload = {"a": 1, "b": 2}
    m1 = _enriched_meta("s", "t", 0.5, agent_name="deepseek_coder", payload=payload)
    m2 = _enriched_meta("s", "t", 0.5, agent_name="deepseek_coder", payload=payload)
    assert m1["hash_conteudo"] == m2["hash_conteudo"]


def test_enriched_meta_hash_differs_by_payload():
    m1 = _enriched_meta("s", "t", 0.5, agent_name="gemini_analyst", payload={"a": 1})
    m2 = _enriched_meta("s", "t", 0.5, agent_name="gemini_analyst", payload={"a": 2})
    assert m1["hash_conteudo"] != m2["hash_conteudo"]
