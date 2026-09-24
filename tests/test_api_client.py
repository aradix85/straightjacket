from __future__ import annotations

from typing import Any

import pytest

from straightjacket.engine import config_loader
from straightjacket.engine.ai import api_client
from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse


class _FakeAdapter:
    def __init__(self, name: str, models: list[str]) -> None:
        self.name = name
        self.models = models
        self.roles: list[str] = []

    def create_message(self, spec: AICallSpec) -> AIResponse:
        self.roles.append(spec.log_role)
        return AIResponse(content=self.name)

    def list_models(self) -> list[str]:
        return self.models


def _cluster(provider: str, model: str) -> dict[str, Any]:
    return {"provider": provider, "model": model, "temperature": 0.5, "top_p": 0.9, "max_tokens": 64, "max_retries": 0}


@pytest.fixture
def two_providers(monkeypatch: pytest.MonkeyPatch) -> dict[str, _FakeAdapter]:
    data = {
        "server": {"host": "127.0.0.1", "port": 8081, "stream_narration": True},
        "language": {"narration_language": "English"},
        "ai": {
            "prompts_dir": "prompts",
            "providers": {
                "fast": {
                    "type": "openai_compatible",
                    "api_base": "http://fast.invalid/v1",
                    "api_key_env": "FAST_KEY",
                    "timeout_seconds": 30,
                },
                "prose": {"type": "anthropic", "api_base": "", "api_key_env": "PROSE_KEY", "timeout_seconds": 30},
            },
            "clusters": {"narrator": _cluster("prose", "model-b"), "classification": _cluster("fast", "model-a")},
            "role_cluster": {"narrator": "narrator", "brain": "classification"},
        },
    }
    monkeypatch.setattr(config_loader, "_cfg", config_loader._parse_config(data))
    adapters = {"fast": _FakeAdapter("fast", ["model-a"]), "prose": _FakeAdapter("prose", ["model-b"])}
    monkeypatch.setattr(api_client, "_build_adapter", lambda name, pc: adapters[name])
    return adapters


def _spec(role: str) -> AICallSpec:
    return AICallSpec(model="m", system="s", messages=[], max_tokens=8, log_role=role)


def test_each_role_is_routed_to_its_clusters_provider(two_providers: dict[str, _FakeAdapter]) -> None:
    provider = api_client.get_provider()
    assert provider.create_message(_spec("narrator")).content == "prose"
    assert provider.create_message(_spec("brain")).content == "fast"
    assert two_providers["prose"].roles == ["narrator"]
    assert two_providers["fast"].roles == ["brain"]


def test_call_without_a_known_role_raises(two_providers: dict[str, _FakeAdapter]) -> None:
    with pytest.raises(ValueError, match="no cluster assignment"):
        api_client.get_provider().create_message(_spec(""))


def test_startup_check_passes_when_every_model_is_offered(two_providers: dict[str, _FakeAdapter]) -> None:
    api_client.check_configured_models()


def test_startup_check_names_the_missing_model_and_what_is_available(two_providers: dict[str, _FakeAdapter]) -> None:
    two_providers["prose"].models = ["model-c"]
    with pytest.raises(
        RuntimeError, match="cluster 'narrator': model 'model-b' is not offered by provider 'prose'"
    ) as err:
        api_client.check_configured_models()
    assert "model-c" in str(err.value)


def test_missing_api_key_names_the_environment_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SJ_TEST_MISSING_KEY", raising=False)
    pc = config_loader.ProviderConfig(
        type="openai_compatible", api_base="", api_key_env="SJ_TEST_MISSING_KEY", timeout_seconds=30
    )
    with pytest.raises(ValueError, match="SJ_TEST_MISSING_KEY"):
        api_client._build_adapter("somewhere", pc)


def test_unknown_provider_type_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SJ_TEST_KEY", "k")
    pc = config_loader.ProviderConfig(type="carrier_pigeon", api_base="", api_key_env="SJ_TEST_KEY", timeout_seconds=30)
    with pytest.raises(ValueError, match="Unknown type 'carrier_pigeon'"):
        api_client._build_adapter("somewhere", pc)
