from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from typing_extensions import override

from straightjacket.engine.ai.provider_base import AIResponse
from straightjacket.engine.ai.sentence_stream import SentenceStream
from straightjacket.engine.config_loader import cfg
from straightjacket.engine.game import process_turn
from tests._creation import TurnProvider, brain_answer, force_result, library_game
from tests._helpers import make_ai_call_spec
from tests._mocks import MockProvider
from tests.model_compare import replay as replay_module
from tests.model_compare.calls import RecordingProvider, read_calls
from tests.model_compare.judging import SCORES, read_scores, write_packets, write_summary
from tests.model_compare.replay import (
    ANSWERS,
    CALLS,
    KEY,
    Answer,
    Attempt,
    KeyEntry,
    MeasuredProvider,
    configured,
    read_jsonl,
    replay,
)
from tests.model_compare.settings import Configuration, Price, load_settings

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from straightjacket.engine.ai.provider_base import AICallSpec

_SONNET = Configuration(model="model-s", effort="medium", fast=False)
_OPUS_FAST = Configuration(model="model-o", effort="high", fast=True)
_CONFIGURATIONS = {"s_medium": _SONNET, "o_fast": _OPUS_FAST}


class _Measured(MeasuredProvider):
    def __init__(self, speed: str) -> None:
        super().__init__(api_key="k", timeout_seconds=30, api_base="")
        self._speed = speed
        self.models: list[str] = []

    @override
    def create_message(self, spec: AICallSpec) -> AIResponse:
        self.models.append(spec.model)
        self.attempts.append(
            Attempt(
                seconds=1.5,
                first_text=None,
                uncached_tokens=1_000_000,
                cache_write_tokens=0,
                cache_read_tokens=0,
                output_tokens=0,
                thinking_tokens=0,
                speed=self._speed,
            )
        )
        return AIResponse(content=f"{spec.log_role} answer", usage={"input_tokens": 1, "output_tokens": 1})

    @override
    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse:
        response = self.create_message(spec)
        on_text(response.content)
        return response


def _captured(path: Path) -> None:
    recorder = RecordingProvider(MockProvider("ok"), path, "src")
    recorder.stream_message(make_ai_call_spec(extra_body={"output_config": {"effort": "medium"}}), lambda _t: None)
    recorder.create_message(
        make_ai_call_spec(
            log_role="brain",
            messages=[{"role": "user", "content": "I leap the gorge"}],
            extra_body={"output_config": {"effort": "medium"}, "cache_control": {"type": "ephemeral"}},
        )
    )


def _measure_with(monkeypatch: pytest.MonkeyPatch, speed: str) -> list[_Measured]:
    made: list[_Measured] = []

    def provider() -> _Measured:
        made.append(_Measured(speed))
        return made[-1]

    monkeypatch.setattr(replay_module, "_measured_provider", provider)
    return made


def _prices() -> dict[str, dict[str, Price]]:
    price = Price(uncached=2.0, cache_write=4.0, cache_read=0.1, output=10.0)
    return {"model-s": {"standard": price, "fast": price}, "model-o": {"standard": price, "fast": price}}


def test_a_turn_played_through_the_recorder_is_captured_whole(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    game = library_game()
    force_result(monkeypatch, "MISS")
    inner = TurnProvider(brain_answer())
    path = tmp_path / CALLS
    process_turn(RecordingProvider(inner, path, "run"), game, "I leap the gorge", SentenceStream(lambda _s: None))
    calls = read_calls(path)
    assert [c.spec for c in calls] == inner.calls
    assert [c.call_id for c in calls] == [f"run-{i:03d}" for i in range(len(calls))]
    assert {c.spec.log_role: c.streamed for c in calls}["narrator"]
    assert not any(c.streamed for c in calls if c.spec.log_role != "narrator")
    assert {c.spec.log_role for c in calls} >= {"brain", "narrator", "narrator_metadata"}


def test_a_configuration_changes_only_the_model_effort_and_speed() -> None:
    spec = make_ai_call_spec(extra_body={"output_config": {"effort": "medium"}, "cache_control": {"type": "ephemeral"}})
    changed = configured(spec, _OPUS_FAST)
    assert changed.model == "model-o"
    assert changed.sampling["extra_body"] == {
        "output_config": {"effort": "high"},
        "cache_control": {"type": "ephemeral"},
        "speed": "fast",
    }
    assert (changed.system, changed.messages, changed.json_schema, changed.log_role) == (
        spec.system,
        spec.messages,
        spec.json_schema,
        spec.log_role,
    )
    assert "speed" not in configured(spec, _SONNET).sampling["extra_body"]


def test_every_captured_call_is_answered_once_per_configuration_under_a_code_of_its_own(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _captured(tmp_path / CALLS)
    made = _measure_with(monkeypatch, "fast")
    done = replay(tmp_path, _CONFIGURATIONS, _prices(), lambda _c: True, again=False)
    answers = read_jsonl(tmp_path / ANSWERS, Answer)
    key = {k.code: k for k in read_jsonl(tmp_path / KEY, KeyEntry)}
    assert (done.answered, done.failed, done.truncated) == (4, 0, 0)
    assert done.cost == pytest.approx(8.0)
    assert len({a.code for a in answers}) == 4
    assert sorted((a.call, key[a.code].configuration) for a in answers) == [
        ("src-000", "o_fast"),
        ("src-000", "s_medium"),
        ("src-001", "o_fast"),
        ("src-001", "s_medium"),
    ]
    assert sorted(m for provider in made for m in provider.models) == ["model-o", "model-o", "model-s", "model-s"]
    assert not any("model-" in line or "medium" in line for line in (tmp_path / ANSWERS).read_text().splitlines())


def test_a_second_round_answers_only_what_is_new_unless_asked_again(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _captured(tmp_path / CALLS)
    _measure_with(monkeypatch, "fast")
    replay(tmp_path, _CONFIGURATIONS, _prices(), lambda c: c.call_id == "src-000", again=False)
    assert replay(tmp_path, _CONFIGURATIONS, _prices(), lambda _c: True, again=False).answered == 2
    assert replay(tmp_path, {"s_medium": _SONNET}, _prices(), lambda _c: True, again=True).answered == 2
    replicates = sorted((k.configuration, k.replicate) for k in read_jsonl(tmp_path / KEY, KeyEntry))
    assert replicates == [
        ("o_fast", 1),
        ("o_fast", 1),
        ("s_medium", 1),
        ("s_medium", 1),
        ("s_medium", 2),
        ("s_medium", 2),
    ]


def test_fast_mode_that_the_answer_does_not_report_stops_the_round(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _captured(tmp_path / CALLS)
    _measure_with(monkeypatch, "standard")
    with pytest.raises(RuntimeError, match="fast mode was asked but not applied"):
        replay(tmp_path, {"o_fast": _OPUS_FAST}, _prices(), lambda _c: True, again=False)


def test_a_packet_shows_the_request_and_every_answer_by_code_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _captured(tmp_path / CALLS)
    _measure_with(monkeypatch, "fast")
    replay(tmp_path, _CONFIGURATIONS, _prices(), lambda _c: True, again=False)
    assert write_packets(tmp_path, {"common": "Judge blind.", "narrator": "softened", "brain": "move"}) == 2
    packet = (tmp_path / "packets" / "brain" / "src-001.md").read_text(encoding="utf-8")
    codes = [a.code for a in read_jsonl(tmp_path / ANSWERS, Answer) if a.call == "src-001"]
    assert "I leap the gorge" in packet
    assert all(f"## Answer {code}" in packet for code in codes)
    assert not any(word in packet for word in ("s_medium", "o_fast", "model-s", "model-o"))
    assert (tmp_path / "packets" / "brain" / "RUBRIC.md").read_text(encoding="utf-8") == "Judge blind.\nmove"


def _score_all(tmp_path: Path, values: Callable[[str], dict[str, object]]) -> None:
    (tmp_path / SCORES).mkdir()
    lines = [
        json.dumps({"code": a.code, "scores": values(a.role), "note": ""})
        for a in read_jsonl(tmp_path / ANSWERS, Answer)
    ]
    (tmp_path / SCORES / "judge.jsonl").write_text("\n".join(lines), encoding="utf-8")


def test_the_summary_averages_the_scores_and_sums_the_cost_per_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _captured(tmp_path / CALLS)
    _measure_with(monkeypatch, "fast")
    replay(tmp_path, _CONFIGURATIONS, _prices(), lambda _c: True, again=False)
    _score_all(tmp_path, lambda role: {"softened": False, "prose": 4} if role == "narrator" else {"move": 1})
    summary = write_summary(tmp_path, _CONFIGURATIONS, _prices())
    assert "| s_medium | 1 | 4.00 (1) | 0.00 (1) |" in summary
    assert "| o_fast | 1 | 1.00 (1) |" in summary
    assert "| s_medium | 2000000 | 0 | 0 | $4.00 |" in summary


def test_the_summary_refuses_an_answer_without_a_score(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _captured(tmp_path / CALLS)
    _measure_with(monkeypatch, "fast")
    replay(tmp_path, _CONFIGURATIONS, _prices(), lambda _c: True, again=False)
    (tmp_path / SCORES).mkdir()
    (tmp_path / SCORES / "judge.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="4 answers have no score yet"):
        write_summary(tmp_path, _CONFIGURATIONS, _prices())


@pytest.mark.parametrize(
    ("lines", "named"),
    [
        (['{"code": "a1", "scores": {"prose": "good"}, "note": ""}'], "expected numbers"),
        (['{"code": "a1", "scores": {}, "note": ""}', '{"code": "a1", "scores": {}, "note": ""}'], "scored twice"),
    ],
)
def test_a_score_that_is_no_number_or_comes_twice_is_refused(tmp_path: Path, lines: list[str], named: str) -> None:
    (tmp_path / SCORES).mkdir()
    (tmp_path / SCORES / "judge.jsonl").write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(ValueError, match=named):
        read_scores(tmp_path)


def test_the_shipped_comparison_prices_every_configuration_and_has_a_rubric_for_every_role() -> None:
    settings = load_settings()
    for configuration in settings.configurations.values():
        assert "fast" in settings.prices[configuration.model] or not configuration.fast
        assert "standard" in settings.prices[configuration.model]
    assert set(cfg().ai.role_cluster) <= set(settings.rubrics)
