from __future__ import annotations

from collections.abc import Callable
from typing import Any

from straightjacket.engine.ai.provider_base import AICallSpec, AIProvider, AIResponse

INJECTED = "injected narrator outage"


class NarratorOutage:
    def __init__(self, inner: AIProvider) -> None:
        self._inner = inner

    def create_message(self, spec: AICallSpec) -> AIResponse:
        if spec.log_role == "narrator":
            raise RuntimeError(INJECTED)
        return self._inner.create_message(spec)

    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse:
        if spec.log_role == "narrator":
            raise RuntimeError(INJECTED)
        stream: Any = self._inner.stream_message
        response: AIResponse = stream(spec, on_text)
        return response
