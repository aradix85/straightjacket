import json
from typing import Any

import pytest


class _Capture:
    def __init__(self) -> None:
        self.specs: list[Any] = []

    def create_message(self, spec: Any) -> Any:
        from straightjacket.engine.ai.provider_base import AIResponse

        self.specs.append(spec)
        return AIResponse(content="{}")

    def stream_message(self, spec: Any, on_text: Any) -> Any:
        return self.create_message(spec)


def _router(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, _Capture]:
    from straightjacket.engine.ai import api_client

    capture = _Capture()
    monkeypatch.setattr(api_client, "provider_for_role", lambda role: "fake")
    adapters: dict[str, Any] = {"fake": capture}
    return api_client.RoutingProvider(adapters), capture


def _spec(**kwargs: Any) -> Any:
    from straightjacket.engine.ai.provider_base import AICallSpec

    return AICallSpec(
        model="m",
        system="You are the Brain.",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=10,
        log_role="brain",
        **kwargs,
    )


def test_a_call_with_a_schema_carries_the_schema_at_the_end_of_its_last_message(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    router, capture = _router(monkeypatch)
    schema = {"type": "object", "required": ["move"], "properties": {"move": {"type": "string"}}}
    router.create_message(_spec(json_schema=schema))
    sent = capture.specs[0]
    assert sent.system == "You are the Brain."
    assert sent.messages[-1]["content"].startswith("hi\n\n")
    assert sent.messages[-1]["content"].endswith(json.dumps(schema, separators=(",", ":")))
    assert sent.json_schema == schema


def test_a_call_without_a_schema_is_sent_unchanged(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    router, capture = _router(monkeypatch)
    router.create_message(_spec())
    router.stream_message(_spec(), lambda text: None)
    assert [s.system for s in capture.specs] == ["You are the Brain.", "You are the Brain."]
    assert [s.messages[-1]["content"] for s in capture.specs] == ["hi", "hi"]
