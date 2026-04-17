"""
model_registry.py
Registro central de modelos do Jarvas.
- Aliases curtos para comandos rápidos
- Fallback automático por família
- Verificação de disponibilidade via OpenRouter
"""

import os
import httpx
from datetime import datetime, timedelta, timezone

# ─────────────────────────────────────────────
# ALIASES — o que o usuário digita → modelo real
# ─────────────────────────────────────────────
MODEL_ALIASES = {
    # Anthropic Claude
    "claude":       "anthropic/claude-sonnet-4-5",
    "sonnet":       "anthropic/claude-sonnet-4-5",
    "opus":         "anthropic/claude-opus-4",
    "haiku":        "anthropic/claude-haiku-3-5",

    # Google Gemini
    "gemini":       "google/gemini-2.0-flash-001",
    "flash":        "google/gemini-2.0-flash-001",
    "pro":          "google/gemini-1.5-pro",

    # DeepSeek
    "deepseek":     "deepseek/deepseek-chat",
    "deep":         "deepseek/deepseek-chat",
    "r1":           "deepseek/deepseek-r1",

    # Meta Llama
    "llama":        "meta-llama/llama-3.3-70b-instruct",
    "llama3":       "meta-llama/llama-3.3-70b-instruct",

    # Mistral
    "mistral":      "mistralai/mistral-large",
    "mixtral":      "mistralai/mixtral-8x7b-instruct",

    # Hermes (modelo padrão do Jarvas)
    "hermes":       "nousresearch/hermes-3-llama-3.1-70b",

    # OpenAI (via OpenRouter)
    "gpt4o":        "openai/gpt-4o",
    "gpt4o-mini":   "openai/gpt-4o-mini",
    "mini":         "openai/gpt-4o-mini",

    # Claude 3.7
    "sonnet-3.7":   "anthropic/claude-3.7-sonnet",
    "claude-3.7":   "anthropic/claude-3.7-sonnet",

    # Legacy — modelos descontinuados redirecionam automaticamente
    "claude-3.5-sonnet":   "anthropic/claude-sonnet-4-5",
    "claude-3-sonnet":     "anthropic/claude-sonnet-4-5",
    "claude-3-haiku":      "anthropic/claude-haiku-3-5",
    "claude-3-opus":       "anthropic/claude-opus-4",
    "gemini-pro":          "google/gemini-2.0-flash-001",
    "gpt-4":               "anthropic/claude-sonnet-4-5",
}

# ─────────────────────────────────────────────
# FALLBACK — se modelo X falhar, tenta Y, depois Z
# ─────────────────────────────────────────────
FALLBACK_CHAINS = {
    "anthropic/claude-sonnet-4-5": [
        "anthropic/claude-haiku-3-5",
        "google/gemini-2.0-flash-001",
        "deepseek/deepseek-chat",
    ],
    "anthropic/claude-opus-4": [
        "anthropic/claude-sonnet-4-5",
        "google/gemini-1.5-pro",
        "deepseek/deepseek-r1",
    ],
    "anthropic/claude-haiku-3-5": [
        "google/gemini-2.0-flash-001",
        "deepseek/deepseek-chat",
    ],
    "google/gemini-2.0-flash-001": [
        "google/gemini-1.5-pro",
        "anthropic/claude-haiku-3-5",
        "deepseek/deepseek-chat",
    ],
    "deepseek/deepseek-chat": [
        "deepseek/deepseek-r1",
        "google/gemini-2.0-flash-001",
        "anthropic/claude-haiku-3-5",
    ],
    "deepseek/deepseek-r1": [
        "deepseek/deepseek-chat",
        "google/gemini-2.0-flash-001",
    ],
    "nousresearch/hermes-3-llama-3.1-70b": [
        "meta-llama/llama-3.3-70b-instruct",
        "google/gemini-2.0-flash-001",
        "deepseek/deepseek-chat",
    ],
    "meta-llama/llama-3.3-70b-instruct": [
        "nousresearch/hermes-3-llama-3.1-70b",
        "google/gemini-2.0-flash-001",
        "deepseek/deepseek-chat",
    ],
    "anthropic/claude-3.5-sonnet": [
        "anthropic/claude-sonnet-4-5",
        "anthropic/claude-haiku-3-5",
        "google/gemini-2.0-flash-001",
    ],
    "openai/gpt-4o": [
        "anthropic/claude-sonnet-4-5",
        "google/gemini-1.5-pro",
        "deepseek/deepseek-r1",
    ],
    "mistralai/mistral-large": [
        "meta-llama/llama-3.3-70b-instruct",
        "google/gemini-2.0-flash-001",
        "deepseek/deepseek-chat",
    ],
}

# Cache local para não chamar API a cada request
_available_models_cache: list[str] = []
_cache_expiry: datetime | None = None
CACHE_TTL_HOURS = 6


def resolve_alias(name: str) -> str:
    """
    Converte alias curto para nome completo do modelo.
    Ex: 'claude' → 'anthropic/claude-sonnet-4-5'
    Se não encontrar alias, devolve o próprio nome (pode ser o nome completo).
    """
    return MODEL_ALIASES.get(name.lower().strip(), name)


def get_available_models(force_refresh: bool = False) -> list[str]:
    """
    Retorna lista de modelos disponíveis no OpenRouter.
    Usa cache de 6 horas para não bater na API toda hora.
    """
    global _available_models_cache, _cache_expiry

    now = datetime.now(timezone.utc)
    if not force_refresh and _cache_expiry and now < _cache_expiry and _available_models_cache:
        return _available_models_cache

    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return list(MODEL_ALIASES.values())  # fallback sem API key

    try:
        resp = httpx.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            _available_models_cache = [m["id"] for m in data.get("data", [])]
            _cache_expiry = now + timedelta(hours=CACHE_TTL_HOURS)
            return _available_models_cache
    except Exception:
        pass

    return list(MODEL_ALIASES.values())


def is_model_available(model_id: str) -> bool:
    """Verifica se um modelo específico ainda está ativo no OpenRouter."""
    available = get_available_models()
    return model_id in available


def resolve_with_fallback(model_id: str, verbose: bool = True) -> str:
    """
    Tenta usar o modelo solicitado.
    Se não estiver disponível, percorre a cadeia de fallback automaticamente.
    Retorna o primeiro modelo disponível.
    Loga aviso quando faz substituição.
    """
    # Resolver alias primeiro
    resolved = resolve_alias(model_id)

    if is_model_available(resolved):
        return resolved

    # Modelo não disponível — buscar fallback
    chain = FALLBACK_CHAINS.get(resolved, [])
    for fallback in chain:
        if is_model_available(fallback):
            if verbose:
                print(
                    f"\n[aviso] Modelo '{resolved}' não encontrado ou descontinuado.\n"
                    f"        Usando fallback automático: '{fallback}'\n"
                )
            _update_alias_for_model(resolved, fallback)
            return fallback

    # Nenhum fallback disponível — usar default seguro
    default = "google/gemini-2.0-flash-001"
    if verbose:
        print(
            f"\n[aviso] Nenhum fallback disponível para '{resolved}'.\n"
            f"        Usando modelo padrão de segurança: '{default}'\n"
        )
    return default


def _update_alias_for_model(old_model: str, new_model: str):
    """
    Atualiza os aliases que apontavam para um modelo descontinuado
    para apontarem para o novo modelo automaticamente.
    """
    for alias, target in MODEL_ALIASES.items():
        if target == old_model:
            MODEL_ALIASES[alias] = new_model


def list_aliases() -> str:
    """Retorna tabela formatada de aliases para exibir ao usuário."""
    lines = ["\n  Modelos disponíveis (use o alias no comando):\n"]
    lines.append(f"  {'ALIAS':<12} {'MODELO COMPLETO':<45} {'STATUS'}")
    lines.append("  " + "─" * 70)

    available = get_available_models()
    for alias, model in sorted(MODEL_ALIASES.items()):
        status = "✓ ativo" if model in available else "✗ offline"
        lines.append(f"  {alias:<12} {model:<45} {status}")

    lines.append("")
    return "\n".join(lines)
