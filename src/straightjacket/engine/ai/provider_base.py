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


@dataclass(frozen=True)
class AICallSpec:
    model: str
    system: str
    messages: list[dict]
    max_tokens: int
    max_retries: int = 0
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    extra_body: dict | None = None
    json_schema: dict | None = None
    tools: list[dict] | None = None
    log_role: str = ""


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
    def create_message(self, spec: AICallSpec) -> AIResponse: ...


_THINK_TAG_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
_UNICODE_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})")


def _decode_literal_unicode_escapes(text: str) -> str:
    return _UNICODE_ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), text)


def post_process_response(response: AIResponse) -> AIResponse:
    if response.stop_reason == "tool_use":
        return response

    content = response.content

    if "<think>" in content:
        content = _THINK_TAG_RE.sub("", content).lstrip()
        if content != response.content:
            log("[AI] Stripped <think> tags from response")

    if "\\u" in content:
        decoded = _decode_literal_unicode_escapes(content)
        if decoded != content:
            log("[AI] Decoded literal \\uXXXX escape sequences in response")
            content = decoded

    if content != response.content:
        return AIResponse(
            content=content,
            stop_reason=response.stop_reason,
            tool_calls=response.tool_calls,
            usage=response.usage,
        )
    return response


def create_with_retry(provider: AIProvider, spec: AICallSpec) -> AIResponse:
    for attempt in range(spec.max_retries + 1):
        try:
            response = provider.create_message(spec)
            result = post_process_response(response)
            if spec.log_role:
                if result.usage:
                    inp = result.usage["input_tokens"]
                    out = result.usage["output_tokens"]
                    log(f"[TOKENS] {spec.log_role}: {inp} in + {out} out = {inp + out} total")
                    log_tokens(spec.log_role, inp, out)
                else:
                    log(f"[TOKENS] {spec.log_role}: usage not returned by provider", level="warning")
            return result

        except Exception as e:
            from ..engine_loader import eng as _eng

            _retry_cfg = _eng().retry
            status_code = getattr(e, "status_code", None)
            is_connection_error = "connection" in type(e).__name__.lower() or "connect" in str(e).lower()
            is_retryable_status = status_code in _retry_cfg.retryable_http_codes

            if attempt < spec.max_retries and (is_retryable_status or is_connection_error):
                wait = _retry_cfg.backoff_base**attempt
                error_desc = f"HTTP {status_code}" if status_code else str(e)[: _eng().truncations.log_medium]
                log(f"[AI] {error_desc}, retry {attempt + 1}/{spec.max_retries} in {wait}s", level="warning")
                _backoff_sleep(wait)
                continue
            raise
