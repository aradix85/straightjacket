from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import Any, Self

import anthropic
import openai
import pytest
from anthropic.resources.messages import Messages
from openai.resources.chat.completions import Completions
from openai.types.chat import ChatCompletionMessageCustomToolCall, ChatCompletionMessageFunctionToolCall
from openai.types.chat.chat_completion_message_custom_tool_call import Custom
from openai.types.chat.chat_completion_message_function_tool_call import Function

from straightjacket.engine.ai import provider_anthropic, provider_openai
from straightjacket.engine.ai.provider_base import AIUnavailableError, ToolCall, create_with_retry
from straightjacket.engine.tools import ToolDefinition
from tests._helpers import make_ai_call_spec


class _FakeEndpoint:
    def __init__(self) -> None:
        self.response: Any = None
        self.calls: list[dict[str, Any]] = []
        self.init_args: dict[str, Any] = {}
        self.models: list[SimpleNamespace] = []
        self.listing: Any = None
        self.listing_paths: list[str] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.response

    def stream(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.response


def _anthropic_usage(input_tokens: int = 5, output_tokens: int = 7, **cache: int) -> SimpleNamespace:
    fields: dict[str, Any] = {"cache_read_input_tokens": None, "cache_creation_input_tokens": None, **cache}
    return SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens, **fields)


def _openai_usage(prompt_tokens: int, completion_tokens: int, **extra: Any) -> SimpleNamespace:
    fields: dict[str, Any] = {"prompt_tokens_details": None, "completion_tokens_details": None, **extra}
    return SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, **fields)


def _tool() -> ToolDefinition:
    return ToolDefinition(
        name="query_npc",
        description="Look up an NPC",
        parameters={"type": "object", "properties": {"npc_id": {"type": "string"}}},
    )


def _anthropic() -> provider_anthropic.AnthropicProvider:
    return provider_anthropic.AnthropicProvider(api_key="k", timeout_seconds=30, api_base="")


def _openai() -> provider_openai.OpenAICompatibleProvider:
    return provider_openai.OpenAICompatibleProvider(api_key="k", timeout_seconds=30, api_base="")


@pytest.fixture(name="anthropic_endpoint")
def fixture_anthropic_endpoint(monkeypatch: pytest.MonkeyPatch) -> _FakeEndpoint:
    endpoint = _FakeEndpoint()

    def fake_client(**kwargs: Any) -> SimpleNamespace:
        endpoint.init_args = kwargs
        return SimpleNamespace(messages=endpoint, models=SimpleNamespace(list=lambda: endpoint.models))

    monkeypatch.setattr(anthropic, "Anthropic", fake_client)
    return endpoint


@pytest.fixture(name="openai_endpoint")
def fixture_openai_endpoint(monkeypatch: pytest.MonkeyPatch) -> _FakeEndpoint:
    endpoint = _FakeEndpoint()

    def fake_client(**kwargs: Any) -> SimpleNamespace:
        endpoint.init_args = kwargs

        def get(path: str, **_kwargs: object) -> Any:
            endpoint.listing_paths.append(path)
            return endpoint.listing

        return SimpleNamespace(chat=SimpleNamespace(completions=endpoint), get=get)

    monkeypatch.setattr(openai, "OpenAI", fake_client)
    return endpoint


class TestAnthropicProvider:
    @staticmethod
    def test_maps_text_tool_use_stop_reason_and_usage(anthropic_endpoint: _FakeEndpoint) -> None:
        anthropic_endpoint.response = SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text="Hello "),
                SimpleNamespace(type="text", text="world"),
                SimpleNamespace(type="tool_use", id="t1", name="query_npc", input={"npc_id": "npc_1"}),
            ],
            stop_reason="tool_use",
            usage=_anthropic_usage(11, 7),
        )
        result = _anthropic().create_message(make_ai_call_spec())
        assert result.content == "Hello world"
        assert result.tool_calls == [ToolCall(name="query_npc", arguments={"npc_id": "npc_1"})]
        assert result.stop_reason == "tool_use"
        assert result.usage == {"input_tokens": 11, "output_tokens": 7, "cache_read_tokens": 0}

    @staticmethod
    def test_request_carries_system_sampling_schema_and_converted_tools(anthropic_endpoint: _FakeEndpoint) -> None:
        anthropic_endpoint.response = _anthropic_reply()
        schema = {"title": "brain_output", "type": "object"}
        spec = make_ai_call_spec(temperature=0.5, top_p=0.9, json_schema=schema, tools=[_tool()])
        _anthropic().create_message(spec)
        sent = anthropic_endpoint.calls[0]
        assert sent["system"] == "system text"
        assert sent["messages"] == [{"role": "user", "content": "hello"}]
        assert sent["extra_body"] == {"temperature": 0.5, "top_p": 0.9}
        assert not {"temperature", "top_p"} & set(sent)
        assert sent["output_config"] == {
            "format": {"type": "json_schema", "schema": anthropic.transform_schema(schema)}
        }
        assert sent["tools"] == [
            {
                "name": "query_npc",
                "description": "Look up an NPC",
                "input_schema": {"type": "object", "properties": {"npc_id": {"type": "string"}}},
            }
        ]

    @staticmethod
    def test_unset_options_are_not_sent(anthropic_endpoint: _FakeEndpoint) -> None:
        anthropic_endpoint.response = _anthropic_reply()
        _anthropic().create_message(make_ai_call_spec())
        assert set(anthropic_endpoint.calls[0]) == {"model", "max_tokens", "system", "messages"}

    @staticmethod
    def test_max_tokens_is_truncated(anthropic_endpoint: _FakeEndpoint) -> None:
        anthropic_endpoint.response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="cut")], stop_reason="max_tokens", usage=_anthropic_usage()
        )
        result = _anthropic().create_message(make_ai_call_spec())
        assert result.stop_reason == "truncated"
        assert not result.tool_calls

    @staticmethod
    def test_base_url_only_when_configured(anthropic_endpoint: _FakeEndpoint) -> None:
        _anthropic()
        assert anthropic_endpoint.init_args == {"api_key": "k", "max_retries": 0, "timeout": 30}
        provider_anthropic.AnthropicProvider(api_key="k", timeout_seconds=30, api_base="http://localhost:9")
        assert anthropic_endpoint.init_args == {
            "api_key": "k",
            "max_retries": 0,
            "timeout": 30,
            "base_url": "http://localhost:9",
        }


def _function_call(arguments: str) -> ChatCompletionMessageFunctionToolCall:
    return ChatCompletionMessageFunctionToolCall(
        id="c1", type="function", function=Function(name="query_npc", arguments=arguments)
    )


def _openai_response(
    content: str | None,
    finish_reason: str,
    tool_calls: list[ChatCompletionMessageCustomToolCall | ChatCompletionMessageFunctionToolCall] | None,
) -> SimpleNamespace:
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
        usage=_openai_usage(20, 5),
    )


class TestOpenAICompatibleProvider:
    @staticmethod
    def test_maps_content_tool_calls_stop_reason_and_usage(openai_endpoint: _FakeEndpoint) -> None:
        openai_endpoint.response = _openai_response("Narration", "tool_calls", [_function_call('{"npc_id": "npc_2"}')])
        result = _openai().create_message(make_ai_call_spec())
        assert result.content == "Narration"
        assert result.tool_calls == [ToolCall(name="query_npc", arguments={"npc_id": "npc_2"})]
        assert result.stop_reason == "tool_use"
        assert result.usage == {"input_tokens": 20, "output_tokens": 5}

    @staticmethod
    @pytest.mark.parametrize("arguments", ['["npc_2"]', "null", '"npc_2"'])
    def test_tool_arguments_that_are_no_json_object_are_refused(openai_endpoint: _FakeEndpoint, arguments: str) -> None:
        openai_endpoint.response = _openai_response("", "tool_calls", [_function_call(arguments)])
        with pytest.raises(ValueError, match="query_npc: expected dict"):
            _openai().create_message(make_ai_call_spec())

    @staticmethod
    def test_a_tool_call_that_calls_no_function_is_refused(openai_endpoint: _FakeEndpoint) -> None:
        custom = ChatCompletionMessageCustomToolCall(id="c2", type="custom", custom=Custom(name="note", input="x"))
        openai_endpoint.response = _openai_response("", "tool_calls", [_function_call("{}"), custom])
        with pytest.raises(ValueError, match="tool call: expected a function call, got ChatCompletionMessageCustom"):
            _openai().create_message(make_ai_call_spec())

    @staticmethod
    def test_request_prepends_system_and_builds_schema_format(openai_endpoint: _FakeEndpoint) -> None:
        openai_endpoint.response = _openai_response("{}", "stop", None)
        schema = {"title": "brain_output", "type": "object"}
        spec = make_ai_call_spec(temperature=0.7, top_p=0.95, json_schema=schema, tools=[_tool()])
        _openai().create_message(spec)
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
        assert sent["tools"] == [
            {
                "type": "function",
                "function": {
                    "name": "query_npc",
                    "description": "Look up an NPC",
                    "parameters": {"type": "object", "properties": {"npc_id": {"type": "string"}}},
                },
            }
        ]

    @staticmethod
    def test_the_clusters_extra_body_reaches_the_request(openai_endpoint: _FakeEndpoint) -> None:
        openai_endpoint.response = _openai_response("ok", "stop", None)
        _openai().create_message(make_ai_call_spec(extra_body={"reasoning_effort": "none"}))
        assert openai_endpoint.calls[0]["extra_body"] == {"reasoning_effort": "none"}

    @staticmethod
    def test_unset_options_are_not_sent(openai_endpoint: _FakeEndpoint) -> None:
        openai_endpoint.response = _openai_response("ok", "stop", None)
        _openai().create_message(make_ai_call_spec())
        assert set(openai_endpoint.calls[0]) == {"model", "max_completion_tokens", "messages"}

    @staticmethod
    def test_length_is_truncated_and_empty_content_is_empty_string(openai_endpoint: _FakeEndpoint) -> None:
        openai_endpoint.response = _openai_response(None, "length", None)
        result = _openai().create_message(make_ai_call_spec())
        assert result.stop_reason == "truncated"
        assert not result.content
        assert not result.tool_calls

    @staticmethod
    def test_base_url_only_when_configured(openai_endpoint: _FakeEndpoint) -> None:
        _openai()
        assert openai_endpoint.init_args == {"api_key": "k", "max_retries": 0, "timeout": 30}
        provider_openai.OpenAICompatibleProvider(api_key="k", timeout_seconds=30, api_base="http://localhost:9/v1")
        assert openai_endpoint.init_args == {
            "api_key": "k",
            "max_retries": 0,
            "timeout": 30,
            "base_url": "http://localhost:9/v1",
        }


def _accepted(create: Any) -> set[str]:
    return set(inspect.signature(create).parameters)


def test_anthropic_request_uses_only_parameters_the_installed_sdk_accepts(anthropic_endpoint: _FakeEndpoint) -> None:
    anthropic_endpoint.response = _anthropic_reply()
    spec = make_ai_call_spec(temperature=0.5, top_p=0.9, json_schema={"title": "t", "type": "object"}, tools=[_tool()])
    _anthropic().create_message(spec)
    accepted = _accepted(Messages.create)
    assert set(anthropic_endpoint.calls[0]) <= accepted


def test_openai_request_uses_only_parameters_the_installed_sdk_accepts(openai_endpoint: _FakeEndpoint) -> None:
    openai_endpoint.response = _openai_response("ok", "stop", None)
    spec = make_ai_call_spec(
        temperature=0.5,
        top_p=0.9,
        extra_body={"reasoning_effort": "none"},
        json_schema={"title": "t", "type": "object"},
        tools=[_tool()],
    )
    _openai().create_message(spec)
    accepted = _accepted(Completions.create)
    assert set(openai_endpoint.calls[0]) <= accepted


def test_anthropic_list_models_returns_ids(anthropic_endpoint: _FakeEndpoint) -> None:
    anthropic_endpoint.models = [SimpleNamespace(id="model-a"), SimpleNamespace(id="model-b")]
    assert _anthropic().list_models() == [
        "model-a",
        "model-b",
    ]


def test_openai_list_models_reads_the_openai_listing(openai_endpoint: _FakeEndpoint) -> None:
    openai_endpoint.listing = {"object": "list", "data": [{"id": "model-c"}, {"id": "model-d"}]}
    provider = _openai()
    assert provider.list_models() == ["model-c", "model-d"]
    assert openai_endpoint.listing_paths == ["/models"]


def test_openai_list_models_reads_a_bare_list_as_together_returns_it(openai_endpoint: _FakeEndpoint) -> None:
    openai_endpoint.listing = [{"id": "vendor-org/model-t", "type": "chat"}]
    provider = _openai()
    assert provider.list_models() == ["vendor-org/model-t"]


def test_openai_list_models_refuses_an_unknown_listing(openai_endpoint: _FakeEndpoint) -> None:
    openai_endpoint.listing = "not a listing"
    with pytest.raises(TypeError, match="Unexpected model listing"):
        _openai().list_models()


def _anthropic_reply(*blocks: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(content=list(blocks), stop_reason="end_turn", usage=_anthropic_usage())


def test_anthropic_thinking_blocks_never_reach_the_content(anthropic_endpoint: _FakeEndpoint) -> None:
    anthropic_endpoint.response = _anthropic_reply(
        SimpleNamespace(type="thinking", thinking="plan the scene", signature="sig"),
        SimpleNamespace(type="redacted_thinking", data="opaque"),
        SimpleNamespace(type="text", text="The door holds."),
    )
    result = _anthropic().create_message(make_ai_call_spec())
    assert result.content == "The door holds."


def test_anthropic_passes_cluster_extra_body_to_the_right_parameters(anthropic_endpoint: _FakeEndpoint) -> None:
    anthropic_endpoint.response = _anthropic_reply(SimpleNamespace(type="text", text="{}"))
    extra = {
        "output_config": {"effort": "low"},
        "cache_control": {"type": "ephemeral"},
        "thinking": {"type": "enabled", "budget_tokens": 2048},
        "metadata_flag": True,
    }
    sent_as_written = {key: dict(value) if isinstance(value, dict) else value for key, value in extra.items()}
    spec = make_ai_call_spec(json_schema={"title": "t", "type": "object"}, extra_body=extra, temperature=0.5)
    _anthropic().create_message(spec)
    sent = anthropic_endpoint.calls[0]
    assert sent["output_config"] == {
        "effort": "low",
        "format": {
            "type": "json_schema",
            "schema": anthropic.transform_schema({"title": "t", "type": "object"}),
        },
    }
    assert "cache_control" not in sent
    assert sent["system"] == [{"type": "text", "text": "system text", "cache_control": {"type": "ephemeral"}}]
    assert sent["thinking"] == {"type": "enabled", "budget_tokens": 2048}
    assert sent["extra_body"] == {"temperature": 0.5, "metadata_flag": True}
    assert extra == sent_as_written


def test_anthropic_caches_the_stable_start_of_the_system_prompt(anthropic_endpoint: _FakeEndpoint) -> None:
    anthropic_endpoint.response = _anthropic_reply(SimpleNamespace(type="text", text="ok"))
    cache = {"type": "ephemeral", "ttl": "1h"}
    spec = make_ai_call_spec(
        system="fixed rules\nstate: wounded", cached_system_prefix="fixed rules\n", extra_body={"cache_control": cache}
    )
    _anthropic().create_message(spec)
    sent = anthropic_endpoint.calls[0]
    assert sent["system"] == [
        {"type": "text", "text": "fixed rules\n", "cache_control": cache},
        {"type": "text", "text": "state: wounded"},
    ]
    assert "cache_control" not in sent


def test_anthropic_caches_the_whole_system_prompt_without_a_prefix(anthropic_endpoint: _FakeEndpoint) -> None:
    anthropic_endpoint.response = _anthropic_reply(SimpleNamespace(type="text", text="ok"))
    cache = {"type": "ephemeral"}
    spec = make_ai_call_spec(extra_body={"cache_control": cache})
    _anthropic().create_message(spec)
    assert anthropic_endpoint.calls[0]["system"] == [{"type": "text", "text": "system text", "cache_control": cache}]


def test_anthropic_refuses_a_cache_prefix_that_is_not_the_start_of_the_system(
    anthropic_endpoint: _FakeEndpoint,
) -> None:
    anthropic_endpoint.response = _anthropic_reply(SimpleNamespace(type="text", text="ok"))
    spec = make_ai_call_spec(cached_system_prefix="other text", extra_body={"cache_control": {"type": "ephemeral"}})
    with pytest.raises(ValueError, match="cached_system_prefix"):
        _anthropic().create_message(spec)


@pytest.mark.parametrize(
    ("extra_body", "named"),
    [
        ({"output_config": {"effort": "medium", "efort": "low"}}, r"extra_body\.output_config: efort: Extra inputs"),
        ({"output_config": {"effort": "utmost"}}, r"extra_body\.output_config: effort: Input should be 'low'"),
        ({"output_config": "medium"}, r"extra_body\.output_config: : Input should be a valid dict"),
        ({"output_config": None}, r"extra_body\.output_config: : Input should be a valid dict"),
        ({"cache_control": {"ttl": "1h"}}, r"extra_body\.cache_control: type: Field required"),
        ({"cache_control": None}, r"extra_body\.cache_control: : Input should be a valid dict"),
        ({"cache_control": {"type": "ephemeral", "ttl": "1d"}}, r"extra_body\.cache_control: ttl: Input should be"),
        ({"thinking": {"type": "sometimes"}}, r"extra_body\.thinking: .*type: Input should be 'adaptive'"),
        ({"thinking": {"type": "enabled"}}, r"extra_body\.thinking: .*budget_tokens: Field required"),
        ({"thinking": {"type": "enabled", "budget_tokens": "2048"}}, r"budget_tokens: Input should be a valid integer"),
    ],
)
def test_anthropic_refuses_a_routed_extra_body_value_the_sdk_does_not_know(
    anthropic_endpoint: _FakeEndpoint, extra_body: dict[str, object], named: str
) -> None:
    with pytest.raises(ValueError, match=named):
        _anthropic().create_message(make_ai_call_spec(extra_body=extra_body))
    assert not anthropic_endpoint.calls


def test_a_refused_extra_body_fails_the_call_without_asking_again(anthropic_endpoint: _FakeEndpoint) -> None:
    spec = make_ai_call_spec(extra_body={"output_config": {"efort": "low"}}, max_retries=2)
    with pytest.raises(AIUnavailableError, match=r"narrator: ValueError: extra_body\.output_config: efort"):
        create_with_retry(_anthropic(), spec)
    assert not anthropic_endpoint.calls


def test_anthropic_sends_the_system_prompt_as_text_without_caching(anthropic_endpoint: _FakeEndpoint) -> None:
    anthropic_endpoint.response = _anthropic_reply(SimpleNamespace(type="text", text="ok"))
    _anthropic().create_message(make_ai_call_spec(cached_system_prefix="sys"))
    assert anthropic_endpoint.calls[0]["system"] == "system text"


def test_anthropic_moves_array_limits_it_cannot_enforce_into_the_description(anthropic_endpoint: _FakeEndpoint) -> None:
    anthropic_endpoint.response = _anthropic_reply(SimpleNamespace(type="text", text="{}"))
    boasts = {"type": "array", "items": {"type": "string", "enum": ["a", "b"]}, "maxItems": 2}
    schema = {"type": "object", "properties": {"boasts": boasts}, "required": ["boasts"], "additionalProperties": False}
    _anthropic().create_message(make_ai_call_spec(json_schema=schema))
    sent_boasts = anthropic_endpoint.calls[0]["output_config"]["format"]["schema"]["properties"]["boasts"]
    assert "maxItems" not in sent_boasts
    assert "maxItems: 2" in sent_boasts["description"]
    assert boasts["maxItems"] == 2


def test_anthropic_usage_counts_cached_input_and_reports_the_cached_share(anthropic_endpoint: _FakeEndpoint) -> None:
    anthropic_endpoint.response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="ok")],
        stop_reason="end_turn",
        usage=_anthropic_usage(4, 9, cache_read_input_tokens=3970, cache_creation_input_tokens=0),
    )
    result = _anthropic().create_message(make_ai_call_spec())
    assert result.usage == {"input_tokens": 3974, "output_tokens": 9, "cache_read_tokens": 3970}


class _FakeAnthropicStream:
    def __init__(self, events: list[SimpleNamespace], final: SimpleNamespace) -> None:
        self.events = events
        self.final = final

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def __iter__(self) -> Any:
        return iter(self.events)

    def get_final_message(self) -> SimpleNamespace:
        return self.final


def _delta(kind: str, **fields: str) -> SimpleNamespace:
    return SimpleNamespace(type="content_block_delta", delta=SimpleNamespace(type=kind, **fields))


def test_anthropic_stream_passes_only_text_deltas(anthropic_endpoint: _FakeEndpoint) -> None:
    final = _anthropic_reply(
        SimpleNamespace(type="thinking", thinking="plan"), SimpleNamespace(type="text", text="The door holds.")
    )
    events = [
        _delta("thinking_delta", thinking="plan"),
        _delta("text_delta", text="The door "),
        _delta("text_delta", text="holds."),
    ]
    anthropic_endpoint.response = _FakeAnthropicStream(events, final)
    received: list[str] = []
    result = _anthropic().stream_message(make_ai_call_spec(), received.append)
    assert received == ["The door ", "holds."]
    assert result.content == "The door holds."
    accepted = _accepted(Messages.stream)
    assert set(anthropic_endpoint.calls[0]) <= accepted


def test_openai_stream_collects_text_finish_reason_and_usage(openai_endpoint: _FakeEndpoint) -> None:
    def chunk(text: str | None, finish: str | None = None) -> SimpleNamespace:
        return SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content=text), finish_reason=finish)], usage=None
        )

    usage_chunk = SimpleNamespace(choices=[], usage=_openai_usage(3, 2))
    openai_endpoint.response = iter([chunk("Rain "), chunk(None), chunk("falls.", "stop"), usage_chunk])
    received: list[str] = []
    result = _openai().stream_message(make_ai_call_spec(), received.append)
    assert received == ["Rain ", "falls."]
    assert result.content == "Rain falls."
    assert result.usage == {"input_tokens": 3, "output_tokens": 2}
    assert openai_endpoint.calls[0]["stream"] is True
    assert openai_endpoint.calls[0]["stream_options"] == {"include_usage": True}
    assert set(openai_endpoint.calls[0]) <= _accepted(Completions.create)


def test_openai_usage_reports_cached_prompt_tokens(openai_endpoint: _FakeEndpoint) -> None:
    response = _openai_response("Narration", "stop", None)
    response.usage = _openai_usage(2000, 300, prompt_tokens_details=SimpleNamespace(cached_tokens=1500))
    openai_endpoint.response = response
    result = _openai().create_message(make_ai_call_spec())
    assert result.usage == {"input_tokens": 2000, "output_tokens": 300, "cache_read_tokens": 1500}


def test_openai_usage_reports_reasoning_tokens_nested_or_top_level(openai_endpoint: _FakeEndpoint) -> None:
    provider = _openai()
    nested = _openai_response("{}", "length", None)
    nested.usage = _openai_usage(10, 8192, completion_tokens_details=SimpleNamespace(reasoning_tokens=7800))
    openai_endpoint.response = nested
    assert provider.create_message(make_ai_call_spec()).usage == {
        "input_tokens": 10,
        "output_tokens": 8192,
        "reasoning_tokens": 7800,
    }
    top_level = _openai_response("{}", "stop", None)
    top_level.usage = _openai_usage(10, 600, reasoning_tokens=40)
    openai_endpoint.response = top_level
    assert provider.create_message(make_ai_call_spec()).usage == {
        "input_tokens": 10,
        "output_tokens": 600,
        "reasoning_tokens": 40,
    }


def test_openai_response_keeps_the_reasoning_text_under_either_name(openai_endpoint: _FakeEndpoint) -> None:
    provider = _openai()
    together_style = _openai_response("{}", "stop", None)
    together_style.choices[0].message.reasoning = "First, the NPC."
    openai_endpoint.response = together_style
    assert provider.create_message(make_ai_call_spec()).reasoning == "First, the NPC."
    other_style = _openai_response("{}", "stop", None)
    other_style.choices[0].message.reasoning_content = "Then the clock."
    openai_endpoint.response = other_style
    assert provider.create_message(make_ai_call_spec()).reasoning == "Then the clock."
    openai_endpoint.response = _openai_response("{}", "stop", None)
    assert not provider.create_message(make_ai_call_spec()).reasoning


def test_anthropic_refusal_is_reported_as_refusal(anthropic_endpoint: _FakeEndpoint) -> None:
    anthropic_endpoint.response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="")],
        stop_reason="refusal",
        usage=_anthropic_usage(1, 1),
    )
    assert _anthropic().create_message(make_ai_call_spec()).stop_reason == "refusal"


def test_openai_content_filter_is_reported_as_refusal(openai_endpoint: _FakeEndpoint) -> None:
    openai_endpoint.response = _openai_response("", "content_filter", None)
    assert _openai().create_message(make_ai_call_spec()).stop_reason == "refusal"
