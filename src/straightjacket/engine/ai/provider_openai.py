import json as _json

from collections.abc import Callable
from typing import Any

import openai

from ..logging_util import log
from .provider_base import AICallSpec, AIResponse, extract_usage, normalize_stop_reason


def _usage_with_cache(raw_usage: Any) -> dict[str, int] | None:
    usage = extract_usage(raw_usage, "prompt_tokens", "completion_tokens")
    details = getattr(raw_usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", None)
    if usage is not None and isinstance(cached, int):
        usage["cache_read_tokens"] = cached
    reasoning = getattr(getattr(raw_usage, "completion_tokens_details", None), "reasoning_tokens", None)
    if reasoning is None:
        reasoning = getattr(raw_usage, "reasoning_tokens", None)
    if usage is not None and isinstance(reasoning, int):
        usage["reasoning_tokens"] = reasoning
    return usage


class OpenAICompatibleProvider:
    def __init__(self, api_key: str, timeout_seconds: float, api_base: str | None = None):
        client_kwargs: dict[str, Any] = {"api_key": api_key, "max_retries": 0, "timeout": timeout_seconds}
        if api_base:
            client_kwargs["base_url"] = api_base
        self._client = openai.OpenAI(**client_kwargs)
        log(f"[OpenAICompatibleProvider] Initialized{f' (base: {api_base})' if api_base else ''}")

    def list_models(self) -> list[str]:
        listing = self._client.get("/models", cast_to=object)
        if isinstance(listing, dict):
            listing = listing["data"]
        if not isinstance(listing, list):
            raise TypeError(f"Unexpected model listing from the provider: {type(listing).__name__}")
        return [str(entry["id"]) for entry in listing]

    def create_message(self, spec: AICallSpec) -> AIResponse:
        return self._response(self._client.chat.completions.create(**self._request(spec)))

    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse:
        content = ""
        finish_reason = ""
        raw_usage = None
        for chunk in self._client.chat.completions.create(
            **self._request(spec), stream=True, stream_options={"include_usage": True}
        ):
            if chunk.choices:
                choice = chunk.choices[0]
                text = choice.delta.content
                if text:
                    content += text
                    on_text(text)
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
            if getattr(chunk, "usage", None):
                raw_usage = chunk.usage
        return AIResponse(
            content=content,
            stop_reason=normalize_stop_reason(finish_reason, ("length",), "tool_calls", "content_filter"),
            tool_calls=[],
            usage=_usage_with_cache(raw_usage),
        )

    def _request(self, spec: AICallSpec) -> dict[str, Any]:
        full_messages = [{"role": "system", "content": spec.system}, *spec.messages]

        create_kwargs: dict[str, Any] = {
            "model": spec.model,
            "max_completion_tokens": spec.max_tokens,
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

        return create_kwargs

    def _response(self, response: Any) -> AIResponse:
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

        stop_reason = normalize_stop_reason(choice.finish_reason, ("length",), "tool_calls", "content_filter")

        usage = _usage_with_cache(getattr(response, "usage", None))

        return AIResponse(
            content=content,
            stop_reason=stop_reason,
            tool_calls=parsed_tool_calls,
            usage=usage,
            reasoning=getattr(choice.message, "reasoning", None)
            or getattr(choice.message, "reasoning_content", None)
            or "",
        )
