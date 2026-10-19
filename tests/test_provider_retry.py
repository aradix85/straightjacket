import pytest

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse


def _spec(max_retries: int = 0) -> AICallSpec:
    return AICallSpec(
        model="m",
        system="s",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=100,
        max_retries=max_retries,
    )


def test_create_with_retry_retries_on_connection_error() -> None:
    from straightjacket.engine.ai.provider_base import create_with_retry

    call_count = [0]

    class FlakeyProvider:
        def create_message(self, spec: AICallSpec) -> AIResponse:
            call_count[0] += 1
            if call_count[0] <= 1:
                raise ConnectionError("reset")
            return AIResponse(content="OK", usage={"input_tokens": 10, "output_tokens": 10})

    resp = create_with_retry(FlakeyProvider(), _spec(max_retries=2))
    assert resp.content == "OK"
    assert call_count[0] == 2


def test_create_with_retry_retries_a_timeout_whose_message_never_says_connection(load_engine: None) -> None:
    from straightjacket.engine.ai.provider_base import create_with_retry

    class APIConnectionError(Exception):
        pass

    class APITimeoutError(APIConnectionError):
        pass

    outcomes: list[Exception | AIResponse] = [APITimeoutError("Request timed out."), AIResponse(content="OK")]

    class SlowOnce:
        def create_message(self, spec: AICallSpec) -> AIResponse:
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

    assert create_with_retry(SlowOnce(), _spec(max_retries=1)).content == "OK"


def test_create_with_retry_raises_on_exhaustion() -> None:
    from straightjacket.engine.ai.provider_base import AIUnavailableError, create_with_retry

    class AlwaysFail:
        def create_message(self, spec: AICallSpec) -> AIResponse:
            raise ConnectionError("permanent")

    with pytest.raises(AIUnavailableError) as raised:
        create_with_retry(AlwaysFail(), _spec(max_retries=1))
    assert isinstance(raised.value.__cause__, ConnectionError)


def test_post_process_decodes_literal_unicode_escapes() -> None:
    from straightjacket.engine.ai.provider_base import AIResponse, post_process_response

    raw = AIResponse(content="She said \\u201chello\\u201d.", stop_reason="complete", tool_calls=[], usage={})
    result = post_process_response(raw)
    assert result.content == "She said \u201chello\u201d."


def test_post_process_leaves_real_unicode_alone() -> None:
    from straightjacket.engine.ai.provider_base import AIResponse, post_process_response

    raw = AIResponse(content="She said \u201chello\u201d.", stop_reason="complete", tool_calls=[], usage={})
    result = post_process_response(raw)
    assert result.content == "She said \u201chello\u201d."


def test_post_process_handles_mixed_real_and_literal_escapes() -> None:
    from straightjacket.engine.ai.provider_base import AIResponse, post_process_response

    raw = AIResponse(
        content="real \u201cquote\u201d and literal \\u201cquote\\u201d",
        stop_reason="complete",
        tool_calls=[],
        usage={},
    )
    result = post_process_response(raw)
    assert result.content == "real \u201cquote\u201d and literal \u201cquote\u201d"


def test_post_process_keeps_the_reasoning_when_it_changes_the_content() -> None:
    from straightjacket.engine.ai.provider_base import AIResponse, post_process_response

    raw = AIResponse(
        content="<think>plan</think>The door holds.",
        stop_reason="complete",
        tool_calls=[],
        usage={},
        reasoning="First, the door.",
    )
    result = post_process_response(raw)
    assert (result.content, result.reasoning) == ("The door holds.", "First, the door.")


def test_post_process_does_not_alter_response_without_escapes() -> None:
    from straightjacket.engine.ai.provider_base import AIResponse, post_process_response

    raw = AIResponse(content="Plain ASCII content.", stop_reason="complete", tool_calls=[], usage={})
    result = post_process_response(raw)
    assert result is raw
