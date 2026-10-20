from __future__ import annotations

from collections.abc import Callable

from straightjacket.engine.ai.provider_base import AICallSpec, AIProvider, AIResponse


class TokenMeter:
    def __init__(self, inner: AIProvider) -> None:
        self._inner = inner
        self._usage: list[dict[str, str | int]] = []
        self.narrator_prompt = ""

    def create_message(self, spec: AICallSpec) -> AIResponse:
        self._note(spec)
        return self._count(spec, self._inner.create_message(spec))

    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse:
        self._note(spec)
        return self._count(spec, self._inner.stream_message(spec, on_text))

    def drain(self) -> list[dict[str, str | int]]:
        usage, self._usage = self._usage, []
        return usage

    def _note(self, spec: AICallSpec) -> None:
        if spec.log_role == "narrator":
            self.narrator_prompt = str(spec.messages[-1]["content"])

    def _count(self, spec: AICallSpec, response: AIResponse) -> AIResponse:
        if response.usage:
            self._usage.append(
                {
                    "role": spec.log_role,
                    "input": response.usage["input_tokens"],
                    "output": response.usage["output_tokens"],
                }
            )
        return response
