import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse

MODELTEST = Path(__file__).resolve().parent / "modeltest"


def _yaml(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load((MODELTEST / name).read_text(encoding="utf-8"))
    return loaded


def _stored(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((MODELTEST / "scenarios" / f"{name}.json").read_text(encoding="utf-8"))
    return loaded


def _first_contestant(settings: dict[str, Any]) -> tuple[str, str]:
    from tests.modeltest import measure as m

    return "current", m.contestants(["current"], settings)[0].label


class _FakeAdapter:
    def create_message(self, spec: AICallSpec) -> AIResponse:
        if spec.json_schema:
            criteria = _yaml("modeltest_config.yaml")["criteria"]
            verdict = {**dict.fromkeys(criteria, 4), "overall": 8, "weakness": "none"}
            return AIResponse(content=json.dumps(verdict), usage={"input_tokens": 1000, "output_tokens": 100})
        return AIResponse(content="You leap. The ledge crumbles.", usage={"input_tokens": 2000, "output_tokens": 50})


class _DownAdapter:
    def create_message(self, spec: AICallSpec) -> AIResponse:
        raise RuntimeError("provider down")


@pytest.mark.parametrize("name", sorted(p.stem for p in (MODELTEST / "scenarios").glob("*.json")))
def test_the_stored_scene_matches_the_current_engine(load_engine: None, name: str) -> None:
    from tests.modeltest.capture import capture_scenario

    definitions = _yaml("modeltest_scenarios.yaml")
    settings = _yaml("modeltest_config.yaml")
    captured = capture_scenario(
        definitions["scenarios"][name], definitions["common"], settings["seed_limit"], settings["narration_lang"]
    )
    assert captured == _stored(name)


def test_a_captured_miss_carries_its_result_tag(load_engine: None) -> None:
    from tests.modeltest.capture import scene_text

    stored = _stored("danger_miss")
    assert stored["result"] == "MISS"
    assert '<result type="MISS"' in scene_text(stored["messages"])


def test_every_narration_is_judged_and_summarized(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.modeltest import measure as m

    monkeypatch.setattr(m, "provider_named", lambda name: _FakeAdapter())
    monkeypatch.setattr(m, "build_adapter", lambda name, config: _FakeAdapter())
    settings = _yaml("modeltest_config.yaml")
    name, label = _first_contestant(settings)
    scenarios = {scene: _stored(scene) for scene in ("danger_miss", "dialog")}
    generations = m.measure(
        m.contestants([name], settings),
        scenarios,
        m.judges_from(settings),
        settings,
        _yaml("modeltest_prompts.yaml"),
        2,
    )
    assert len(generations) == 4
    assert all(len(g["verdicts"]) == len(settings["judges"]) for g in generations)
    summary = m.summarize(generations, {"danger_miss"}, settings["criteria"])[label]
    assert (summary["overall"], summary["integrity_on_miss"], summary["errors"]) == (8, 4, 0)
    per_verdict = sum(
        1000 * settings["prices"][j["model"]][0] + 100 * settings["prices"][j["model"]][1] for j in settings["judges"]
    )
    assert summary["judge_cost"] == pytest.approx(4 * per_verdict / 1_000_000, abs=0.001)
    from straightjacket.engine.config_loader import model_for_role

    price_in, price_out = settings["prices"][model_for_role("narrator")]
    assert summary["cost_per_100"] == pytest.approx(100 * (2000 * price_in + 50 * price_out) / 1_000_000, abs=0.001)
    assert summary["first_text"] is not None
    assert f"## {label}" in m.report(
        {label: summary}, {}, "test", {}, "", settings["criteria"], m.per_judge(generations)
    )


def test_a_failed_narration_is_recorded_not_judged(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.modeltest import measure as m

    monkeypatch.setattr(m, "provider_named", lambda name: _DownAdapter())
    monkeypatch.setattr(m, "build_adapter", lambda name, config: _DownAdapter())
    settings = _yaml("modeltest_config.yaml")
    name, label = _first_contestant(settings)
    generations = m.measure(
        m.contestants([name], settings),
        {"dialog": _stored("dialog")},
        m.judges_from(settings),
        settings,
        _yaml("modeltest_prompts.yaml"),
        1,
    )
    assert "provider down" in generations[0]["error"]
    summary = m.summarize(generations, set(), settings["criteria"])[label]
    assert (summary["errors"], summary["overall"]) == (1, None)


def test_the_comparison_tells_a_real_difference_from_chance() -> None:
    from tests.modeltest.measure import compare, intervals, report

    def narration(model: str, scene: str, overall: int) -> dict[str, Any]:
        return {
            "model": model,
            "scenario": scene,
            "attempt": 1,
            "verdicts": [{"overall": overall}, {"overall": overall}],
        }

    generations = []
    for index in range(20):
        generations.append(narration("Reference", f"s{index}", 6))
        generations.append(narration("Better", f"s{index}", 8))
        generations.append(narration("Same", f"s{index}", 7 if index % 2 else 5))
    comparison = compare(generations, "Reference")
    assert comparison["Better"]["diff"] == 2
    assert comparison["Better"]["interval"][0] > 0
    assert comparison["Same"]["diff"] == 0
    assert comparison["Same"]["interval"][0] < 0 < comparison["Same"]["interval"][1]
    assert intervals(generations)["Reference"] == (6, 6)
    text = report({}, {}, "test", comparison, "Reference", [], {})
    assert "Better: +2" in text
    assert ": better" in text
    assert "Same: +0" in text
    assert "not distinguishable" in text


def test_rejudging_replaces_every_verdict(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.modeltest import measure as m

    monkeypatch.setattr(m, "provider_named", lambda name: _FakeAdapter())
    monkeypatch.setattr(m, "build_adapter", lambda name, config: _FakeAdapter())
    settings = _yaml("modeltest_config.yaml")
    old = [
        {
            "model": "A",
            "scenario": "dialog",
            "attempt": 1,
            "text": "Words.",
            "verdicts": [{"judge": "old", "overall": 1}],
        },
        {"model": "A", "scenario": "dialog", "attempt": 2, "error": "down"},
    ]
    judged = m.judge_all(
        old, {"dialog": _stored("dialog")}, m.judges_from(settings), settings, _yaml("modeltest_prompts.yaml")
    )
    assert [v["judge"] for v in judged[0]["verdicts"]] == [j["label"] for j in settings["judges"]]
    assert all(v["overall"] == 8 for v in judged[0]["verdicts"])
    assert "verdicts" not in judged[1]
    assert old[0]["verdicts"] == [{"judge": "old", "overall": 1}]
    assert m.per_judge(judged) == {"A": {j["label"]: 8 for j in settings["judges"]}}
