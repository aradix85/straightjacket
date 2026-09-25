from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

from straightjacket.engine.ai.provider_base import AICallSpec, AIProvider, AIResponse

ALL_ROLES = frozenset({"*"})


class ModelSwap:
    def __init__(
        self, inner: AIProvider, target: Any, model: str, extra_body: dict[str, Any], roles: frozenset[str]
    ) -> None:
        self.inner = inner
        self._target = target
        self._model = model
        self._extra_body = extra_body
        self._roles = roles

    def _applies(self, spec: AICallSpec) -> bool:
        return self._roles == ALL_ROLES or spec.log_role in self._roles

    def _swapped(self, spec: AICallSpec) -> AICallSpec:
        return dataclasses.replace(spec, model=self._model, extra_body=dict(self._extra_body))

    def create_message(self, spec: AICallSpec) -> AIResponse:
        if self._applies(spec):
            response: AIResponse = self._target.create_message(self._swapped(spec))
            return response
        return self.inner.create_message(spec)

    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse:
        if self._applies(spec):
            swapped: AIResponse = self._target.stream_message(self._swapped(spec), on_text)
            return swapped
        stream: Any = self.inner.stream_message
        response: AIResponse = stream(spec, on_text)
        return response


class NarratorSwap(ModelSwap):
    def __init__(self, inner: AIProvider, narrator: Any, model: str, extra_body: dict[str, Any]) -> None:
        super().__init__(inner, narrator, model, extra_body, frozenset({"narrator"}))
