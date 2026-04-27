from typing import Any

import anthropic

from ..logging_util import log
from .provider_base import AICallSpec, AIResponse, extract_usage, normalize_stop_reason


class AnthropicProvider:
    def __init__(self, api_key: str, api_base: str | None = None):
        if api_base:
            self._client = anthropic.Anthropic(api_key=api_key, base_url=api_base)
        else:
            self._client = anthropic.Anthropic(api_key=api_key)
        log(f"[AnthropicProvider] Initialized{f' (base: {api_base})' if api_base else ''}")

    def create_message(self, spec: AICallSpec) -> AIResponse:
        create_kwargs: dict[str, Any] = {
            "model": spec.model,
            "max_tokens": spec.max_tokens,
            "system": spec.system,
            "messages": spec.messages,
        }

        if spec.temperature is not None:
            create_kwargs["temperature"] = spec.temperature
        if spec.top_p is not None:
            create_kwargs["top_p"] = spec.top_p
        if spec.top_k is not None:
            create_kwargs["top_k"] = spec.top_k

        if spec.json_schema is not None:
            create_kwargs["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": spec.json_schema,
                }
            }

        if spec.tools is not None:
            create_kwargs["tools"] = [
                {
                    "name": t.get("function", {}).get("name", ""),
                    "description": t.get("function", {}).get("description", ""),
                    "input_schema": t.get("function", {}).get("parameters", {}),
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

        return AIResponse(
            content=content,
            stop_reason=stop_reason,
            tool_calls=parsed_tool_calls,
            usage=usage,
        )
