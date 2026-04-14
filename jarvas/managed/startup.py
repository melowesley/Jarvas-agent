# jarvas/managed/startup.py

from .store import create_agent, list_agents
from .models import AgentCreate

PRESET_AGENTS = [
    {
        "name": "hermes",
        "model": "nousresearch/hermes-3-llama-3.1-70b",
        "tools": ["bash", "write", "read", "web_search"],
        "callable_agents": [],  # to be populated
    },
    {
        "name": "gemini-guard",
        "model": "gemini-2.5-flash",
        "tools": ["web_search", "read"],
    },
    {
        "name": "deepseek-guard",
        "model": "deepseek/deepseek-chat",
        "tools": ["read", "write"],
    },
    {
        "name": "gemma-local",
        "model": "ollama/llama3.2:3b",
        "system_prompt": (
            "Você é Jarvas, um assistente de código com acesso direto ao VSCode. "
            "Use vscode_edit para modificar arquivos, vscode_open para abrir, "
            "vscode_terminal para executar comandos, vscode_list para listar arquivos. "
            "Sempre leia o arquivo com read antes de editar. "
            "Seja preciso: forneça old_text exato ao usar vscode_edit."
        ),
        "tools": ["read", "web_search", "vscode_open", "vscode_edit", "vscode_terminal", "vscode_list"],
        "description": "Agente local via Ollama/Gemma 4 — edita o VSCode diretamente sem depender de nuvem",
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