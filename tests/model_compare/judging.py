from __future__ import annotations

import hashlib
import json
import shutil
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from straightjacket.engine.serialization import build_strict, shaped
from tests.model_compare.calls import read_calls
from tests.model_compare.replay import ANSWERS, CALLS, KEY, MEASURES, Answer, KeyEntry, Measure, cost, read_jsonl

if TYPE_CHECKING:
    from pathlib import Path

    from tests.model_compare.calls import CapturedCall
    from tests.model_compare.settings import Configuration, Price

PACKETS = "packets"
SCORES = "scores"
SUMMARY = "summary.md"


@dataclass(frozen=True)
class Score:
    code: str
    scores: dict[str, float | bool | None]
    note: str


def write_packets(run_dir: Path, rubrics: dict[str, str]) -> int:
    calls = {c.call_id: c for c in read_calls(run_dir / CALLS)}
    by_call: dict[str, list[Answer]] = defaultdict(list)
    for answer in read_jsonl(run_dir / ANSWERS, Answer):
        by_call[answer.call].append(answer)
    root = run_dir / PACKETS
    if root.exists():
        shutil.rmtree(root)
    for call_id, answers in by_call.items():
        call = calls[call_id]
        folder = root / call.spec.log_role
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "RUBRIC.md").write_text(rubrics["common"] + "\n" + rubrics[call.spec.log_role], encoding="utf-8")
        (folder / f"{call_id}.md").write_text(_packet(call, answers, folder), encoding="utf-8")
    return len(by_call)


def _packet(call: CapturedCall, answers: list[Answer], folder: Path) -> str:
    spec = call.spec
    fixed = spec.cached_system_prefix or spec.system
    system_file = f"system-{hashlib.sha256(fixed.encode()).hexdigest()[:8]}.md"
    (folder / system_file).write_text(fixed, encoding="utf-8")
    parts = [f"# {call.call_id}: {spec.log_role}, from the {call.source} run", f"System prompt: {system_file}"]
    if tail := spec.system[len(fixed) :]:
        parts.append(f"## The system prompt's part for this turn\n\n{tail}")
    earlier = [m["content"] for m in spec.messages[:-1] if m["role"] == "assistant"]
    if earlier:
        parts.append(f"## The narration before this request\n\n{earlier[-1]}")
    parts.append(f"## The request's last message\n\n{spec.messages[-1]['content']}")
    for answer in sorted(answers, key=lambda a: a.code):
        stop = "" if answer.stop_reason == "complete" else f" (stop: {answer.stop_reason})"
        parts.append(f"## Answer {answer.code}{stop}\n\n{_readable(answer.content)}")
    return "\n\n".join(parts) + "\n"


def _readable(content: str) -> str:
    try:
        return json.dumps(json.loads(content), ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return content


def read_scores(run_dir: Path) -> dict[str, Score]:
    scores: dict[str, Score] = {}
    for path in sorted((run_dir / SCORES).glob("*.jsonl")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            score = build_strict(Score, json.loads(line), f"{path.name}:{n}", scores=_score_values)
            if score.code in scores:
                msg = f"{path.name}:{n}: answer {score.code} is scored twice"
                raise ValueError(msg)
            scores[score.code] = score
    return scores


def _score_values(data: object, where: str) -> dict[str, float | bool | None]:
    values = shaped(data, dict, f"{where}: expected dict")
    if wrong := {k: v for k, v in values.items() if v is not None and not isinstance(v, int | float)}:
        msg = f"{where}: expected numbers, true, false, or null, got {wrong}"
        raise ValueError(msg)
    return {str(k): v for k, v in values.items()}


def write_summary(run_dir: Path, configurations: dict[str, Configuration], prices: dict[str, dict[str, Price]]) -> str:
    answers = {a.code: a for a in read_jsonl(run_dir / ANSWERS, Answer)}
    key = {k.code: k for k in read_jsonl(run_dir / KEY, KeyEntry)}
    measures = {m.code: m for m in read_jsonl(run_dir / MEASURES, Measure)}
    scores = read_scores(run_dir)
    if unscored := sorted(set(answers) - set(scores)):
        msg = f"{len(unscored)} answers have no score yet, among them {unscored[:5]}"
        raise ValueError(msg)
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for code, answer in answers.items():
        groups[_label(key[code]), answer.role].append(code)
    lines = ["# Summary", ""]
    for role in sorted({role for _, role in groups}):
        lines.extend(_role_section(role, {label: codes for (label, r), codes in groups.items() if r == role}, scores))
        lines.extend(_speed_lines(role, groups, measures))
    lines.extend(_cost_lines(groups, key, measures, configurations, prices))
    text = "\n".join(lines) + "\n"
    (run_dir / SUMMARY).write_text(text, encoding="utf-8")
    return text


def _label(entry: KeyEntry) -> str:
    return entry.configuration if entry.replicate == 1 else f"{entry.configuration}#{entry.replicate}"


def _role_section(role: str, by_label: dict[str, list[str]], scores: dict[str, Score]) -> list[str]:
    keys = sorted({k for codes in by_label.values() for code in codes for k in scores[code].scores})
    lines = [f"## {role}", "", "| configuration | n | " + " | ".join(keys) + " |", "|---" * (len(keys) + 2) + "|"]
    for label in sorted(by_label):
        codes = by_label[label]
        cells = [_mean([scores[c].scores.get(k) for c in codes]) for k in keys]
        lines.append(f"| {label} | {len(codes)} | " + " | ".join(cells) + " |")
    return [*lines, ""]


def _mean(values: list[float | bool | None]) -> str:
    present = [float(v) for v in values if v is not None]
    return f"{statistics.fmean(present):.2f} ({len(present)})" if present else "-"


def _speed_lines(role: str, groups: dict[tuple[str, str], list[str]], measures: dict[str, Measure]) -> list[str]:
    lines = [f"Speed of {role}: median seconds of the answering attempt; time to first text where streamed.", ""]
    for (label, r), codes in sorted(groups.items()):
        if r != role:
            continue
        finals = [measures[c].attempts[-1] for c in codes if measures[c].attempts]
        firsts = [a.first_text for a in finals if a.first_text is not None]
        first = f", first text {statistics.median(firsts):.1f} s" if firsts else ""
        retried = sum(len(measures[c].attempts) > 1 for c in codes)
        failed = sum(not measures[c].attempts or bool(measures[c].error) for c in codes)
        seconds = f"{statistics.median(a.seconds for a in finals):.1f} s" if finals else "-"
        lines.append(f"- {label}: {seconds}{first}; {retried} asked again, {failed} failed")
    return [*lines, ""]


def _cost_lines(
    groups: dict[tuple[str, str], list[str]],
    key: dict[str, KeyEntry],
    measures: dict[str, Measure],
    configurations: dict[str, Configuration],
    prices: dict[str, dict[str, Price]],
) -> list[str]:
    lines = ["## Tokens and cost", "", "| configuration | input | output | thinking | cost |", "|---|---|---|---|---|"]
    by_label: dict[str, list[str]] = defaultdict(list)
    for (label, _), codes in groups.items():
        by_label[label].extend(codes)
    for label, codes in sorted(by_label.items()):
        attempts = [(a, configurations[key[c].configuration].model) for c in codes for a in measures[c].attempts]
        inputs = sum(a.uncached_tokens + a.cache_write_tokens + a.cache_read_tokens for a, _ in attempts)
        outputs = sum(a.output_tokens for a, _ in attempts)
        thinking = sum(a.thinking_tokens for a, _ in attempts)
        dollars = sum(cost(a, prices, model) for a, model in attempts)
        lines.append(f"| {label} | {inputs} | {outputs} | {thinking} | ${dollars:.2f} |")
    return [*lines, ""]
