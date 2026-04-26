import hashlib
import os

from ..config_loader import cfg
from .provider_base import AIProvider


_provider_cache: dict[str, AIProvider] = {}


def get_provider() -> AIProvider:
    _c = cfg()
    provider_type = _c.ai.provider

    env_var = _c.ai.api_key_env
    resolved_key = os.environ.get(env_var, "")

    if not resolved_key:
        raise ValueError(f"No API key found. Set the ${env_var} environment variable.")

    cache_key = f"{provider_type}:{hashlib.sha256(resolved_key.encode()).hexdigest()[:16]}"
    if cache_key in _provider_cache:
        return _provider_cache[cache_key]

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
