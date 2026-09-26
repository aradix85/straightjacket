import re
import time as _time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
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
    tool_calls: list[dict[str, str | dict[str, Any]]] = field(default_factory=list)
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


def normalize_stop_reason(raw: str, truncated_values: tuple[str, ...], tool_use_value: str, refusal_value: str) -> str:
    if raw in truncated_values:
        return "truncated"
    if raw == tool_use_value:
        return "tool_use"
    if raw == refusal_value:
        return "refusal"
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


@runtime_checkable
class StreamingProvider(Protocol):
    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse: ...


class ModelListingProvider(AIProvider, Protocol):
    def list_models(self) -> list[str]: ...

    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse: ...


class NarrationSink(Protocol):
    def feed(self, delta: str) -> None: ...

    def finish(self) -> None: ...

    def fail(self) -> None: ...


_THINK_TAG_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
_UNICODE_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})")


def decode_literal_unicode_escapes(text: str) -> str:
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
        decoded = decode_literal_unicode_escapes(content)
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


def _log_usage(spec: AICallSpec, result: AIResponse) -> None:
    if not spec.log_role:
        return
    if result.usage:
        inp = result.usage["input_tokens"]
        out = result.usage["output_tokens"]
        cached = result.usage.get("cache_read_tokens")
        cached_note = f", {cached} cached" if cached is not None else ""
        log(f"[TOKENS] {spec.log_role}: {inp} in + {out} out = {inp + out} total{cached_note}")
        log_tokens(spec.log_role, inp, out)
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
    for attempt in range(spec.max_retries + 1):
        try:
            response = provider.create_message(spec)
            result = post_process_response(response)
            _log_usage(spec, result)
            if result.stop_reason == "refusal":
                if attempt < spec.max_retries:
                    log(f"[AI] {spec.log_role}: model refused, retry {attempt + 1}/{spec.max_retries}", level="warning")
                    continue
                log(f"[AI] {spec.log_role}: model refused on every attempt", level="error")
                raise AIUnavailableError(f"{spec.log_role}: model refused on every attempt")
            return result

        except Exception as e:
            from ..engine_loader import eng as _eng

            _retry_cfg = _eng().retry
            status_code = getattr(e, "status_code", None)
            is_connection_error = "connection" in type(e).__name__.lower() or "connect" in str(e).lower()
            is_retryable_status = status_code in _retry_cfg.retryable_http_codes

            if attempt < spec.max_retries and (is_retryable_status or is_connection_error):
                retry_after = _retry_after_seconds(e)
                wait = (
                    min(retry_after, _retry_cfg.max_retry_after_seconds)
                    if retry_after is not None
                    else _retry_cfg.backoff_base**attempt
                )
                error_desc = f"HTTP {status_code}" if status_code else str(e)[: _eng().truncations.log_medium]
                log(f"[AI] {error_desc}, retry {attempt + 1}/{spec.max_retries} in {wait}s", level="warning")
                _backoff_sleep(wait)
                continue
            if isinstance(e, AIUnavailableError):
                raise
            raise AIUnavailableError(f"{spec.log_role}: {type(e).__name__}: {e}") from e
    raise RuntimeError(f"{spec.log_role}: no attempts made")


def stream_with_retry(provider: AIProvider, spec: AICallSpec, sink: NarrationSink) -> AIResponse:
    if not isinstance(provider, StreamingProvider):
        response = create_with_retry(provider, spec)
        sink.feed(response.content)
        sink.finish()
        return response
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
