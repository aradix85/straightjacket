from collections.abc import Callable
from typing import Any

import anthropic

from ..logging_util import log
from .provider_base import AICallSpec, AIResponse, ToolCall, normalize_stop_reason


def _cached_system(spec: AICallSpec, cache_control: dict[str, Any]) -> list[dict[str, Any]]:
    prefix = spec.cached_system_prefix or spec.system
    if not spec.system.startswith(prefix):
        raise ValueError(f"{spec.log_role}: cached_system_prefix is not the start of the system prompt")
    blocks: list[dict[str, Any]] = [{"type": "text", "text": prefix, "cache_control": cache_control}]
    if len(spec.system) > len(prefix):
        blocks.append({"type": "text", "text": spec.system[len(prefix) :]})
    return blocks


class AnthropicProvider:
    def __init__(self, api_key: str, timeout_seconds: float, api_base: str):
        client_kwargs: dict[str, Any] = {"api_key": api_key, "max_retries": 0, "timeout": timeout_seconds}
        if api_base:
            client_kwargs["base_url"] = api_base
        self._client = anthropic.Anthropic(**client_kwargs)
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

    def _request(self, spec: AICallSpec) -> dict[str, Any]:
        create_kwargs: dict[str, Any] = {
            "model": spec.model,
            "max_tokens": spec.max_tokens,
            "system": spec.system,
            "messages": spec.messages,
        }
        extra: dict[str, Any] = dict(spec.extra_body)

        sampling: dict[str, Any] = {}
        if spec.temperature is not None:
            sampling["temperature"] = spec.temperature
        if spec.top_p is not None:
            sampling["top_p"] = spec.top_p

        output_config: dict[str, Any] = extra.pop("output_config") if "output_config" in extra else {}
        if spec.json_schema is not None:
            schema = anthropic.transform_schema(spec.json_schema)
            output_config = {**output_config, "format": {"type": "json_schema", "schema": schema}}
        if output_config:
            create_kwargs["output_config"] = output_config

        if "cache_control" in extra:
            create_kwargs["system"] = _cached_system(spec, extra.pop("cache_control"))
        if "thinking" in extra:
            create_kwargs["thinking"] = extra.pop("thinking")

        body = {**sampling, **extra}
        if body:
            create_kwargs["extra_body"] = body

        if spec.tools is not None:
            create_kwargs["tools"] = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"]["description"],
                    "input_schema": t["function"]["parameters"],
                }
                for t in spec.tools
            ]

        return create_kwargs

    def _response(self, response: Any) -> AIResponse:
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
