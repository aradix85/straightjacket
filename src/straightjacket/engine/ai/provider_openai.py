from __future__ import annotations

import json as _json
from functools import partial
from typing import TYPE_CHECKING

import openai
from openai.types.chat import ChatCompletionMessageFunctionToolCall
from openai.types.chat.completion_create_params import CompletionCreateParamsBase

from straightjacket.engine.ai.provider_base import AIResponse, ToolCall, normalize_stop_reason
from straightjacket.engine.logging_util import log
from straightjacket.engine.serialization import read_key, shaped

if TYPE_CHECKING:
    from collections.abc import Callable

    from openai.types import CompletionUsage
    from openai.types.chat import ChatCompletion, ChatCompletionMessageParam, ChatCompletionMessageToolCallUnion

    from straightjacket.engine.ai.provider_base import AICallSpec, Message


class _Request(CompletionCreateParamsBase, total=False):
    extra_body: dict[str, object]


def _message(message: Message) -> ChatCompletionMessageParam:
    if message["role"] == "assistant":
        return {"role": "assistant", "content": message["content"]}
    return {"role": "user", "content": message["content"]}


def _tool_call(call: ChatCompletionMessageToolCallUnion) -> ToolCall:
    function = shaped(call, ChatCompletionMessageFunctionToolCall, "tool call: expected a function call").function
    return ToolCall(
        name=function.name, arguments=shaped(_json.loads(function.arguments), dict, f"{function.name}: expected dict")
    )


def _usage(raw_usage: CompletionUsage | None) -> dict[str, int] | None:
    if raw_usage is None:
        return None
    usage = {"input_tokens": raw_usage.prompt_tokens, "output_tokens": raw_usage.completion_tokens}
    prompt_details = raw_usage.prompt_tokens_details
    if prompt_details is not None and prompt_details.cached_tokens is not None:
        usage["cache_read_tokens"] = prompt_details.cached_tokens
    completion_details = raw_usage.completion_tokens_details
    reasoning = completion_details.reasoning_tokens if completion_details is not None else None
    if reasoning is None:
        reasoning = getattr(raw_usage, "reasoning_tokens", None)  # some hosts report it beside the standard fields
    if reasoning is not None:
        usage["reasoning_tokens"] = reasoning
    return usage


class OpenAICompatibleProvider:
    def __init__(self, api_key: str, timeout_seconds: float, api_base: str) -> None:
        client = partial(openai.OpenAI, api_key=api_key, max_retries=0, timeout=timeout_seconds)
        self._client = client(base_url=api_base) if api_base else client()
        log(f"[OpenAICompatibleProvider] Initialized{f' (base: {api_base})' if api_base else ''}")

    def list_models(self) -> list[str]:
        listing = self._client.get("/models", cast_to=object)
        if isinstance(listing, dict):
            listing = listing["data"]
        if not isinstance(listing, list):
            msg = f"Unexpected model listing from the provider: {type(listing).__name__}"
            raise TypeError(msg)
        return [str(entry["id"]) for entry in listing]

    def create_message(self, spec: AICallSpec) -> AIResponse:
        return self._response(self._client.chat.completions.create(**self._request(spec)))

    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse:
        content = ""
        finish_reason = ""
        raw_usage = None
        request = self._request(spec)
        request["stream_options"] = {"include_usage": True}
        for chunk in self._client.chat.completions.create(**request, stream=True):
            if chunk.choices:
                choice = chunk.choices[0]
                text = choice.delta.content
                if text:
                    content += text
                    on_text(text)
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
            if chunk.usage is not None:
                raw_usage = chunk.usage
        return AIResponse(
            content=content,
            stop_reason=normalize_stop_reason(finish_reason, ("length",), "tool_calls", "content_filter"),
            tool_calls=[],
            usage=_usage(raw_usage),
        )

    @staticmethod
    def _request(spec: AICallSpec) -> _Request:
        request: _Request = {
            "model": spec.model,
            "max_completion_tokens": spec.sampling["max_tokens"],
            "messages": [{"role": "system", "content": spec.system}, *map(_message, spec.messages)],
        }

        if spec.sampling["temperature"] is not None:
            request["temperature"] = spec.sampling["temperature"]
        if spec.sampling["top_p"] is not None:
            request["top_p"] = spec.sampling["top_p"]

        if spec.sampling["extra_body"]:
            request["extra_body"] = dict(spec.sampling["extra_body"])

        if spec.json_schema is not None:
            request["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": read_key(spec.json_schema, "title", str, "json_schema"),
                    "strict": True,
                    "schema": spec.json_schema,
                },
            }

        if spec.tools is not None:
            request["tools"] = [
                {
                    "type": "function",
                    "function": {"name": tool.name, "description": tool.description, "parameters": tool.parameters},
                }
                for tool in spec.tools
            ]

        return request

    @staticmethod
    def _response(response: ChatCompletion) -> AIResponse:
        choice = response.choices[0]
        content = choice.message.content or ""

        return AIResponse(
            content=content,
            stop_reason=normalize_stop_reason(choice.finish_reason, ("length",), "tool_calls", "content_filter"),
            tool_calls=[_tool_call(call) for call in choice.message.tool_calls or []],
            usage=_usage(response.usage),
            reasoning=getattr(choice.message, "reasoning", None)
            or getattr(choice.message, "reasoning_content", None)
            or "",
        )
