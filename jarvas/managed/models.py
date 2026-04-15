from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal
import uuid

# ── Agent ──────────────────────────────────────────────────────────
class AgentCreate(BaseModel):
    name: str
    model: str                          # ex: "nousresearch/hermes-3-llama-3.1-70b"
    system_prompt: str = ""
    tools: list[str] = ["bash", "write", "read", "web_search"]
    skills: list["SkillRef"] = []       # refs para skills registradas
    callable_agents: list[str] = []     # IDs de outros AgentRecords
    description: str | None = None
    metadata: dict = {}

class AgentRecord(AgentCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    archived_at: datetime | None = None

class AgentUpdate(BaseModel):
    version: int                        # otimistic lock
    name: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    tools: list[str] | None = None
    skills: list["SkillRef"] | None = None
    callable_agents: list[str] | None = None
    description: str | None = None
    metadata: dict | None = None

# ── Skill ──────────────────────────────────────────────────────────
class SkillCreate(BaseModel):
    name: str
    description: str
    content: str                        # markdown/text: contexto de domínio
    metadata: dict = {}

class SkillRecord(SkillCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SkillRef(BaseModel):
    skill_id: str

# ── Environment ────────────────────────────────────────────────────
class EnvironmentCreate(BaseModel):
    name: str
    allowed_tools: list[str] = ["bash", "write", "read", "web_search"]

class EnvironmentRecord(EnvironmentCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ── Session ────────────────────────────────────────────────────────
class SessionCreate(BaseModel):
    agent_id: str
    environment_id: str | None = None
    title: str | None = None
    workspace_path: str | None = None

class SessionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    environment_id: str | None = None
    title: str | None = None
    workspace_path: str | None = None
    status: Literal["idle", "running", "error"] = "idle"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# ── Events SSE ─────────────────────────────────────────────────────
class SendMessageRequest(BaseModel):
    content: str

# ── VSCode tool callback ────────────────────────────────────────────
class ToolResultRequest(BaseModel):
    tool_call_id: str
    output: str
    is_error: bool = False