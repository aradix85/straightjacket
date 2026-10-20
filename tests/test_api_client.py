from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from straightjacket.engine import config_loader
from straightjacket.engine.ai import api_client
from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse


class _FakeAdapter:
    def __init__(self, name: str, models: list[str]) -> None:
        self.name = name
        self.models = models
        self.specs: list[AICallSpec] = []

    def create_message(self, spec: AICallSpec) -> AIResponse:
        self.specs.append(spec)
        return AIResponse(content=self.name)

    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse:
        return self.create_message(spec)

    def list_models(self) -> list[str]:
        return self.models


def _cluster(provider: str, model: str) -> dict[str, Any]:
    return {
        "provider": provider,
        "model": model,
        "temperature": 0.5,
        "top_p": 0.9,
        "max_tokens": 64,
        "max_retries": 0,
        "extra_body": {},
    }


@pytest.fixture
def two_providers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, _FakeAdapter]:
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
            "role_cluster": {
                "narrator": "narrator",
                "blueprint_voicing": "classification",
                "director": "classification",
                "recap": "classification",
                "brain": "classification",
                "correction": "classification",
                "narrator_metadata": "classification",
                "opening_setup": "classification",
            },
        },
    }
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.safe_dump(data), encoding="utf-8")
    monkeypatch.setattr(config_loader, "_CONFIG_PATH", config_file)
    monkeypatch.setattr(config_loader, "_cfg", None)
    adapters = {"fast": _FakeAdapter("fast", ["model-a"]), "prose": _FakeAdapter("prose", ["model-b"])}
    monkeypatch.setattr(api_client, "build_adapter", lambda name, pc: adapters[name])
    return adapters


def _spec(role: str, **fields: Any) -> AICallSpec:
    return AICallSpec(
        model="m",
        system="You are the Brain.",
        messages=[{"role": "user", "content": "hi"}],
        **{
            "max_tokens": 8,
            "max_retries": 0,
            "temperature": None,
            "top_p": None,
            "extra_body": {},
            "json_schema": None,
            "tools": None,
            "log_role": role,
            "cached_system_prefix": "",
            **fields,
        },
    )


def test_each_role_is_routed_to_its_clusters_provider(two_providers: dict[str, _FakeAdapter]) -> None:
    provider = api_client.get_provider()
    assert provider.create_message(_spec("narrator")).content == "prose"
    assert provider.create_message(_spec("brain")).content == "fast"
    assert [s.log_role for s in two_providers["prose"].specs] == ["narrator"]
    assert [s.log_role for s in two_providers["fast"].specs] == ["brain"]


def test_call_without_a_known_role_raises(two_providers: dict[str, _FakeAdapter]) -> None:
    with pytest.raises(KeyError):
        api_client.get_provider().create_message(_spec(""))


def test_a_call_with_a_schema_carries_the_schema_at_the_end_of_its_last_message(
    load_engine: None, two_providers: dict[str, _FakeAdapter]
) -> None:
    schema = {"type": "object", "required": ["move"], "properties": {"move": {"type": "string"}}}
    api_client.get_provider().create_message(_spec("brain", json_schema=schema))
    [sent] = two_providers["fast"].specs
    assert sent.system == "You are the Brain."
    assert sent.messages[-1]["content"].startswith("hi\n\n")
    assert sent.messages[-1]["content"].endswith(json.dumps(schema, separators=(",", ":")))
    assert sent.json_schema == schema


def test_a_call_without_a_schema_is_sent_unchanged(load_engine: None, two_providers: dict[str, _FakeAdapter]) -> None:
    provider = api_client.get_provider()
    provider.create_message(_spec("brain"))
    provider.stream_message(_spec("brain"), lambda text: None)
    specs = two_providers["fast"].specs
    assert [(s.system, s.messages[-1]["content"]) for s in specs] == [("You are the Brain.", "hi")] * 2


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
        api_client.build_adapter("somewhere", pc)


def test_unknown_provider_type_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SJ_TEST_KEY", "k")
    pc = config_loader.ProviderConfig(type="carrier_pigeon", api_base="", api_key_env="SJ_TEST_KEY", timeout_seconds=30)
    with pytest.raises(ValueError, match="Unknown type 'carrier_pigeon'"):
        api_client.build_adapter("somewhere", pc)
