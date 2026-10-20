import re
import time as _time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from ..engine_loader import eng
from ..logging_util import log


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class AIResponse:
    content: str
    stop_reason: str = "complete"
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] | None = field(default=None, repr=False)
    reasoning: str = field(default="", repr=False)


@dataclass(frozen=True)
class AICallSpec:
    model: str
    system: str
    messages: list[dict[str, Any]]
    max_tokens: int
    max_retries: int = 0
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    extra_body: dict[str, Any] | None = None
    json_schema: dict[str, Any] | None = None
    tools: list[dict[str, Any]] | None = None
    log_role: str = ""
    cached_system_prefix: str = ""


def normalize_stop_reason(raw: str, truncated_values: tuple[str, ...], tool_use_value: str, refusal_value: str) -> str:
    if raw in truncated_values:
        return "truncated"
    if raw == tool_use_value:
        return "tool_use"
    if raw == refusal_value:
        return "refusal"
    return "complete"


class AIProvider(Protocol):
    def create_message(self, spec: AICallSpec) -> AIResponse: ...

    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse: ...


class ModelListingProvider(AIProvider, Protocol):
    def list_models(self) -> list[str]: ...


class NarrationSink(Protocol):
    def feed(self, delta: str) -> None: ...

    def finish(self) -> None: ...

    def fail(self) -> None: ...


_UNICODE_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})")


def decode_literal_unicode_escapes(text: str) -> str:
    return _UNICODE_ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), text)


def post_process_response(response: AIResponse) -> AIResponse:
    if response.stop_reason == "tool_use":
        return response

    content = response.content

    parser = eng().parser
    if parser.think_open in content:
        content = re.sub(parser.think_block, "", content, flags=re.DOTALL).lstrip()
        if content != response.content:
            log("[AI] Stripped <think> tags from response")

    if "\\u" in content:
        decoded = decode_literal_unicode_escapes(content)
        if decoded != content:
            log("[AI] Decoded literal \\uXXXX escape sequences in response")
            content = decoded

    if content != response.content:
        return replace(response, content=content)
    return response


def _log_usage(spec: AICallSpec, result: AIResponse) -> None:
    if result.usage:
        inp = result.usage["input_tokens"]
        out = result.usage["output_tokens"]
        cached = result.usage.get("cache_read_tokens")
        cached_note = f", {cached} cached" if cached is not None else ""
        log(f"[TOKENS] {spec.log_role}: {inp} in + {out} out = {inp + out} total{cached_note}")
    else:
        log(f"[TOKENS] {spec.log_role}: usage not returned by provider", level="warning")


def _retry_after_seconds(error: Exception) -> float | None:
    headers = getattr(getattr(error, "response", None), "headers", None)
    if not headers:
        return None
    value = headers.get("retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


class AIUnavailableError(Exception):
    pass


def create_with_retry(provider: AIProvider, spec: AICallSpec) -> AIResponse:
    attempt = 0
    while True:
        try:
            response = provider.create_message(spec)
        except Exception as e:
            _retry_cfg = eng().retry
            status_code = getattr(e, "status_code", None)
            is_connection_error = any("Connection" in cls.__name__ for cls in type(e).__mro__)
            is_retryable_status = status_code in _retry_cfg.retryable_http_codes
            if attempt >= spec.max_retries or not (is_retryable_status or is_connection_error):
                raise AIUnavailableError(f"{spec.log_role}: {type(e).__name__}: {e}") from e
            retry_after = _retry_after_seconds(e)
            wait = (
                min(retry_after, _retry_cfg.max_retry_after_seconds)
                if retry_after is not None
                else _retry_cfg.backoff_base**attempt
            )
            error_desc = f"HTTP {status_code}" if status_code else str(e)[: eng().truncations.log_medium]
            log(f"[AI] {error_desc}, retry {attempt + 1}/{spec.max_retries} in {wait}s", level="warning")
            _time.sleep(wait)
            attempt += 1
            continue
        result = post_process_response(response)
        _log_usage(spec, result)
        if result.stop_reason != "refusal":
            return result
        if attempt >= spec.max_retries:
            log(f"[AI] {spec.log_role}: model refused on every attempt", level="error")
            raise AIUnavailableError(f"{spec.log_role}: model refused on every attempt")
        log(f"[AI] {spec.log_role}: model refused, retry {attempt + 1}/{spec.max_retries}", level="warning")
        attempt += 1


def stream_with_retry(provider: AIProvider, spec: AICallSpec, sink: NarrationSink) -> AIResponse:
    try:
        response = provider.stream_message(spec, sink.feed)
    except Exception as e:
        log(
            f"[AI] Streaming failed for {spec.log_role} ({type(e).__name__}: {e}); retrying without streaming",
            level="warning",
        )
        sink.fail()
        return create_with_retry(provider, spec)
    result = post_process_response(response)
    _log_usage(spec, result)
    if result.stop_reason == "refusal":
        log(f"[AI] {spec.log_role}: model refused while streaming; retrying without streaming", level="warning")
        sink.fail()
        return create_with_retry(provider, spec)
    sink.finish()
    return result
