#!/usr/bin/env python3
"""AI provider router: creates and caches the right provider based on config.

This is the single entry point for getting an AI provider. Call get_provider()
with an API key to get a ready-to-use AIProvider instance. The provider type
is determined by config.yaml ("ai.provider": "anthropic" or "openai_compatible").
"""

import os

from ..config_loader import cfg
from .provider_base import AIProvider

# PROVIDER CACHE

_provider_cache: dict[str, AIProvider] = {}

def get_provider(api_key: str | None = None) -> AIProvider:
    """Get or create the AI provider based on config.

    The API key is resolved from config in this order:
    1. server.api_key in config.yaml (if non-empty)
    2. Environment variable named in ai.api_key_env (e.g. CEREBRAS_API_KEY)
    3. api_key parameter (UI-entered key from session state)

    Returns:
        An AIProvider instance (cached per api_key).

    Raises:
        ValueError: if provider type is unknown or no key found.
    """
    _c = cfg()
    provider_type = _c.ai.provider  # "anthropic" or "openai_compatible"

    # Resolve API key: config.yaml server.api_key → ai.api_key_env → passed arg
    resolved_key = ""

    # 1. Check server.api_key in config
    try:
        server_key = _c.server.api_key
        if server_key and str(server_key).strip():
            resolved_key = str(server_key).strip()
    except (AttributeError, KeyError):
        pass

    # 2. Check config-driven env var (ai.api_key_env)
    if not resolved_key:
        env_var = _c.ai.api_key_env
        resolved_key = os.environ.get(env_var, "")

    # 3. UI-entered key from session state
    if not resolved_key and api_key:
        resolved_key = api_key

    if not resolved_key:
        raise ValueError(
            f"No API key found. Set server.api_key in config.yaml, "
            f"or set ${_c.ai.api_key_env} environment variable."
        )

    # Cache key: provider type + api_key hash (don't store raw key)
    cache_key = f"{provider_type}:{hash(resolved_key)}"
    if cache_key in _provider_cache:
        return _provider_cache[cache_key]

    # Resolve api_base
    api_base = _c.ai.api_base or None

    if provider_type == "anthropic":
        from .provider_anthropic import AnthropicProvider
        provider: AIProvider = AnthropicProvider(api_key=resolved_key, api_base=api_base)
    elif provider_type == "openai_compatible":
        from .provider_openai import OpenAICompatibleProvider
        provider = OpenAICompatibleProvider(api_key=resolved_key, api_base=api_base)
    else:
        raise ValueError(f"Unknown AI provider: {provider_type!r}")

    _provider_cache[cache_key] = provider
    return provider

def clear_provider_cache():
    """Clear cached providers. Use after config reload or key change."""
    _provider_cache.clear()
