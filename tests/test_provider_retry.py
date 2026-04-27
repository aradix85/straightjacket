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


def test_create_with_retry_raises_on_exhaustion() -> None:
    from straightjacket.engine.ai.provider_base import create_with_retry

    class AlwaysFail:
        def create_message(self, spec: AICallSpec) -> AIResponse:
            raise ConnectionError("permanent")

    with pytest.raises(ConnectionError):
        create_with_retry(AlwaysFail(), _spec(max_retries=1))


def test_post_process_decodes_literal_unicode_escapes() -> None:
    from straightjacket.engine.ai.provider_base import post_process_response, AIResponse

    raw = AIResponse(content="She said \\u201chello\\u201d.", stop_reason="complete", tool_calls=[], usage={})
    result = post_process_response(raw)
    assert result.content == "She said \u201chello\u201d."


def test_post_process_leaves_real_unicode_alone() -> None:
    from straightjacket.engine.ai.provider_base import post_process_response, AIResponse

    raw = AIResponse(content="She said \u201chello\u201d.", stop_reason="complete", tool_calls=[], usage={})
    result = post_process_response(raw)
    assert result.content == "She said \u201chello\u201d."


def test_post_process_handles_mixed_real_and_literal_escapes() -> None:
    from straightjacket.engine.ai.provider_base import post_process_response, AIResponse

    raw = AIResponse(
        content="real \u201cquote\u201d and literal \\u201cquote\\u201d",
        stop_reason="complete",
        tool_calls=[],
        usage={},
    )
    result = post_process_response(raw)
    assert result.content == "real \u201cquote\u201d and literal \u201cquote\u201d"


def test_post_process_does_not_alter_response_without_escapes() -> None:
    from straightjacket.engine.ai.provider_base import post_process_response, AIResponse

    raw = AIResponse(content="Plain ASCII content.", stop_reason="complete", tool_calls=[], usage={})
    result = post_process_response(raw)
    assert result is raw
