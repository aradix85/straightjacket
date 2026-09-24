import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse
from tests.elvira.elvira_bot.judge import CRITERIA

MODELTEST = Path(__file__).resolve().parent / "modeltest"


def _yaml(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load((MODELTEST / name).read_text(encoding="utf-8"))
    return loaded


def _stored(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((MODELTEST / "scenarios" / f"{name}.json").read_text(encoding="utf-8"))
    return loaded


def _first_contestant(settings: dict[str, Any]) -> tuple[str, str]:
    name = next(iter(settings["contestants"]))
    return name, settings["contestants"][name]["label"]


class _FakeAdapter:
    def create_message(self, spec: AICallSpec) -> AIResponse:
        if spec.json_schema:
            verdict = {**dict.fromkeys(CRITERIA, 4), "overall": 8, "weakness": "none"}
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
    assert all(len(g["verdicts"]) == 2 for g in generations)
    summary = m.summarize(generations, {"danger_miss"})[label]
    assert (summary["overall"], summary["integrity_on_miss"], summary["errors"]) == (8, 4, 0)
    assert summary["judge_cost"] == 0.024
    assert summary["cost_per_100"] == pytest.approx(0.0225, abs=0.001)
    assert summary["first_text"] is not None
    assert f"## {label}" in m.report({label: summary}, {}, "test")


def test_a_failed_narration_is_recorded_not_judged(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.modeltest import measure as m

    monkeypatch.setattr(m, "provider_named", lambda name: _DownAdapter())
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
    summary = m.summarize(generations, set())[label]
    assert (summary["errors"], summary["overall"]) == (1, None)
