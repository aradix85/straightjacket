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

    API key is read from the environment variable named in ai.api_key_env.
    The api_key parameter is accepted for backward compatibility but ignored.
    """
    _c = cfg()
    provider_type = _c.ai.provider

    # Resolve API key from environment variable configured in config.yaml
    env_var = _c.ai.api_key_env
    resolved_key = os.environ.get(env_var, "")

    if not resolved_key:
        raise ValueError(
            f"No API key found. Set the ${env_var} environment variable."
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
