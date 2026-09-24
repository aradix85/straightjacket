from __future__ import annotations

from typing import Any

import pytest

from straightjacket.engine.ai import provider_base
from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse, create_with_retry, stream_with_retry
from straightjacket.engine.ai.sentence_stream import SentenceStream


def _spec(max_retries: int = 2) -> AICallSpec:
    return AICallSpec(model="m", system="s", messages=[], max_tokens=8, log_role="narrator", max_retries=max_retries)


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


@pytest.fixture
def waits() -> Any:
    recorded: list[float] = []
    provider_base.set_backoff_sleep(recorded.append)
    yield recorded
    provider_base.set_backoff_sleep(lambda _: None)


def test_a_refusal_is_retried(load_engine: None) -> None:
    provider = _Scripted(
        AIResponse(content="", stop_reason="refusal"), AIResponse(content="The door holds.", stop_reason="complete")
    )
    result = create_with_retry(provider, _spec())
    assert (result.content, provider.calls) == ("The door holds.", 2)


def test_a_persistent_refusal_raises_after_the_last_attempt(load_engine: None) -> None:
    from straightjacket.engine.ai.provider_base import AIUnavailableError

    provider = _Scripted(*(AIResponse(content="", stop_reason="refusal") for _ in range(3)))
    with pytest.raises(AIUnavailableError, match="model refused on every attempt"):
        create_with_retry(provider, _spec(max_retries=2))
    assert provider.calls == 3


def test_retry_after_is_honoured_and_capped(load_engine: None, waits: list[float]) -> None:
    provider = _Scripted(_RateLimited("7"), _RateLimited("600"), AIResponse(content="ok", stop_reason="complete"))
    assert create_with_retry(provider, _spec()).content == "ok"
    assert waits == [7.0, 60.0]


class _RefusingStream:
    def create_message(self, spec: AICallSpec) -> AIResponse:
        return AIResponse(content="Recovered.", stop_reason="complete")

    def stream_message(self, spec: AICallSpec, on_text: Any) -> AIResponse:
        on_text("I can")
        return AIResponse(content="I can", stop_reason="refusal")


def test_a_refusal_while_streaming_falls_back_to_a_normal_call(load_engine: None) -> None:
    stream = SentenceStream(lambda text: None)
    result = stream_with_retry(_RefusingStream(), _spec(), stream)
    assert result.content == "Recovered."
    assert stream.failed
