import hashlib
import os
from collections.abc import Callable

from ..config_loader import ProviderConfig, cfg, provider_for_role
from .provider_base import AICallSpec, AIProvider, AIResponse, ModelListingProvider


_adapter_cache: dict[str, ModelListingProvider] = {}


def _build_adapter(name: str, pc: ProviderConfig) -> ModelListingProvider:
    resolved_key = os.environ.get(pc.api_key_env, "")
    if not resolved_key:
        raise ValueError(f"No API key for provider '{name}'. Set the ${pc.api_key_env} environment variable.")

    cache_key = (
        f"{name}:{pc.type}:{pc.api_base}:{pc.timeout_seconds}:{hashlib.sha256(resolved_key.encode()).hexdigest()[:16]}"
    )
    if cache_key in _adapter_cache:
        return _adapter_cache[cache_key]

    api_base = pc.api_base or None
    adapter: ModelListingProvider
    if pc.type == "anthropic":
        from .provider_anthropic import AnthropicProvider

        adapter = AnthropicProvider(api_key=resolved_key, timeout_seconds=pc.timeout_seconds, api_base=api_base)
    elif pc.type == "openai_compatible":
        from .provider_openai import OpenAICompatibleProvider

        adapter = OpenAICompatibleProvider(api_key=resolved_key, timeout_seconds=pc.timeout_seconds, api_base=api_base)
    else:
        raise ValueError(f"Unknown type {pc.type!r} for provider '{name}'. Valid types: anthropic, openai_compatible.")

    _adapter_cache[cache_key] = adapter
    return adapter


def _adapters_in_use() -> dict[str, ModelListingProvider]:
    ai = cfg().ai
    names = sorted({cluster.provider for cluster in ai.clusters.values()})
    return {name: provider_named(name) for name in names}


class RoutingProvider:
    def __init__(self, adapters: dict[str, ModelListingProvider]) -> None:
        self._adapters = adapters

    def create_message(self, spec: AICallSpec) -> AIResponse:
        return self._adapters[provider_for_role(spec.log_role)].create_message(spec)

    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse:
        return self._adapters[provider_for_role(spec.log_role)].stream_message(spec, on_text)


def get_provider() -> AIProvider:
    return RoutingProvider(_adapters_in_use())


def provider_named(name: str) -> ModelListingProvider:
    return _build_adapter(name, cfg().ai.providers[name])


def check_configured_models() -> None:
    ai = cfg().ai
    adapters = _adapters_in_use()
    available = {name: set(adapter.list_models()) for name, adapter in adapters.items()}
    missing = [
        (cluster_name, cluster.provider, cluster.model)
        for cluster_name, cluster in sorted(ai.clusters.items())
        if cluster.model not in available[cluster.provider]
    ]
    if missing:
        lines = [
            f"  cluster '{cluster_name}': model '{model}' is not offered by provider '{provider}'. "
            f"Available there: {', '.join(sorted(available[provider])) or 'none'}."
            for cluster_name, provider, model in missing
        ]
        raise RuntimeError(
            "Configured models are not available:\n" + "\n".join(lines) + "\nUpdate ai.clusters in config.yaml."
        )
