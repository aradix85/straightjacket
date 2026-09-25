from __future__ import annotations

import json
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from straightjacket.engine.ai.api_client import build_adapter, provider_named
from straightjacket.engine.ai.provider_base import AICallSpec, AIUnavailableError, create_with_retry, stream_with_retry
from straightjacket.engine.config_loader import ProviderConfig, cfg
from tests.elvira.elvira_bot.judge import CRITERIA, JUDGE_SCHEMA
from tests.modeltest.capture import scene_text


@dataclass(frozen=True)
class Voice:
    label: str
    provider: str
    model: str
    extra_body: dict[str, Any]


def voice_from(entry: dict[str, Any]) -> Voice:
    return Voice(entry["label"], entry["provider"], entry["model"], dict(entry["extra_body"]))


def contestants(names: list[str], settings: dict[str, Any]) -> list[Voice]:
    voices = []
    for name in names:
        if name == "current":
            cluster = cfg().ai.clusters["narrator"]
            voices.append(
                Voice(f"current narrator ({cluster.model})", cluster.provider, cluster.model, dict(cluster.extra_body))
            )
        else:
            voices.append(voice_from(settings["contestants"][name]))
    return voices


def judges_from(settings: dict[str, Any]) -> list[Voice]:
    return [voice_from(entry) for entry in settings["judges"]]


def adapter_for(provider: str, settings: dict[str, Any]) -> Any:
    if provider in settings["providers"]:
        return build_adapter(provider, ProviderConfig(**settings["providers"][provider]))
    return provider_named(provider)


def check_models(voices: list[Voice], settings: dict[str, Any]) -> None:
    offered: dict[str, set[str]] = {}
    for voice in voices:
        if voice.provider not in offered:
            offered[voice.provider] = set(adapter_for(voice.provider, settings).list_models())
    missing = [f"{v.provider}/{v.model}" for v in voices if v.model not in offered[v.provider]]
    if missing:
        raise SystemExit(f"Not offered by their provider: {', '.join(missing)}")


class _FirstText:
    def __init__(self, started: float) -> None:
        self.started = started
        self.first: float | None = None

    def feed(self, delta: str) -> None:
        if self.first is None and delta.strip():
            self.first = round(time.monotonic() - self.started, 2)

    def finish(self) -> None:
        return None

    def fail(self) -> None:
        self.first = None


def _cost(usage: dict[str, int], model: str, prices: dict[str, list[float]]) -> float:
    price_in, price_out = prices[model]
    return (usage["input_tokens"] * price_in + usage["output_tokens"] * price_out) / 1_000_000


def _generate(job: tuple[Voice, Any, str, dict[str, Any], int, dict[str, Any]]) -> dict[str, Any]:
    voice, adapter, name, scenario, attempt, settings = job
    spec = AICallSpec(
        model=voice.model,
        system=scenario["system"],
        messages=[{"role": "user", "content": scene_text(scenario["messages"])}],
        max_tokens=settings["narration_max_tokens"],
        max_retries=settings["max_retries"],
        extra_body=dict(voice.extra_body),
        log_role="narrator",
    )
    head = {"model": voice.label, "scenario": name, "attempt": attempt}
    started = time.monotonic()
    sink = _FirstText(started)
    try:
        response = stream_with_retry(adapter, spec, sink)
    except AIUnavailableError as e:
        return {**head, "error": str(e)}
    text = response.content.strip()
    return {
        **head,
        "text": text,
        "first_text": sink.first,
        "secs": round(time.monotonic() - started, 1),
        "cost": _cost(response.usage, voice.model, settings["prices"]),
        "words": len(text.split()),
    }


def _judge(job: tuple[Voice, Any, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
    judge, adapter, generation, scenario, settings, prompts = job
    user = prompts["judge_user"].format(scene=scene_text(scenario["messages"]), narration=generation["text"])
    spec = AICallSpec(
        model=judge.model,
        system=prompts["judge_system"],
        messages=[{"role": "user", "content": user}],
        max_tokens=settings["judge_max_tokens"],
        max_retries=settings["max_retries"],
        json_schema=JUDGE_SCHEMA,
        extra_body=dict(judge.extra_body),
        log_role="brain",
    )
    try:
        response = create_with_retry(adapter, spec)
        verdict = json.loads(response.content)
    except (AIUnavailableError, json.JSONDecodeError) as e:
        return {"judge": judge.label, "error": f"{type(e).__name__}: {e}"}
    return {"judge": judge.label, "cost": _cost(response.usage, judge.model, settings["prices"]), **verdict}


def measure(
    voices: list[Voice],
    scenarios: dict[str, dict[str, Any]],
    judges: list[Voice],
    settings: dict[str, Any],
    prompts: dict[str, Any],
    attempts: int,
) -> list[dict[str, Any]]:
    adapters = {voice.provider: adapter_for(voice.provider, settings) for voice in [*voices, *judges]}
    jobs = [
        (voice, adapters[voice.provider], name, scenario, attempt, settings)
        for voice in voices
        for name, scenario in scenarios.items()
        for attempt in range(1, attempts + 1)
    ]
    with ThreadPoolExecutor(max_workers=settings["workers"]) as pool:
        generations = list(pool.map(_generate, jobs))
    done = [g for g in generations if g.get("text")]
    judge_jobs = [
        (judge, adapters[judge.provider], g, scenarios[g["scenario"]], settings, prompts)
        for g in done
        for judge in judges
    ]
    with ThreadPoolExecutor(max_workers=settings["workers"]) as pool:
        verdicts = list(pool.map(_judge, judge_jobs))
    for index, generation in enumerate(done):
        generation["verdicts"] = verdicts[index * len(judges) : (index + 1) * len(judges)]
    return generations


def _mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 2) if values else None


def _valid_verdicts(generations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [v for g in generations for v in g["verdicts"] if "overall" in v]


def _errors(generations: list[dict[str, Any]], judged: list[dict[str, Any]]) -> int:
    return sum("error" in g for g in generations) + sum("error" in v for g in judged for v in g["verdicts"])


def _cost_per_100(generations: list[dict[str, Any]]) -> float | None:
    costs = [g["cost"] for g in generations if "cost" in g]
    return round(statistics.mean(costs) * 100, 3) if costs else None


def _judge_cost(judged: list[dict[str, Any]]) -> float:
    return round(sum(v["cost"] for g in judged for v in g["verdicts"] if "cost" in v), 3)


def _model_summary(generations: list[dict[str, Any]], miss_scenarios: set[str]) -> dict[str, Any]:
    judged = [g for g in generations if "verdicts" in g]
    scores = _valid_verdicts(judged)
    on_miss = _valid_verdicts([g for g in judged if g["scenario"] in miss_scenarios])
    return {
        "generations": len(generations),
        "errors": _errors(generations, judged),
        "overall": _mean([v["overall"] for v in scores]),
        **{criterion: _mean([v[criterion] for v in scores]) for criterion in CRITERIA},
        "integrity_on_miss": _mean([v["result_integrity"] for v in on_miss]),
        "first_text": _mean([g["first_text"] for g in judged if g.get("first_text") is not None]),
        "secs": _mean([g["secs"] for g in judged]),
        "words": _mean([g["words"] for g in judged]),
        "cost_per_100": _cost_per_100(generations),
        "judge_cost": _judge_cost(judged),
    }


def summarize(generations: list[dict[str, Any]], miss_scenarios: set[str]) -> dict[str, dict[str, Any]]:
    by_model: dict[str, list[dict[str, Any]]] = {}
    for generation in generations:
        if generation["model"] not in by_model:
            by_model[generation["model"]] = []
        by_model[generation["model"]].append(generation)
    return {model: _model_summary(items, miss_scenarios) for model, items in by_model.items()}


BOOTSTRAP_ROUNDS = 2000


def _narration_score(generation: dict[str, Any]) -> float | None:
    scores = [v["overall"] for v in generation.get("verdicts", []) if "overall" in v]
    return statistics.mean(scores) if scores else None


def _interval(values: list[float]) -> tuple[float, float] | None:
    if len(values) < 2:
        return None
    rng = random.Random(0)
    means = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(BOOTSTRAP_ROUNDS))
    return round(means[int(0.025 * BOOTSTRAP_ROUNDS)], 2), round(means[int(0.975 * BOOTSTRAP_ROUNDS) - 1], 2)


def intervals(generations: list[dict[str, Any]]) -> dict[str, tuple[float, float] | None]:
    by_model: dict[str, list[float]] = {}
    for generation in generations:
        score = _narration_score(generation)
        if score is not None:
            if generation["model"] not in by_model:
                by_model[generation["model"]] = []
            by_model[generation["model"]].append(score)
    return {model: _interval(values) for model, values in by_model.items()}


def compare(generations: list[dict[str, Any]], reference: str) -> dict[str, dict[str, Any]]:
    scores: dict[tuple[str, str, int], float] = {}
    for generation in generations:
        score = _narration_score(generation)
        if score is not None:
            scores[(generation["model"], generation["scenario"], generation["attempt"])] = score
    models = sorted({model for model, _, _ in scores if model != reference})
    result = {}
    for model in models:
        diffs = [
            score - scores[(reference, scene, attempt)]
            for (name, scene, attempt), score in scores.items()
            if name == model and (reference, scene, attempt) in scores
        ]
        if diffs:
            result[model] = {
                "diff": round(statistics.mean(diffs), 2),
                "interval": _interval(diffs),
                "pairs": len(diffs),
            }
    return result


def _verdict(entry: dict[str, Any]) -> str:
    low_high = entry["interval"]
    if low_high is None:
        return "too few pairs to tell"
    if low_high[0] > 0:
        return "better"
    if low_high[1] < 0:
        return "worse"
    return "not distinguishable"


def _comparison_lines(comparison: dict[str, dict[str, Any]], reference: str) -> list[str]:
    lines = [f"# Compared with {reference}, scene by scene", ""]
    for model, entry in comparison.items():
        lines.append(
            f"- {model}: {entry['diff']:+} (95% interval {entry['interval']}, {entry['pairs']} pairs): {_verdict(entry)}"
        )
    return [*lines, ""]


def _summary_lines(summary: dict[str, dict[str, Any]]) -> list[str]:
    lines = []
    for model, s in summary.items():
        lines += [
            f"## {model}",
            "",
            f"Overall: {s['overall']} out of 10, over {s['generations']} narrations ({s['errors']} errors); 95% interval {s.get('interval')}.",
            f"Result integrity on a miss: {s['integrity_on_miss']} out of 5.",
            *[f"- {criterion}: {s[criterion]} out of 5" for criterion in CRITERIA],
            f"Speed: first text after {s['first_text']} seconds, whole narration {s['secs']} seconds, {s['words']} words.",
            f"Price: about ${s['cost_per_100']} per 100 narrations; judging this run cost ${s['judge_cost']}.",
            "",
        ]
    return lines


def report(
    summary: dict[str, dict[str, Any]],
    baseline: dict[str, dict[str, Any]],
    stamp: str,
    comparison: dict[str, dict[str, Any]],
    reference: str,
) -> str:
    lines = [f"# Model test {stamp}", "", *_summary_lines(summary)]
    if comparison:
        lines += _comparison_lines(comparison, reference)
    lines += ["# Baseline", "", *_summary_lines(baseline)]
    return "\n".join(lines)
