from __future__ import annotations

import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from straightjacket.engine.ai.api_client import provider_named
from straightjacket.engine.ai.provider_base import AICallSpec, AIUnavailableError, create_with_retry
from straightjacket.engine.config_loader import cfg
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


def check_models(voices: list[Voice]) -> None:
    offered: dict[str, set[str]] = {}
    for voice in voices:
        if voice.provider not in offered:
            offered[voice.provider] = set(provider_named(voice.provider).list_models())
    missing = [f"{v.provider}/{v.model}" for v in voices if v.model not in offered[v.provider]]
    if missing:
        raise SystemExit(f"Not offered by their provider: {', '.join(missing)}")


def _cost(usage: dict[str, int], model: str, prices: dict[str, list[float]]) -> float:
    price_in, price_out = prices[model]
    return (usage["input_tokens"] * price_in + usage["output_tokens"] * price_out) / 1_000_000


def _generate(job: tuple[Voice, str, dict[str, Any], int, dict[str, Any]]) -> dict[str, Any]:
    voice, name, scenario, attempt, settings = job
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
    try:
        response = create_with_retry(provider_named(voice.provider), spec)
    except AIUnavailableError as e:
        return {**head, "error": str(e)[:200]}
    text = response.content.strip()
    return {
        **head,
        "text": text,
        "secs": round(time.monotonic() - started, 1),
        "cost": _cost(response.usage, voice.model, settings["prices"]),
        "words": len(text.split()),
    }


def _judge(job: tuple[Voice, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
    judge, generation, scenario, settings, prompts = job
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
        response = create_with_retry(provider_named(judge.provider), spec)
        verdict = json.loads(response.content)
    except (AIUnavailableError, json.JSONDecodeError) as e:
        return {"judge": judge.label, "error": f"{type(e).__name__}: {e}"[:200]}
    return {"judge": judge.label, "cost": _cost(response.usage, judge.model, settings["prices"]), **verdict}


def measure(
    voices: list[Voice],
    scenarios: dict[str, dict[str, Any]],
    judges: list[Voice],
    settings: dict[str, Any],
    prompts: dict[str, Any],
    attempts: int,
) -> list[dict[str, Any]]:
    jobs = [
        (voice, name, scenario, attempt, settings)
        for voice in voices
        for name, scenario in scenarios.items()
        for attempt in range(1, attempts + 1)
    ]
    with ThreadPoolExecutor(max_workers=settings["workers"]) as pool:
        generations = list(pool.map(_generate, jobs))
    done = [g for g in generations if g.get("text")]
    judge_jobs = [(judge, g, scenarios[g["scenario"]], settings, prompts) for g in done for judge in judges]
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


def _total_cost(generations: list[dict[str, Any]], judged: list[dict[str, Any]]) -> float:
    narration = sum(g["cost"] for g in generations if "cost" in g)
    judging = sum(v["cost"] for g in judged for v in g["verdicts"] if "cost" in v)
    return round(narration + judging, 3)


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
        "secs": _mean([g["secs"] for g in judged]),
        "words": _mean([g["words"] for g in judged]),
        "cost": _total_cost(generations, judged),
    }


def summarize(generations: list[dict[str, Any]], miss_scenarios: set[str]) -> dict[str, dict[str, Any]]:
    by_model: dict[str, list[dict[str, Any]]] = {}
    for generation in generations:
        if generation["model"] not in by_model:
            by_model[generation["model"]] = []
        by_model[generation["model"]].append(generation)
    return {model: _model_summary(items, miss_scenarios) for model, items in by_model.items()}


def _summary_lines(summary: dict[str, dict[str, Any]]) -> list[str]:
    lines = []
    for model, s in summary.items():
        lines += [
            f"## {model}",
            "",
            f"Overall: {s['overall']} out of 10, over {s['generations']} narrations ({s['errors']} errors).",
            f"Result integrity on a miss: {s['integrity_on_miss']} out of 5.",
            *[f"- {criterion}: {s[criterion]} out of 5" for criterion in CRITERIA],
            f"Speed: {s['secs']} seconds per narration, {s['words']} words. Cost: about ${s['cost']}.",
            "",
        ]
    return lines


def report(summary: dict[str, dict[str, Any]], baseline: dict[str, dict[str, Any]], stamp: str) -> str:
    lines = [f"# Model test {stamp}", "", *_summary_lines(summary), "# Baseline", "", *_summary_lines(baseline)]
    return "\n".join(lines)
