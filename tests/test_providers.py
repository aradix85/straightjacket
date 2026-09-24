from __future__ import annotations

from types import SimpleNamespace
import inspect
from typing import Any

import pytest

from straightjacket.engine.ai import provider_anthropic, provider_openai
from straightjacket.engine.ai.provider_base import AICallSpec


class _FakeEndpoint:
    def __init__(self) -> None:
        self.response: Any = None
        self.calls: list[dict[str, Any]] = []
        self.init_args: dict[str, Any] = {}
        self.models: list[SimpleNamespace] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.response


def _spec(**overrides: Any) -> AICallSpec:
    base: dict[str, Any] = {
        "model": "test-model",
        "system": "system text",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 64,
    }
    base.update(overrides)
    return AICallSpec(**base)


def _tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "query_npc",
            "description": "Look up an NPC",
            "parameters": {"type": "object", "properties": {"npc_id": {"type": "string"}}},
        },
    }


@pytest.fixture
def anthropic_endpoint(monkeypatch: pytest.MonkeyPatch) -> _FakeEndpoint:
    endpoint = _FakeEndpoint()

    def fake_client(**kwargs: Any) -> SimpleNamespace:
        endpoint.init_args = kwargs
        return SimpleNamespace(messages=endpoint, models=SimpleNamespace(list=lambda: endpoint.models))

    monkeypatch.setattr(provider_anthropic.anthropic, "Anthropic", fake_client)
    return endpoint


@pytest.fixture
def openai_endpoint(monkeypatch: pytest.MonkeyPatch) -> _FakeEndpoint:
    endpoint = _FakeEndpoint()

    def fake_client(**kwargs: Any) -> SimpleNamespace:
        endpoint.init_args = kwargs
        return SimpleNamespace(
            chat=SimpleNamespace(completions=endpoint), models=SimpleNamespace(list=lambda: endpoint.models)
        )

    monkeypatch.setattr(provider_openai.openai, "OpenAI", fake_client)
    return endpoint


class TestAnthropicProvider:
    def test_maps_text_tool_use_stop_reason_and_usage(self, anthropic_endpoint: _FakeEndpoint) -> None:
        anthropic_endpoint.response = SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text="Hello "),
                SimpleNamespace(type="text", text="world"),
                SimpleNamespace(type="tool_use", id="t1", name="query_npc", input={"npc_id": "npc_1"}),
            ],
            stop_reason="tool_use",
            usage=SimpleNamespace(input_tokens=11, output_tokens=7),
        )
        result = provider_anthropic.AnthropicProvider(api_key="k").create_message(_spec())
        assert result.content == "Hello world"
        assert result.tool_calls == [{"id": "t1", "name": "query_npc", "arguments": {"npc_id": "npc_1"}}]
        assert result.stop_reason == "tool_use"
        assert result.usage == {"input_tokens": 11, "output_tokens": 7}

    def test_request_carries_system_sampling_schema_and_converted_tools(
        self, anthropic_endpoint: _FakeEndpoint
    ) -> None:
        anthropic_endpoint.response = SimpleNamespace(content=[], stop_reason="end_turn")
        schema = {"title": "brain_output", "type": "object"}
        spec = _spec(temperature=0.5, top_p=0.9, top_k=40, json_schema=schema, tools=[_tool()])
        provider_anthropic.AnthropicProvider(api_key="k").create_message(spec)
        sent = anthropic_endpoint.calls[0]
        assert sent["system"] == "system text"
        assert sent["messages"] == [{"role": "user", "content": "hello"}]
        assert sent["extra_body"] == {"temperature": 0.5, "top_p": 0.9, "top_k": 40}
        assert not {"temperature", "top_p", "top_k"} & set(sent)
        assert sent["output_config"] == {"format": {"type": "json_schema", "schema": schema}}
        assert sent["tools"] == [
            {
                "name": "query_npc",
                "description": "Look up an NPC",
                "input_schema": {"type": "object", "properties": {"npc_id": {"type": "string"}}},
            }
        ]

    def test_unset_options_are_not_sent(self, anthropic_endpoint: _FakeEndpoint) -> None:
        anthropic_endpoint.response = SimpleNamespace(content=[], stop_reason="end_turn")
        provider_anthropic.AnthropicProvider(api_key="k").create_message(_spec())
        assert set(anthropic_endpoint.calls[0]) == {"model", "max_tokens", "system", "messages"}

    def test_max_tokens_is_truncated_and_missing_usage_is_none(self, anthropic_endpoint: _FakeEndpoint) -> None:
        anthropic_endpoint.response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="cut")], stop_reason="max_tokens"
        )
        result = provider_anthropic.AnthropicProvider(api_key="k").create_message(_spec())
        assert result.stop_reason == "truncated"
        assert result.usage is None
        assert result.tool_calls == []

    def test_base_url_only_when_configured(self, anthropic_endpoint: _FakeEndpoint) -> None:
        provider_anthropic.AnthropicProvider(api_key="k")
        assert anthropic_endpoint.init_args == {"api_key": "k"}
        provider_anthropic.AnthropicProvider(api_key="k", api_base="http://localhost:9")
        assert anthropic_endpoint.init_args == {"api_key": "k", "base_url": "http://localhost:9"}


def _openai_response(content: str | None, finish_reason: str, tool_calls: list | None) -> SimpleNamespace:
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
        usage=SimpleNamespace(prompt_tokens=20, completion_tokens=5),
    )


class TestOpenAICompatibleProvider:
    def test_maps_content_tool_calls_stop_reason_and_usage(self, openai_endpoint: _FakeEndpoint) -> None:
        call = SimpleNamespace(id="c1", function=SimpleNamespace(name="query_npc", arguments='{"npc_id": "npc_2"}'))
        openai_endpoint.response = _openai_response("Narration", "tool_calls", [call])
        result = provider_openai.OpenAICompatibleProvider(api_key="k").create_message(_spec())
        assert result.content == "Narration"
        assert result.tool_calls == [{"id": "c1", "name": "query_npc", "arguments": {"npc_id": "npc_2"}}]
        assert result.stop_reason == "tool_use"
        assert result.usage == {"input_tokens": 20, "output_tokens": 5}

    def test_request_prepends_system_and_builds_schema_format(self, openai_endpoint: _FakeEndpoint) -> None:
        openai_endpoint.response = _openai_response("{}", "stop", None)
        schema = {"title": "brain_output", "type": "object"}
        spec = _spec(temperature=0.7, top_p=0.95, json_schema=schema, tools=[_tool()])
        provider_openai.OpenAICompatibleProvider(api_key="k").create_message(spec)
        sent = openai_endpoint.calls[0]
        assert sent["messages"] == [
            {"role": "system", "content": "system text"},
            {"role": "user", "content": "hello"},
        ]
        assert (sent["temperature"], sent["top_p"]) == (0.7, 0.95)
        assert sent["response_format"] == {
            "type": "json_schema",
            "json_schema": {"name": "brain_output", "strict": True, "schema": schema},
        }
        assert sent["tools"] == [_tool()]

    def test_top_k_merges_into_extra_body_without_mutating_spec(self, openai_endpoint: _FakeEndpoint) -> None:
        openai_endpoint.response = _openai_response("ok", "stop", None)
        extra = {"reasoning_effort": "none"}
        provider_openai.OpenAICompatibleProvider(api_key="k").create_message(_spec(extra_body=extra, top_k=30))
        assert openai_endpoint.calls[0]["extra_body"] == {"reasoning_effort": "none", "top_k": 30}
        assert extra == {"reasoning_effort": "none"}

    def test_unset_options_are_not_sent(self, openai_endpoint: _FakeEndpoint) -> None:
        openai_endpoint.response = _openai_response("ok", "stop", None)
        provider_openai.OpenAICompatibleProvider(api_key="k").create_message(_spec())
        assert set(openai_endpoint.calls[0]) == {"model", "max_tokens", "messages"}

    def test_length_is_truncated_and_empty_content_is_empty_string(self, openai_endpoint: _FakeEndpoint) -> None:
        openai_endpoint.response = _openai_response(None, "length", None)
        result = provider_openai.OpenAICompatibleProvider(api_key="k").create_message(_spec())
        assert result.stop_reason == "truncated"
        assert result.content == ""
        assert result.tool_calls == []

    def test_base_url_only_when_configured(self, openai_endpoint: _FakeEndpoint) -> None:
        provider_openai.OpenAICompatibleProvider(api_key="k")
        assert openai_endpoint.init_args == {"api_key": "k"}
        provider_openai.OpenAICompatibleProvider(api_key="k", api_base="http://localhost:9/v1")
        assert openai_endpoint.init_args == {"api_key": "k", "base_url": "http://localhost:9/v1"}


def _accepted(create: Any) -> set[str]:
    return set(inspect.signature(create).parameters)


def test_anthropic_request_uses_only_parameters_the_installed_sdk_accepts(anthropic_endpoint: _FakeEndpoint) -> None:
    anthropic_endpoint.response = SimpleNamespace(content=[], stop_reason="end_turn")
    spec = _spec(temperature=0.5, top_p=0.9, top_k=40, json_schema={"title": "t", "type": "object"}, tools=[_tool()])
    provider_anthropic.AnthropicProvider(api_key="k").create_message(spec)
    accepted = _accepted(provider_anthropic.anthropic.resources.messages.Messages.create)
    assert set(anthropic_endpoint.calls[0]) <= accepted


def test_openai_request_uses_only_parameters_the_installed_sdk_accepts(openai_endpoint: _FakeEndpoint) -> None:
    openai_endpoint.response = _openai_response("ok", "stop", None)
    spec = _spec(
        temperature=0.5,
        top_p=0.9,
        top_k=40,
        extra_body={"reasoning_effort": "none"},
        json_schema={"title": "t", "type": "object"},
        tools=[_tool()],
    )
    provider_openai.OpenAICompatibleProvider(api_key="k").create_message(spec)
    accepted = _accepted(provider_openai.openai.resources.chat.completions.Completions.create)
    assert set(openai_endpoint.calls[0]) <= accepted


def test_anthropic_list_models_returns_ids(anthropic_endpoint: _FakeEndpoint) -> None:
    anthropic_endpoint.models = [SimpleNamespace(id="model-a"), SimpleNamespace(id="model-b")]
    assert provider_anthropic.AnthropicProvider(api_key="k").list_models() == ["model-a", "model-b"]


def test_openai_list_models_returns_ids(openai_endpoint: _FakeEndpoint) -> None:
    openai_endpoint.models = [SimpleNamespace(id="model-c")]
    assert provider_openai.OpenAICompatibleProvider(api_key="k").list_models() == ["model-c"]
