# jarvas/managed/router.py

import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .models import (
    AgentCreate, AgentUpdate, SendMessageRequest,
    SkillCreate, EnvironmentCreate, SessionCreate,
    ToolResultRequest,
)
from .store import (
    create_agent, get_agent, list_agents, update_agent, archive_agent, list_agent_versions,
    create_skill, get_skill, list_skills, delete_skill,
    create_environment, get_environment, list_environments,
    create_session, get_session, get_events,
    get_or_create_queue,
    resolve_pending_tool,
)
from .runtime import run_agent_loop
from .sse import event_generator, replay_generator

managed_router = APIRouter(prefix="/v1")


# ── Agents ───────────────────────────────────────────────────────────

@managed_router.post("/agents", status_code=201)
async def post_agents(data: AgentCreate):
    return create_agent(data)


@managed_router.get("/agents")
async def get_agents(include_archived: bool = False):
    return list_agents(include_archived)


@managed_router.get("/agents/{agent_id}")
async def get_agent_by_id(agent_id: str):
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@managed_router.patch("/agents/{agent_id}")
async def patch_agent(agent_id: str, data: AgentUpdate):
    try:
        return update_agent(agent_id, data)
    except ValueError as e:
        status = 409 if "Version conflict" in str(e) else 404
        raise HTTPException(status_code=status, detail=str(e))


@managed_router.post("/agents/{agent_id}/archive")
async def post_archive_agent(agent_id: str):
    try:
        return archive_agent(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@managed_router.get("/agents/{agent_id}/versions")
async def get_agent_versions(agent_id: str):
    return list_agent_versions(agent_id)


# ── Skills ───────────────────────────────────────────────────────────

@managed_router.post("/skills", status_code=201)
async def post_skills(data: SkillCreate):
    return create_skill(data)


@managed_router.get("/skills")
async def get_skills_list():
    return list_skills()


@managed_router.get("/skills/{skill_id}")
async def get_skill_by_id(skill_id: str):
    skill = get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


@managed_router.delete("/skills/{skill_id}", status_code=204)
async def delete_skill_by_id(skill_id: str):
    delete_skill(skill_id)


# ── Environments ─────────────────────────────────────────────────────

@managed_router.post("/environments", status_code=201)
async def post_environments(data: EnvironmentCreate):
    return create_environment(data)


@managed_router.get("/environments")
async def get_environments_list():
    return list_environments()


@managed_router.get("/environments/{env_id}")
async def get_environment_by_id(env_id: str):
    env = get_environment(env_id)
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")
    return env


# ── Sessions ─────────────────────────────────────────────────────────

@managed_router.post("/sessions", status_code=201)
async def post_sessions(data: SessionCreate):
    agent = get_agent(data.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return create_session(data)


@managed_router.get("/sessions/{session_id}")
async def get_session_by_id(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@managed_router.post("/sessions/{session_id}/events", status_code=202)
async def post_session_events(session_id: str, data: SendMessageRequest):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == "running":
        raise HTTPException(status_code=409, detail="Session is already running")

    queue = get_or_create_queue(session_id)
    asyncio.create_task(run_agent_loop(session_id, data.content, queue))
    return {"accepted": True, "session_id": session_id}


@managed_router.get("/sessions/{session_id}/stream")
async def get_session_stream(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

    if session.status == "idle":
        # Session already finished — replay stored events
        events = get_events(session_id)
        return StreamingResponse(
            replay_generator(events),
            media_type="text/event-stream",
            headers=headers,
        )

    # Live stream
    queue = get_or_create_queue(session_id)
    return StreamingResponse(
        event_generator(session_id, queue),
        media_type="text/event-stream",
        headers=headers,
    )


@managed_router.get("/sessions/{session_id}/events")
async def get_session_events(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return get_events(session_id)


@managed_router.post("/sessions/{session_id}/tool_result", status_code=200)
async def post_tool_result(session_id: str, data: ToolResultRequest):
    """Extensão VSCode chama este endpoint após executar uma vscode_* tool."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    found = resolve_pending_tool(data.tool_call_id, data.output, data.is_error)
    if not found:
        raise HTTPException(status_code=404, detail="No pending tool call with this ID")
    return {"ok": True}
