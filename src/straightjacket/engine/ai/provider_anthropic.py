import json
from typing import Any

import anthropic

from ..logging_util import log
from .provider_base import AICallSpec, AIResponse, extract_usage, normalize_stop_reason


def _to_anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for msg in messages:
        if msg["role"] == "tool":
            block = {"type": "tool_result", "tool_use_id": msg["tool_call_id"], "content": msg["content"]}
            previous = converted[-1] if converted else None
            if previous is not None and previous["role"] == "user" and isinstance(previous["content"], list):
                previous["content"].append(block)
            else:
                converted.append({"role": "user", "content": [block]})
        elif msg["role"] == "assistant" and "tool_calls" in msg:
            blocks: list[dict[str, Any]] = []
            if msg["content"]:
                blocks.append({"type": "text", "text": msg["content"]})
            blocks.extend(
                {
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "input": json.loads(tc["function"]["arguments"]),
                }
                for tc in msg["tool_calls"]
            )
            converted.append({"role": "assistant", "content": blocks})
        else:
            converted.append(msg)
    return converted


class AnthropicProvider:
    def __init__(self, api_key: str, api_base: str | None = None):
        if api_base:
            self._client = anthropic.Anthropic(api_key=api_key, base_url=api_base)
        else:
            self._client = anthropic.Anthropic(api_key=api_key)
        log(f"[AnthropicProvider] Initialized{f' (base: {api_base})' if api_base else ''}")

    def list_models(self) -> list[str]:
        return [model.id for model in self._client.models.list()]

    def create_message(self, spec: AICallSpec) -> AIResponse:
        create_kwargs: dict[str, Any] = {
            "model": spec.model,
            "max_tokens": spec.max_tokens,
            "system": spec.system,
            "messages": _to_anthropic_messages(spec.messages),
        }
        extra: dict[str, Any] = dict(spec.extra_body) if spec.extra_body else {}

        sampling: dict[str, Any] = {}
        if spec.temperature is not None:
            sampling["temperature"] = spec.temperature
        if spec.top_p is not None:
            sampling["top_p"] = spec.top_p
        if spec.top_k is not None:
            sampling["top_k"] = spec.top_k

        output_config: dict[str, Any] = extra.pop("output_config") if "output_config" in extra else {}
        if spec.json_schema is not None:
            output_config = {**output_config, "format": {"type": "json_schema", "schema": spec.json_schema}}
        if output_config:
            create_kwargs["output_config"] = output_config

        for typed_param in ("cache_control", "thinking"):
            if typed_param in extra:
                create_kwargs[typed_param] = extra.pop(typed_param)

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

        response = self._client.messages.create(**create_kwargs)

        content = ""
        parsed_tool_calls = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                parsed_tool_calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "arguments": block.input,
                    }
                )

        stop_reason = normalize_stop_reason(response.stop_reason, "max_tokens", "tool_use")

        usage = extract_usage(getattr(response, "usage", None), "input_tokens", "output_tokens")
        if usage is not None:
            cache_read = getattr(response.usage, "cache_read_input_tokens", None) or 0
            cache_write = getattr(response.usage, "cache_creation_input_tokens", None) or 0
            usage["input_tokens"] += cache_read + cache_write
            usage["cache_read_tokens"] = cache_read

        return AIResponse(
            content=content,
            stop_reason=stop_reason,
            tool_calls=parsed_tool_calls,
            usage=usage,
        )
