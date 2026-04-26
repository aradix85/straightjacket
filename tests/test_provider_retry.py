import pytest

from tests._mocks import MockResponse


def test_create_with_retry_retries_on_connection_error() -> None:
    from straightjacket.engine.ai.provider_base import create_with_retry

    call_count = [0]

    class FlakeyProvider:
        def create_message(self, **kwargs: object) -> MockResponse:
            call_count[0] += 1
            if call_count[0] <= 1:
                raise ConnectionError("reset")
            return MockResponse("OK")

    resp = create_with_retry(
        FlakeyProvider(),
        max_retries=2,
        model="m",
        system="s",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=100,
    )
    assert resp.content == "OK"
    assert call_count[0] == 2


def test_create_with_retry_raises_on_exhaustion() -> None:
    from straightjacket.engine.ai.provider_base import create_with_retry

    class AlwaysFail:
        def create_message(self, **kwargs: object) -> None:
            raise ConnectionError("permanent")

    with pytest.raises(ConnectionError):
        create_with_retry(
            AlwaysFail(),
            max_retries=1,
            model="m",
            system="s",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=100,
        )
