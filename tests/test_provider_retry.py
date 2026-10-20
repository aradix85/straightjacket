from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from straightjacket.engine.ai import provider_base
from straightjacket.engine.ai.provider_base import (
    AICallSpec,
    AIResponse,
    AIUnavailableError,
    create_with_retry,
    post_process_response,
    stream_with_retry,
)
from straightjacket.engine.ai.sentence_stream import SentenceStream


def _spec(max_retries: int = 2) -> AICallSpec:
    return AICallSpec(
        model="m",
        system="s",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=8,
        max_retries=max_retries,
        temperature=None,
        top_p=None,
        extra_body={},
        json_schema=None,
        tools=None,
        log_role="narrator",
        cached_system_prefix="",
    )


class _Scripted:
    def __init__(self, *outcomes: Any) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def create_message(self, spec: AICallSpec) -> AIResponse:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _RateLimited(Exception):
    def __init__(self, retry_after: str) -> None:
        super().__init__("rate limited")
        self.status_code = 429
        self.response = type("R", (), {"headers": {"retry-after": retry_after}})()


class APIConnectionError(Exception):
    pass


class APITimeoutError(APIConnectionError):
    pass


@pytest.fixture
def waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    recorded: list[float] = []
    monkeypatch.setattr(provider_base, "_time", SimpleNamespace(sleep=recorded.append))
    return recorded


@pytest.mark.parametrize(
    "failure", [ConnectionError("reset"), APITimeoutError("Request timed out.")], ids=["connection", "timeout"]
)
def test_a_connection_error_is_retried_whatever_its_message_says(load_engine: None, failure: Exception) -> None:
    provider = _Scripted(failure, AIResponse(content="OK", stop_reason="complete"))
    assert create_with_retry(provider, _spec()).content == "OK"
    assert provider.calls == 2


def test_a_connection_error_on_every_attempt_makes_the_ai_unavailable(load_engine: None) -> None:
    provider = _Scripted(ConnectionError("permanent"), ConnectionError("permanent"))
    with pytest.raises(AIUnavailableError) as raised:
        create_with_retry(provider, _spec(max_retries=1))
    assert isinstance(raised.value.__cause__, ConnectionError)


def test_a_refusal_is_retried(load_engine: None) -> None:
    provider = _Scripted(
        AIResponse(content="", stop_reason="refusal"), AIResponse(content="The door holds.", stop_reason="complete")
    )
    result = create_with_retry(provider, _spec())
    assert (result.content, provider.calls) == ("The door holds.", 2)


def test_a_persistent_refusal_raises_after_the_last_attempt(load_engine: None) -> None:
    provider = _Scripted(*(AIResponse(content="", stop_reason="refusal") for _ in range(3)))
    with pytest.raises(AIUnavailableError, match="model refused on every attempt"):
        create_with_retry(provider, _spec(max_retries=2))
    assert provider.calls == 3


def test_retry_after_is_honoured_and_capped(load_engine: None, waits: list[float]) -> None:
    provider = _Scripted(_RateLimited("7"), _RateLimited("600"), AIResponse(content="ok", stop_reason="complete"))
    assert create_with_retry(provider, _spec()).content == "ok"
    assert waits == [7.0, 60.0]


class _StreamFails:
    def __init__(self, refuses: bool) -> None:
        self.refuses = refuses

    def create_message(self, spec: AICallSpec) -> AIResponse:
        return AIResponse(content="Recovered without streaming.", stop_reason="complete")

    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse:
        on_text("Half a sent")
        if self.refuses:
            return AIResponse(content="Half a sent", stop_reason="refusal")
        raise ConnectionError("stream dropped")


@pytest.mark.parametrize("refuses", [False, True], ids=["dropped", "refused"])
def test_a_failed_stream_falls_back_to_a_normal_call_and_is_not_complete(load_engine: None, refuses: bool) -> None:
    stream = SentenceStream(lambda text: None)
    response = stream_with_retry(_StreamFails(refuses), _spec(), stream)
    assert response.content == "Recovered without streaming."
    assert stream.failed
    assert not stream.complete


@pytest.mark.parametrize(
    ("raw", "decoded"),
    [
        ("She said \\u201chello\\u201d.", "She said \u201chello\u201d."),
        ("She said \u201chello\u201d.", "She said \u201chello\u201d."),
        (
            "real \u201cquote\u201d and literal \\u201cquote\\u201d",
            "real \u201cquote\u201d and literal \u201cquote\u201d",
        ),
    ],
    ids=["literal", "real", "mixed"],
)
def test_post_processing_decodes_literal_unicode_escapes_only(raw: str, decoded: str) -> None:
    response = AIResponse(content=raw, stop_reason="complete", tool_calls=[], usage={})
    assert post_process_response(response).content == decoded


def test_post_processing_keeps_the_reasoning_when_it_changes_the_content() -> None:
    raw = AIResponse(
        content="<think>plan</think>The door holds.",
        stop_reason="complete",
        tool_calls=[],
        usage={},
        reasoning="First, the door.",
    )
    result = post_process_response(raw)
    assert (result.content, result.reasoning) == ("The door holds.", "First, the door.")


def test_post_processing_returns_a_plain_response_as_it_is() -> None:
    raw = AIResponse(content="Plain ASCII content.", stop_reason="complete", tool_calls=[], usage={})
    assert post_process_response(raw) is raw
