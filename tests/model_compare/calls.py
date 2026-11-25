from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from straightjacket.engine.ai.provider_base import AICallSpec
from straightjacket.engine.serialization import build_strict, read_key, read_optional_key, serialize
from straightjacket.engine.tools import ToolDefinition

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from straightjacket.engine.ai.provider_base import AIProvider, AIResponse, Message
    from straightjacket.engine.config_loader import SamplingParams


@dataclass(frozen=True)
class CapturedCall:
    source: str
    index: int
    streamed: bool
    spec: AICallSpec
    answer: str
    stop_reason: str

    @property
    def call_id(self) -> str:
        return f"{self.source}-{self.index:03d}"


class RecordingProvider:
    def __init__(self, inner: AIProvider, path: Path, source: str) -> None:
        self._inner = inner
        self._path = path
        self._source = source
        self._count = 0
        self._lock = threading.Lock()

    def create_message(self, spec: AICallSpec) -> AIResponse:
        return self._record(spec, lambda: self._inner.create_message(spec), streamed=False)

    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse:
        return self._record(spec, lambda: self._inner.stream_message(spec, on_text), streamed=True)

    def _record(self, spec: AICallSpec, call: Callable[[], AIResponse], *, streamed: bool) -> AIResponse:
        response = call()
        with self._lock:
            captured = CapturedCall(
                source=self._source,
                index=self._count,
                streamed=streamed,
                spec=spec,
                answer=response.content,
                stop_reason=response.stop_reason,
            )
            self._count += 1
            with self._path.open("a", encoding="utf-8") as out:
                out.write(json.dumps(serialize(captured), ensure_ascii=False) + "\n")
        return response


def read_calls(path: Path) -> list[CapturedCall]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [
        build_strict(CapturedCall, json.loads(line), f"{path.name}:{n}", spec=_spec) for n, line in enumerate(lines)
    ]


def _spec(data: object, where: str) -> AICallSpec:
    tools = read_optional_key(data, "tools", list, where)
    return AICallSpec(
        model=read_key(data, "model", str, where),
        system=read_key(data, "system", str, where),
        messages=[_message(m, f"{where}.messages[{i}]") for i, m in enumerate(read_key(data, "messages", list, where))],
        sampling=_sampling(read_key(data, "sampling", dict, where), f"{where}.sampling"),
        json_schema=read_optional_key(data, "json_schema", dict, where),
        tools=None if tools is None else [build_strict(ToolDefinition, t, f"{where}.tools") for t in tools],
        log_role=read_key(data, "log_role", str, where),
        cached_system_prefix=read_key(data, "cached_system_prefix", str, where),
    )


def _message(data: object, where: str) -> Message:
    return {"role": _role(read_key(data, "role", str, where), where), "content": read_key(data, "content", str, where)}


def _role(value: str, where: str) -> Literal["user", "assistant"]:
    if value == "user":
        return "user"
    if value == "assistant":
        return "assistant"
    msg = f"{where}.role: expected user or assistant, got {value!r}"
    raise ValueError(msg)


def _sampling(data: object, where: str) -> SamplingParams:
    return {
        "max_tokens": read_key(data, "max_tokens", int, where),
        "max_retries": read_key(data, "max_retries", int, where),
        "temperature": read_optional_key(data, "temperature", float, where),
        "top_p": read_optional_key(data, "top_p", float, where),
        "extra_body": read_key(data, "extra_body", dict, where),
    }
