# jarvas/managed/startup.py

from .store import create_agent, list_agents
from .models import AgentCreate

PRESET_AGENTS = [
    {
        "name": "hermes",
        "model": "nousresearch/hermes-3-llama-3.1-70b",
        "tools": ["bash", "write", "read", "web_search", "call_strategy"],
        "callable_agents": [],  # to be populated
        "memory_scope": "session",
    },
    {
        "name": "gemini-guard",
        "model": "gemini-2.5-flash",
        "tools": ["web_search", "read"],
        "memory_scope": "session",
    },
    {
        "name": "deepseek-guard",
        "model": "deepseek/deepseek-chat",
        "tools": ["read", "write"],
        "memory_scope": "session",
    },
    {
        "name": "gemma-local",
        "model": "ollama/qwen2.5:7b-coder",
        "system_prompt": (
            "Você é Jarvas, um assistente de código com acesso direto ao VSCode. "
            "Use vscode_edit para modificar arquivos, vscode_open para abrir, "
            "vscode_terminal para executar comandos, vscode_list para listar arquivos. "
            "Sempre leia o arquivo com read antes de editar. "
            "Seja preciso: forneça old_text exato ao usar vscode_edit."
        ),
        "tools": ["read", "web_search", "vscode_open", "vscode_edit", "vscode_terminal", "vscode_list"],
        "description": "Agente local via Ollama/Gemma 4 — edita o VSCode diretamente sem depender de nuvem",
        "memory_scope": "project",
    },
    # ── v0.5.0: agents formalizados do registry legacy ──────────────
    {
        "name": "gemini_analyst",
        "model": "gemini-2.5-flash",
        "tools": ["web_search", "read"],
        "memory_scope": "session",
        "description": "Analista semântico — mineração e busca web.",
    },
    {
        "name": "deepseek_coder",
        "model": "deepseek/deepseek-chat",
        "tools": ["read", "write", "bash"],
        "memory_scope": "session",
        "description": "Arquivista de código e dados.",
    },
    {
        "name": "memory_miner",
        "model": "gemini-2.5-flash",
        "tools": ["read"],
        "memory_scope": "global",
        "description": "Minerador de conversa → MemPalace.",
    },
    {
        "name": "file_editor",
        "model": "openrouter/auto",
        "tools": ["read", "write"],
        "memory_scope": "project",
        "description": "Leitor/editor/processador de arquivos do projeto.",
    },
    {
        "name": "autoescola_specialist",
        "model": "openrouter/auto",
        "tools": ["read"],
        "memory_scope": "project",
        "description": "Professor do curriculum Autoescola Jarvas.",
    },
    {
        "name": "uiux_specialist",
        "model": "openrouter/auto",
        "tools": ["read", "write"],
        "memory_scope": "project",
        "description": "Especialista UI/UX Pro Max.",
    },
]

def seed_preset_agents():
    existing_names = {a.name for a in list_agents()}
    for preset in PRESET_AGENTS:
        if preset["name"] not in existing_names:
            create_agent(AgentCreate(**preset))
    
    # Update hermes with callable_agents
    hermes = next((a for a in list_agents() if a.name == "hermes"), None)
    if hermes:
        gemini = next((a for a in list_agents() if a.name == "gemini-guard"), None)
        deepseek = next((a for a in list_agents() if a.name == "deepseek-guard"), None)
        callable_ids = []
        if gemini:
            callable_ids.append(gemini.id)
        if deepseek:
            callable_ids.append(deepseek.id)
        if callable_ids:
            from .store import update_agent
            from .models import AgentUpdate
            update_agent(hermes.id, AgentUpdate(version=hermes.version, callable_agents=callable_ids))