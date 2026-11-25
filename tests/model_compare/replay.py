from __future__ import annotations

import json
import os
import secrets
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, TypeVar

from typing_extensions import override

from straightjacket.engine.ai.api_client import RoutingProvider
from straightjacket.engine.ai.provider_anthropic import AnthropicProvider
from straightjacket.engine.ai.provider_base import AIUnavailableError, create_with_retry, stream_with_retry
from straightjacket.engine.ai.sentence_stream import SentenceStream
from straightjacket.engine.config_loader import cfg
from straightjacket.engine.serialization import build_strict, read_key, serialize
from tests.model_compare.calls import read_calls

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from anthropic.types import Message

    from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse, ModelListingProvider
    from tests.model_compare.calls import CapturedCall
    from tests.model_compare.settings import Configuration, Price

CALLS = "calls.jsonl"
ANSWERS = "answers.jsonl"
KEY = "key.jsonl"
MEASURES = "measures.jsonl"

_R = TypeVar("_R", "Answer", "KeyEntry", "Measure")


@dataclass(frozen=True)
class Attempt:
    seconds: float
    first_text: float | None
    uncached_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    output_tokens: int
    thinking_tokens: int
    speed: str | None


@dataclass(frozen=True)
class Answer:
    code: str
    call: str
    role: str
    content: str
    stop_reason: str


@dataclass(frozen=True)
class KeyEntry:
    code: str
    configuration: str
    replicate: int


@dataclass(frozen=True)
class Measure:
    code: str
    attempts: list[Attempt]
    error: str


@dataclass
class Round:
    answered: int
    failed: int
    truncated: int
    cost: float
    codes: set[str]


class MeasuredProvider(AnthropicProvider):
    def __init__(self, api_key: str, timeout_seconds: float, api_base: str) -> None:
        super().__init__(api_key=api_key, timeout_seconds=timeout_seconds, api_base=api_base)
        self.attempts: list[Attempt] = []

    @override
    def create_message(self, spec: AICallSpec) -> AIResponse:
        started = time.monotonic()
        return self._measured(self._client.messages.create(**self._request(spec)), started, None)

    @override
    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse:
        started = time.monotonic()
        first_text: float | None = None
        with self._client.messages.stream(**self._request(spec)) as stream:
            for event in stream:
                if event.type == "content_block_delta" and event.delta.type == "text_delta":
                    first_text = time.monotonic() - started if first_text is None else first_text
                    on_text(event.delta.text)
            final = stream.get_final_message()
        return self._measured(final, started, first_text)

    def _measured(self, message: Message, started: float, first_text: float | None) -> AIResponse:
        usage = message.usage
        self.attempts.append(
            Attempt(
                seconds=time.monotonic() - started,
                first_text=first_text,
                uncached_tokens=usage.input_tokens,
                cache_write_tokens=usage.cache_creation_input_tokens or 0,
                cache_read_tokens=usage.cache_read_input_tokens or 0,
                output_tokens=usage.output_tokens,
                thinking_tokens=usage.output_tokens_details.thinking_tokens if usage.output_tokens_details else 0,
                speed=usage.speed,
            )
        )
        return self._response(message)


def configured(spec: AICallSpec, configuration: Configuration) -> AICallSpec:
    extra = dict(spec.sampling["extra_body"])
    output_config = read_key(extra, "output_config", dict, f"{spec.log_role}.extra_body")
    extra["output_config"] = {**output_config, "effort": configuration.effort}
    if configuration.fast:
        extra["speed"] = "fast"
    return replace(spec, model=configuration.model, sampling={**spec.sampling, "extra_body": extra})


def cost(attempt: Attempt, prices: dict[str, dict[str, Price]], model: str) -> float:
    price = prices[model]["fast" if attempt.speed == "fast" else "standard"]
    return (
        attempt.uncached_tokens * price.uncached
        + attempt.cache_write_tokens * price.cache_write
        + attempt.cache_read_tokens * price.cache_read
        + attempt.output_tokens * price.output
    ) / 1_000_000


def replay(
    run_dir: Path,
    configurations: dict[str, Configuration],
    prices: dict[str, dict[str, Price]],
    selection: Callable[[CapturedCall], bool],
    *,
    again: bool,
) -> Round:
    calls = [c for c in read_calls(run_dir / CALLS) if c.stop_reason != "refusal" and selection(c)]
    answers = read_jsonl(run_dir / ANSWERS, Answer)
    call_of = {a.code: a.call for a in answers}
    done = Counter((call_of[k.code], k.configuration) for k in read_jsonl(run_dir / KEY, KeyEntry))
    work = {name: [c for c in calls if again or not done[c.call_id, name]] for name in configurations}
    progress = Round(answered=0, failed=0, truncated=0, cost=0.0, codes={a.code for a in answers})
    lock = threading.Lock()

    def play(name: str) -> None:
        configuration = configurations[name]
        measured = _measured_provider()
        adapters: dict[str, ModelListingProvider] = dict.fromkeys(cfg().ai.providers, measured)
        router = RoutingProvider(adapters)
        for call in work[name]:
            response, error = _replay_one(router, configured(call.spec, configuration), streamed=call.streamed)
            if configuration.fast and any(a.speed != "fast" for a in measured.attempts):
                msg = f"{call.call_id}: fast mode was asked but not applied"
                raise RuntimeError(msg)
            with lock:
                code = _new_code(progress.codes)
                _write(
                    run_dir,
                    Answer(code, call.call_id, call.spec.log_role, _content(response), _stop(response)),
                    KeyEntry(code, name, done[call.call_id, name] + 1),
                    Measure(code, measured.attempts, error),
                )
                done[call.call_id, name] += 1
                progress.answered += 1
                progress.failed += int(response is None)
                progress.truncated += int(response is not None and response.stop_reason == "truncated")
                progress.cost += sum(cost(a, prices, configuration.model) for a in measured.attempts)
            measured.attempts = []

    with ThreadPoolExecutor(max_workers=len(configurations)) as pool:
        for finished in [pool.submit(play, name) for name in configurations]:
            finished.result()
    return progress


def _measured_provider() -> MeasuredProvider:
    (provider,) = cfg().ai.providers.values()
    return MeasuredProvider(
        api_key=os.environ[provider.api_key_env], timeout_seconds=provider.timeout_seconds, api_base=provider.api_base
    )


def _replay_one(router: RoutingProvider, spec: AICallSpec, *, streamed: bool) -> tuple[AIResponse | None, str]:
    try:
        if streamed:
            return stream_with_retry(router, spec, SentenceStream(lambda _sentence: None)), ""
        return create_with_retry(router, spec), ""
    except AIUnavailableError as e:
        return None, str(e)


def _content(response: AIResponse | None) -> str:
    if response is None:
        return ""
    calls = [f"[tool call] {c.name}({json.dumps(c.arguments, ensure_ascii=False)})" for c in response.tool_calls]
    return "\n".join([response.content, *calls]).strip()


def _stop(response: AIResponse | None) -> str:
    return "failed" if response is None else response.stop_reason


def _new_code(taken: set[str]) -> str:
    code = secrets.token_hex(3)
    while code in taken:
        code = secrets.token_hex(3)
    taken.add(code)
    return code


def _write(run_dir: Path, answer: Answer, key: KeyEntry, measure: Measure) -> None:
    for name, record in ((ANSWERS, answer), (KEY, key), (MEASURES, measure)):
        with (run_dir / name).open("a", encoding="utf-8") as out:
            out.write(json.dumps(serialize(record), ensure_ascii=False) + "\n")


def read_jsonl(path: Path, kind: type[_R]) -> list[_R]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [build_strict(kind, json.loads(line), f"{path.name}:{n}") for n, line in enumerate(lines)]
