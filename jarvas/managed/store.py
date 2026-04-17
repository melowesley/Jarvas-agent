# jarvas/managed/store.py

import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional
from .models import (
    AgentCreate, AgentRecord, AgentUpdate,
    SkillCreate, SkillRecord, SkillRef,
    EnvironmentCreate, EnvironmentRecord,
    SessionCreate, SessionRecord
)

# Dicts em memória (fonte de verdade em runtime)
_agents: Dict[str, AgentRecord] = {}
_versions: Dict[str, List[AgentRecord]] = {}  # id → lista de versões históricas
_skills: Dict[str, SkillRecord] = {}
_envs: Dict[str, EnvironmentRecord] = {}
_sessions: Dict[str, SessionRecord] = {}
_events: Dict[str, List[dict]] = {}
_queues: Dict[str, asyncio.Queue] = {}
_pending_tool_results: Dict[str, tuple] = {}  # tool_call_id → (asyncio.Event, result|None)
_resolved_tool_ids: Dict[str, float] = {}    # tool_call_id → timestamp (TTL dedup)
_RESOLVED_TTL = 300  # 5 minutos

# ── Agents ──────────────────────────────────────────────────────────

def create_agent(data: AgentCreate) -> AgentRecord:
    record = AgentRecord(**data.model_dump())
    _agents[record.id] = record
    _versions[record.id] = [record]
    return record

def get_agent(agent_id: str) -> Optional[AgentRecord]:
    return _agents.get(agent_id)

def list_agents(include_archived: bool = False) -> List[AgentRecord]:
    agents = list(_agents.values())
    if not include_archived:
        agents = [a for a in agents if a.archived_at is None]
    return agents

def update_agent(agent_id: str, data: AgentUpdate) -> AgentRecord:
    if agent_id not in _agents:
        raise ValueError(f"Agent {agent_id} not found")
    
    record = _agents[agent_id]
    if data.version != record.version:
        raise ValueError(f"Version conflict: expected {record.version}, got {data.version}")
    
    # Aplicar updates
    update_data = data.model_dump(exclude_unset=True, exclude={"version"})
    for key, value in update_data.items():
        if key == "metadata" and value is not None:
            # Merge metadata
            record.metadata.update(value)
            # Remove keys with empty string
            record.metadata = {k: v for k, v in record.metadata.items() if v != ""}
        elif value is not None:
            setattr(record, key, value)
    
    # Increment version and update timestamp
    record.version += 1
    record.updated_at = datetime.utcnow()
    
    # Save to versions
    _versions[agent_id].append(record)
    
    return record

def archive_agent(agent_id: str) -> AgentRecord:
    if agent_id not in _agents:
        raise ValueError(f"Agent {agent_id} not found")
    
    record = _agents[agent_id]
    record.archived_at = datetime.utcnow()
    return record

def list_agent_versions(agent_id: str) -> List[AgentRecord]:
    return _versions.get(agent_id, [])

# ── Skills ──────────────────────────────────────────────────────────

def create_skill(data: SkillCreate) -> SkillRecord:
    record = SkillRecord(**data.model_dump())
    _skills[record.id] = record
    return record

def get_skill(skill_id: str) -> Optional[SkillRecord]:
    return _skills.get(skill_id)

def list_skills() -> List[SkillRecord]:
    return list(_skills.values())

def delete_skill(skill_id: str) -> None:
    if skill_id in _skills:
        del _skills[skill_id]

# ── Environments ────────────────────────────────────────────────────

def create_environment(data: EnvironmentCreate) -> EnvironmentRecord:
    record = EnvironmentRecord(**data.model_dump())
    _envs[record.id] = record
    return record

def get_environment(env_id: str) -> Optional[EnvironmentRecord]:
    return _envs.get(env_id)

def list_environments() -> List[EnvironmentRecord]:
    return list(_envs.values())

# ── Sessions ────────────────────────────────────────────────────────

def create_session(data: SessionCreate) -> SessionRecord:
    record = SessionRecord(**data.model_dump())
    _sessions[record.id] = record
    return record

def get_session(session_id: str) -> Optional[SessionRecord]:
    return _sessions.get(session_id)

def set_session_status(session_id: str, status: str) -> None:
    if session_id in _sessions:
        _sessions[session_id].status = status
        _sessions[session_id].updated_at = datetime.utcnow()

# ── Events ──────────────────────────────────────────────────────────

def append_event(session_id: str, event: dict) -> None:
    if session_id not in _events:
        _events[session_id] = []
    _events[session_id].append(event)

def get_events(session_id: str) -> List[dict]:
    return _events.get(session_id, [])

# ── Queues ──────────────────────────────────────────────────────────

def get_or_create_queue(session_id: str) -> asyncio.Queue:
    if session_id not in _queues:
        _queues[session_id] = asyncio.Queue()
    return _queues[session_id]

def clear_queue(session_id: str) -> None:
    if session_id in _queues:
        while not _queues[session_id].empty():
            _queues[session_id].get_nowait()

# ── Helpers ─────────────────────────────────────────────────────────

def reconstruct_history(session_id: str) -> list[dict]:
    """Reconstrói histórico de mensagens no formato OpenAI para o runtime."""
    events = get_events(session_id)
    msgs = []
    for e in events:
        if e["type"] == "user.message":
            msgs.append({"role": "user", "content": e["content"]})
        elif e["type"] == "agent.message":
            msgs.append({"role": "assistant", "content": e["content"]})
        elif e["type"] == "agent.tool_use":
            # Reconstruct assistant tool_calls message
            msgs.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": e.get("tool_call_id", "call_unknown"),
                    "type": "function",
                    "function": {
                        "name": e["tool_name"],
                        "arguments": __import__("json").dumps(e.get("tool_input", {})),
                    }
                }]
            })
        elif e["type"] == "agent.tool_result":
            msgs.append({
                "role": "tool",
                "tool_call_id": e.get("tool_call_id", "call_unknown"),
                "content": e["output"],
            })
    return msgs

async def enqueue(queue: asyncio.Queue, session_id: str, event_type: str, payload: dict) -> None:
    """Persiste o evento e enfileira para o SSE stream ativo."""
    from datetime import datetime as _dt, timezone as _tz
    event = {"type": event_type, "session_id": session_id, **payload,
             "timestamp": _dt.now(_tz.utc).isoformat()}
    append_event(session_id, event)
    await queue.put(event)

def get_env(env_id: str):
    """Alias de get_environment para uso no runtime."""
    return get_environment(env_id)

# ── Pending VSCode tool callbacks ────────────────────────────────────

def register_pending_tool(tool_call_id: str) -> asyncio.Event:
    """Registra um tool_call aguardando callback da extensão VSCode."""
    event = asyncio.Event()
    _pending_tool_results[tool_call_id] = (event, None)
    return event

def resolve_pending_tool(tool_call_id: str, output: str, is_error: bool) -> str:
    """Resolve um tool_call pendente. Retorna 'resolved', 'duplicate' ou 'not_found'."""
    # Purge expired resolved IDs
    now = time.monotonic()
    expired = [k for k, ts in _resolved_tool_ids.items() if now - ts > _RESOLVED_TTL]
    for k in expired:
        _resolved_tool_ids.pop(k, None)

    # Idempotência: já resolvido anteriormente
    if tool_call_id in _resolved_tool_ids:
        return "duplicate"

    pending = _pending_tool_results.get(tool_call_id)
    if not pending:
        return "not_found"

    event, existing = pending
    if existing is not None:
        # Resultado já preenchido mas ainda não consumido — tratar como duplicate
        _resolved_tool_ids[tool_call_id] = now
        return "duplicate"

    _pending_tool_results[tool_call_id] = (event, (output, is_error))
    _resolved_tool_ids[tool_call_id] = now
    event.set()
    return "resolved"

def pop_pending_tool_result(tool_call_id: str) -> tuple[str, bool] | None:
    """Remove e retorna o resultado de um tool_call resolvido."""
    pending = _pending_tool_results.pop(tool_call_id, None)
    if pending and pending[1] is not None:
        return pending[1]
    return None