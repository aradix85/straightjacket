import json as _json

from typing import Any

import openai

from ..logging_util import log
from .provider_base import AICallSpec, AIResponse, extract_usage, normalize_stop_reason


class OpenAICompatibleProvider:
    def __init__(self, api_key: str, api_base: str | None = None):
        if api_base:
            self._client = openai.OpenAI(api_key=api_key, base_url=api_base)
        else:
            self._client = openai.OpenAI(api_key=api_key)
        log(f"[OpenAICompatibleProvider] Initialized{f' (base: {api_base})' if api_base else ''}")

    def create_message(self, spec: AICallSpec) -> AIResponse:
        full_messages = [{"role": "system", "content": spec.system}] + spec.messages

        create_kwargs: dict[str, Any] = {
            "model": spec.model,
            "max_tokens": spec.max_tokens,
            "messages": full_messages,
        }

        if spec.temperature is not None:
            create_kwargs["temperature"] = spec.temperature
        if spec.top_p is not None:
            create_kwargs["top_p"] = spec.top_p

        extra: dict[str, Any] = dict(spec.extra_body) if spec.extra_body else {}
        if spec.top_k is not None:
            extra["top_k"] = spec.top_k
        if extra:
            create_kwargs["extra_body"] = extra

        if spec.json_schema is not None:
            schema_name = spec.json_schema["title"]
            create_kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": spec.json_schema,
                },
            }

        if spec.tools is not None:
            create_kwargs["tools"] = spec.tools

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

        stop_reason = normalize_stop_reason(choice.finish_reason, "length", "tool_calls")

        usage = extract_usage(getattr(response, "usage", None), "prompt_tokens", "completion_tokens")

        return AIResponse(
            content=content,
            stop_reason=stop_reason,
            tool_calls=parsed_tool_calls,
            usage=usage,
        )
