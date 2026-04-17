"""Testa unificação managed/ na v0.5.0 — presets extra, memory_scope."""
from jarvas.managed.models import AgentCreate, AgentRecord, AgentUpdate
from jarvas.managed import store as _store
from jarvas.managed.startup import PRESET_AGENTS, seed_preset_agents


def _reset_store():
    _store._agents.clear()
    _store._versions.clear()


def test_agent_record_has_memory_scope_default():
    rec = AgentCreate(name="t", model="m")
    assert rec.memory_scope == "session"


def test_agent_record_accepts_memory_scope():
    rec = AgentCreate(name="t", model="m", memory_scope="global")
    assert rec.memory_scope == "global"


def test_agent_update_accepts_memory_scope():
    _reset_store()
    rec = _store.create_agent(AgentCreate(name="t", model="m"))
    updated = _store.update_agent(
        rec.id, AgentUpdate(version=rec.version, memory_scope="project")
    )
    assert updated.memory_scope == "project"


def test_seed_includes_v050_agents():
    _reset_store()
    seed_preset_agents()
    names = {a.name for a in _store.list_agents()}
    # Novos v0.5.0
    assert "gemini_analyst" in names
    assert "deepseek_coder" in names
    assert "memory_miner" in names
    assert "file_editor" in names
    assert "autoescola_specialist" in names
    assert "uiux_specialist" in names
    # Legados preservados
    assert "hermes" in names
    assert "gemma-local" in names


def test_seed_is_idempotent():
    _reset_store()
    seed_preset_agents()
    count1 = len(_store.list_agents())
    seed_preset_agents()
    count2 = len(_store.list_agents())
    assert count1 == count2


def test_presets_have_memory_scope():
    for p in PRESET_AGENTS:
        assert p.get("memory_scope") in ("session", "project", "global")
