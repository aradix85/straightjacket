#!/usr/bin/env python3
"""AI provider abstraction: base protocol and response dataclass.

Every AI provider (Anthropic, OpenAI-compatible, etc.) implements the
AIProvider protocol. The engine never talks to provider SDKs directly —
it goes through this interface.

AIResponse normalizes the response format across providers so call sites
don't need to know which provider produced the response.
"""

import re
import time as _time
from dataclasses import dataclass, field
from typing import Protocol

from ..logging_util import log

# TOKEN TRACKING — per-call accumulator for session logging
_token_log: list[dict[str, str | int]] = []


def log_tokens(role: str, input_tokens: int, output_tokens: int) -> None:
    """Record token usage for one AI call."""
    _token_log.append({"role": role, "input": input_tokens, "output": output_tokens})


def drain_token_log() -> list[dict[str, str | int]]:
    """Return and clear accumulated token records. Call after each turn."""
    records = list(_token_log)
    _token_log.clear()
    return records


# NORMALIZED RESPONSE


@dataclass
class AIResponse:
    """Provider-agnostic AI response.

    Attributes:
        content: The response text (prose or JSON string). Empty when
                 the model responds only with tool calls.
        stop_reason: Normalized to "complete", "truncated", or "tool_use".
                     "complete" = model finished naturally.
                     "truncated" = hit max_tokens limit.
                     "tool_use" = model is requesting tool calls.
        tool_calls: List of tool call requests from the model. Each dict has
                    "id" (str), "name" (str), "arguments" (dict).
                    Empty list when no tools are called.
        usage: Optional token counts {"input_tokens": int, "output_tokens": int}.
    """

    content: str
    stop_reason: str = "complete"  # "complete" | "truncated" | "tool_use"
    tool_calls: list[dict[str, str | dict]] = field(default_factory=list)
    usage: dict[str, int] | None = field(default=None, repr=False)


# PROVIDER PROTOCOL


class AIProvider(Protocol):
    """Contract that every AI provider must implement.

    Providers handle:
    - SDK/HTTP client setup
    - Translating create_message args to their native API format
    - Structured output (json_schema) in their provider-specific way
    - Normalizing the response into AIResponse

    Providers do NOT handle:
    - Retry logic (that's in create_with_retry wrapper)
    - Post-processing (think tag stripping, etc. — that's in post_process_response)
    """

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
    ) -> AIResponse:
        """Send a message to the AI model and return a normalized response.

        Args:
            model: Model identifier (e.g. "claude-haiku-4-5-20251001", "qwen3-30b").
            system: System prompt text.
            messages: Conversation history as [{"role": "user"|"assistant", "content": "..."}].
            max_tokens: Maximum tokens in the response.
            json_schema: If provided, request structured JSON output matching this schema.
                         Mutually exclusive with tools.
            tools: If provided, list of tool definitions in OpenAI function calling format:
                   [{"type": "function", "function": {"name": ..., "description": ...,
                     "parameters": ..., "strict": True}}].
                   The model may respond with tool_calls instead of content.
            temperature: Sampling temperature (0.0-1.0). None = provider default.
            top_p: Nucleus sampling cutoff (0.0-1.0). None = provider default.
            top_k: Top-k sampling limit. None = provider default.

        Returns:
            AIResponse with normalized content, stop_reason, tool_calls, and optional usage.
        """
        ...


# RESPONSE POST-PROCESSING

_THINK_TAG_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def post_process_response(response: AIResponse) -> AIResponse:
    """Apply model-agnostic post-processing to an AI response.

    Currently handles:
    - Stripping <think>...</think> tags (Qwen 3 thinking mode)

    Skips post-processing for tool_use responses (no prose to clean).
    """
    if response.stop_reason == "tool_use":
        return response

    content = response.content

    # Strip Qwen-style think tags if present
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


# RETRY WRAPPER


def create_with_retry(
    provider: AIProvider,
    max_retries: int = 2,
    *,
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int,
    json_schema: dict | None = None,
    tools: list[dict] | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    log_role: str = "",
) -> AIResponse:
    """Call provider.create_message with retry on transient errors.

    Retries on:
    - HTTP 429 (rate limit)
    - HTTP 500, 502, 503, 529 (server errors)
    - Connection errors

    Uses exponential backoff: 1s, 2s, 4s, ...

    IMPORTANT: This function uses blocking time.sleep() for backoff.
    All callers MUST run this via asyncio.to_thread() to avoid blocking
    the server event loop.

    If log_role is set, logs token usage per call for budget tracking.

    Returns the post-processed AIResponse.
    """
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
            )
            result = post_process_response(response)
            if log_role and result.usage:
                inp = result.usage.get("input_tokens", 0)
                out = result.usage.get("output_tokens", 0)
                log(f"[TOKENS] {log_role}: {inp} in + {out} out = {inp + out} total")
                log_tokens(log_role, inp, out)
            return result

        except Exception as e:
            # Check if this is a retryable error
            status_code = getattr(e, "status_code", None)
            is_connection_error = "connection" in type(e).__name__.lower() or "connect" in str(e).lower()
            is_retryable_status = status_code in (429, 500, 502, 503, 529)

            if attempt < max_retries and (is_retryable_status or is_connection_error):
                wait = 2**attempt
                error_desc = f"HTTP {status_code}" if status_code else str(e)[:80]
                log(f"[AI] {error_desc}, retry {attempt + 1}/{max_retries} in {wait}s", level="warning")
                _time.sleep(wait)
                continue
            raise
