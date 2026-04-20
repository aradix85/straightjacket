"""Anthropic AI provider implementation."""

from typing import Any

import anthropic

from ..logging_util import log
from .provider_base import AIResponse


class AnthropicProvider:
    """AIProvider implementation for the Anthropic API (Claude models).

    Structured output: uses Anthropic's native output_config with json_schema.

    Stop reason mapping:
        "end_turn" -> "complete"
        "max_tokens" -> "truncated"
        anything else -> "complete" (safe default)
    """

    def __init__(self, api_key: str, api_base: str | None = None):
        if api_base:
            self._client = anthropic.Anthropic(api_key=api_key, base_url=api_base)
        else:
            self._client = anthropic.Anthropic(api_key=api_key)
        log(f"[AnthropicProvider] Initialized{f' (base: {api_base})' if api_base else ''}")

    def create_message(
        self,
        model: str,
        system: str,
        messages: list[dict],
        max_tokens: int,
        json_schema: dict | None = None,
        tools: list[dict] | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        extra_body: dict | None = None,
    ) -> AIResponse:
        """Send a message via the Anthropic SDK."""
        create_kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }

        if temperature is not None:
            create_kwargs["temperature"] = temperature
        if top_p is not None:
            create_kwargs["top_p"] = top_p
        if top_k is not None:
            create_kwargs["top_k"] = top_k

        if json_schema is not None:
            create_kwargs["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": json_schema,
                }
            }

        if tools is not None:
            create_kwargs["tools"] = [
                {
                    "name": t.get("function", {}).get("name", ""),
                    "description": t.get("function", {}).get("description", ""),
                    "input_schema": t.get("function", {}).get("parameters", {}),
                }
                for t in tools
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

        stop = response.stop_reason
        if stop == "max_tokens":
            stop_reason = "truncated"
        elif stop == "tool_use":
            stop_reason = "tool_use"
        else:
            stop_reason = "complete"

        usage = None
        if hasattr(response, "usage") and response.usage:
            usage = {
                "input_tokens": getattr(response.usage, "input_tokens", 0),
                "output_tokens": getattr(response.usage, "output_tokens", 0),
            }

        return AIResponse(
            content=content,
            stop_reason=stop_reason,
            tool_calls=parsed_tool_calls,
            usage=usage,
        )
