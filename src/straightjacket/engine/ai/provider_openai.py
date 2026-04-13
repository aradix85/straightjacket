#!/usr/bin/env python3
"""OpenAI-compatible AI provider implementation.

Wraps the openai SDK to implement the AIProvider protocol.
Works with any OpenAI-compatible API: OpenAI, OpenRouter, Cerebras,
Together, local vLLM/Ollama endpoints, etc.

Structured output uses response_format with json_schema (strict: true),
which is supported by all target providers.
"""

import json as _json

from typing import Any

import openai

from ..logging_util import log
from .provider_base import AIResponse


class OpenAICompatibleProvider:
    """AIProvider implementation for OpenAI-compatible APIs.

    Structured output: uses response_format with json_schema and strict: true.
    Confirmed working on Cerebras (GLM-4.7, Qwen 3 235B), OpenRouter, and OpenAI.

    Stop reason mapping:
        "stop" -> "complete"
        "length" -> "truncated"
        anything else -> "complete" (safe default)
    """

    def __init__(self, api_key: str, api_base: str | None = None):
        if api_base:
            self._client = openai.OpenAI(api_key=api_key, base_url=api_base)
        else:
            self._client = openai.OpenAI(api_key=api_key)
        log(f"[OpenAICompatibleProvider] Initialized{f' (base: {api_base})' if api_base else ''}")

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
        """Send a message via the OpenAI-compatible SDK."""

        full_messages = [{"role": "system", "content": system}] + messages

        create_kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": full_messages,
        }

        if temperature is not None:
            create_kwargs["temperature"] = temperature
        if top_p is not None:
            create_kwargs["top_p"] = top_p

        # Provider-specific params (top_k, per-role extra_body from config)
        extra: dict[str, Any] = dict(extra_body) if extra_body else {}
        if top_k is not None:
            extra["top_k"] = top_k
        if extra:
            create_kwargs["extra_body"] = extra

        if json_schema is not None:
            schema_name = json_schema.get("name", "response")
            create_kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": json_schema,
                },
            }

        if tools is not None:
            create_kwargs["tools"] = tools

        response = self._client.chat.completions.create(**create_kwargs)

        choice = response.choices[0]
        content = choice.message.content or ""

        parsed_tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                parsed_tool_calls.append(
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": _json.loads(tc.function.arguments),
                    }
                )

        finish = choice.finish_reason
        if finish == "length":
            stop_reason = "truncated"
        elif finish == "tool_calls":
            stop_reason = "tool_use"
        else:
            stop_reason = "complete"

        usage = None
        if hasattr(response, "usage") and response.usage:
            usage = {
                "input_tokens": getattr(response.usage, "prompt_tokens", 0),
                "output_tokens": getattr(response.usage, "completion_tokens", 0),
            }

        return AIResponse(
            content=content,
            stop_reason=stop_reason,
            tool_calls=parsed_tool_calls,
            usage=usage,
        )
