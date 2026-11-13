from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, TypeVar

import anthropic
from anthropic.types import CacheControlEphemeralParam, OutputConfigParam, ThinkingConfigParam
from anthropic.types.message_create_params import MessageCreateParamsBase
from pydantic import TypeAdapter, ValidationError

from straightjacket.engine.ai.provider_base import AIResponse, ToolCall, normalize_stop_reason
from straightjacket.engine.logging_util import log

if TYPE_CHECKING:
    from collections.abc import Callable

    from anthropic.types import Message, TextBlockParam

    from straightjacket.engine.ai.provider_base import AICallSpec

_P = TypeVar("_P")

_OUTPUT_CONFIG = TypeAdapter(OutputConfigParam)
_CACHE_CONTROL = TypeAdapter(CacheControlEphemeralParam)
_THINKING: TypeAdapter[ThinkingConfigParam] = TypeAdapter(ThinkingConfigParam)


class _Request(MessageCreateParamsBase, total=False):
    extra_body: dict[str, object]


def _routed(adapter: TypeAdapter[_P], extra: dict[str, object], key: str) -> _P:
    try:
        return adapter.validate_python(extra.pop(key), strict=True, extra="forbid")
    except ValidationError as e:
        faults = "; ".join(f"{'.'.join(map(str, fault['loc']))}: {fault['msg']}" for fault in e.errors())
        msg = f"extra_body.{key}: {faults}"
        raise ValueError(msg) from e


def _cached_system(spec: AICallSpec, cache_control: CacheControlEphemeralParam) -> list[TextBlockParam]:
    prefix = spec.cached_system_prefix or spec.system
    if not spec.system.startswith(prefix):
        msg = f"{spec.log_role}: cached_system_prefix is not the start of the system prompt"
        raise ValueError(msg)
    blocks: list[TextBlockParam] = [{"type": "text", "text": prefix, "cache_control": cache_control}]
    if len(spec.system) > len(prefix):
        blocks.append({"type": "text", "text": spec.system[len(prefix) :]})
    return blocks


class AnthropicProvider:
    def __init__(self, api_key: str, timeout_seconds: float, api_base: str) -> None:
        client = partial(anthropic.Anthropic, api_key=api_key, max_retries=0, timeout=timeout_seconds)
        self._client = client(base_url=api_base) if api_base else client()
        log(f"[AnthropicProvider] Initialized{f' (base: {api_base})' if api_base else ''}")

    def list_models(self) -> list[str]:
        return [model.id for model in self._client.models.list()]

    def create_message(self, spec: AICallSpec) -> AIResponse:
        return self._response(self._client.messages.create(**self._request(spec)))

    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse:
        with self._client.messages.stream(**self._request(spec)) as stream:
            for event in stream:
                if event.type == "content_block_delta" and event.delta.type == "text_delta":
                    on_text(event.delta.text)
            final = stream.get_final_message()
        return self._response(final)

    @staticmethod
    def _request(spec: AICallSpec) -> _Request:
        request: _Request = {
            "model": spec.model,
            "max_tokens": spec.sampling["max_tokens"],
            "system": spec.system,
            "messages": [{"role": message["role"], "content": message["content"]} for message in spec.messages],
        }
        extra = dict(spec.sampling["extra_body"])

        body: dict[str, object] = {}
        if spec.sampling["temperature"] is not None:
            body["temperature"] = spec.sampling["temperature"]
        if spec.sampling["top_p"] is not None:
            body["top_p"] = spec.sampling["top_p"]

        output_config: OutputConfigParam = (
            _routed(_OUTPUT_CONFIG, extra, "output_config") if "output_config" in extra else {}
        )
        if spec.json_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": anthropic.transform_schema(spec.json_schema)}
        if output_config:
            request["output_config"] = output_config

        if "cache_control" in extra:
            request["system"] = _cached_system(spec, _routed(_CACHE_CONTROL, extra, "cache_control"))
        if "thinking" in extra:
            request["thinking"] = _routed(_THINKING, extra, "thinking")

        body.update(extra)
        if body:
            request["extra_body"] = body

        if spec.tools is not None:
            request["tools"] = [
                {"name": tool.name, "description": tool.description, "input_schema": tool.parameters}
                for tool in spec.tools
            ]

        return request

    @staticmethod
    def _response(response: Message) -> AIResponse:
        content = ""
        parsed_tool_calls = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                parsed_tool_calls.append(ToolCall(name=block.name, arguments=block.input))

        stop_reason = normalize_stop_reason(
            response.stop_reason, ("max_tokens", "model_context_window_exceeded"), "tool_use", "refusal"
        )

        raw_usage = response.usage
        cache_read = raw_usage.cache_read_input_tokens or 0
        cache_write = raw_usage.cache_creation_input_tokens or 0
        usage = {
            "input_tokens": raw_usage.input_tokens + cache_read + cache_write,
            "output_tokens": raw_usage.output_tokens,
            "cache_read_tokens": cache_read,
        }

        return AIResponse(
            content=content,
            stop_reason=stop_reason,
            tool_calls=parsed_tool_calls,
            usage=usage,
        )
