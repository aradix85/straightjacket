from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

from straightjacket.engine.ai.provider_base import AICallSpec, AIProvider, AIResponse


class NarratorSwap:
    def __init__(self, inner: AIProvider, narrator: Any, model: str, extra_body: dict[str, Any]) -> None:
        self._inner = inner
        self._narrator = narrator
        self._model = model
        self._extra_body = extra_body

    def _swapped(self, spec: AICallSpec) -> AICallSpec:
        return dataclasses.replace(spec, model=self._model, extra_body=dict(self._extra_body))

    def create_message(self, spec: AICallSpec) -> AIResponse:
        if spec.log_role == "narrator":
            response: AIResponse = self._narrator.create_message(self._swapped(spec))
            return response
        return self._inner.create_message(spec)

    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse:
        if spec.log_role == "narrator":
            swapped: AIResponse = self._narrator.stream_message(self._swapped(spec), on_text)
            return swapped
        stream: Any = self._inner.stream_message
        response: AIResponse = stream(spec, on_text)
        return response
