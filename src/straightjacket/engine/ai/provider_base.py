import re
import time as _time
from dataclasses import dataclass, field
from typing import Any, Protocol
from collections.abc import Callable

from ..logging_util import log


_backoff_sleep: Callable[[float], Any] = _time.sleep


def set_backoff_sleep(fn: Callable[[float], Any]) -> None:
    global _backoff_sleep
    _backoff_sleep = fn


_token_log: list[dict[str, str | int]] = []


def log_tokens(role: str, input_tokens: int, output_tokens: int) -> None:
    _token_log.append({"role": role, "input": input_tokens, "output": output_tokens})


def drain_token_log() -> list[dict[str, str | int]]:
    records = list(_token_log)
    _token_log.clear()
    return records


@dataclass
class AIResponse:
    content: str
    stop_reason: str = "complete"
    tool_calls: list[dict[str, str | dict]] = field(default_factory=list)
    usage: dict[str, int] | None = field(default=None, repr=False)


def normalize_stop_reason(raw: str, truncated_value: str, tool_use_value: str) -> str:
    if raw == truncated_value:
        return "truncated"
    if raw == tool_use_value:
        return "tool_use"
    return "complete"


def extract_usage(raw_usage: Any, input_key: str, output_key: str) -> dict[str, int] | None:
    if not raw_usage:
        return None
    return {
        "input_tokens": getattr(raw_usage, input_key, 0),
        "output_tokens": getattr(raw_usage, output_key, 0),
    }


class AIProvider(Protocol):
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
    ) -> AIResponse: ...


_THINK_TAG_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def post_process_response(response: AIResponse) -> AIResponse:
    if response.stop_reason == "tool_use":
        return response

    content = response.content

    if "<think>" in content:
        content = _THINK_TAG_RE.sub("", content).lstrip()
        if content != response.content:
            log("[AI] Stripped <think> tags from response")

    if content != response.content:
        return AIResponse(
            content=content,
            stop_reason=response.stop_reason,
            tool_calls=response.tool_calls,
            usage=response.usage,
        )
    return response


def create_with_retry(
    provider: AIProvider,
    *,
    max_retries: int = 2,
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
    log_role: str = "",
) -> AIResponse:
    for attempt in range(max_retries + 1):
        try:
            response = provider.create_message(
                model=model,
                system=system,
                messages=messages,
                max_tokens=max_tokens,
                json_schema=json_schema,
                tools=tools,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                extra_body=extra_body,
            )
            result = post_process_response(response)
            if log_role:
                if result.usage:
                    inp = result.usage.get("input_tokens", 0)
                    out = result.usage.get("output_tokens", 0)
                    log(f"[TOKENS] {log_role}: {inp} in + {out} out = {inp + out} total")
                    log_tokens(log_role, inp, out)
                else:
                    log(f"[TOKENS] {log_role}: usage not returned by provider", level="warning")
            return result

        except Exception as e:
            from ..engine_loader import eng as _eng

            _retry_cfg = _eng().retry
            status_code = getattr(e, "status_code", None)
            is_connection_error = "connection" in type(e).__name__.lower() or "connect" in str(e).lower()
            is_retryable_status = status_code in _retry_cfg.retryable_http_codes

            if attempt < max_retries and (is_retryable_status or is_connection_error):
                wait = _retry_cfg.backoff_base**attempt
                error_desc = f"HTTP {status_code}" if status_code else str(e)[: _eng().truncations.log_medium]
                log(f"[AI] {error_desc}, retry {attempt + 1}/{max_retries} in {wait}s", level="warning")
                _backoff_sleep(wait)
                continue
            raise
