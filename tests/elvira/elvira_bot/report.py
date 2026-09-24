from __future__ import annotations

import re
import statistics
from collections import Counter
from pathlib import Path
from straightjacket.engine.config_loader import model_for_role

from .coverage import Coverage
from .judge import CRITERIA
from .models import SessionLog


def _warning_problems(slog: SessionLog) -> list[str]:
    return [
        f"Engine {message}" + (f" ({count} times)" if count > 1 else "")
        for message, count in Counter(w[:200] for w in slog.engine_warnings).most_common()
    ]


def _audit_problems(slog: SessionLog) -> list[str]:
    return [
        f"Turn {t.turn}: narration audit scored {t.judge['overall']}/10: {t.judge['weakness']}"
        for t in slog.turns
        if "overall" in t.judge and t.judge["overall"] <= 4
    ]


def collect_problems(slog: SessionLog) -> list[str]:
    problems: list[str] = []
    problems += [f"Turn {t.turn}: engine or bot error: {t.error}" for t in slog.turns if t.error]
    problems += [f"Turn {t.turn}: director error: {t.director_error}" for t in slog.turns if t.director_error]
    problems += [f"Turn {t.turn}: burn error: {t.burn_error}" for t in slog.turns if t.burn_error]
    problems += [f"Invariant: {v}" for v in slog.violations]
    problems += [f"Save/load: {i}" for i in slog.save_roundtrip_issues]
    problems += [f"Streaming: {i}" for i in slog.stream_issues]
    problems += [f"Status query: {i}" for i in slog.query_issues]
    problems += _warning_problems(slog)
    problems += [f"Narration leak: {i}" for i in slog.narration_quality_issues]
    problems += [f"Spatial: {i}" for i in slog.spatial_issues]
    problems += [f"Chapter continuity: {i}" for i in slog.chapter_continuity_issues]
    problems += [f"Correction: {c}" for c in slog.correction_tests if not c["success"]]
    if "error" in slog.succession:
        problems.append(f"Succession: {slog.succession['error']}")
    problems += _audit_problems(slog)
    return problems


def _cost_lines(slog: SessionLog, prices: dict[str, list[float]]) -> list[str]:
    lines: list[str] = []
    total = 0.0
    for role, usage in sorted(slog.token_summary.get("by_role", {}).items()):
        try:
            model = model_for_role(role)
        except (KeyError, ValueError):
            model = "unknown"
        price = prices.get(model)
        if price is None:
            lines.append(
                f"- {role} ({model}): {usage['calls']} calls, {usage['input']} in, {usage['output']} out, no price configured"
            )
            continue
        cost = usage["input"] * price[0] / 1e6 + usage["output"] * price[1] / 1e6
        total += cost
        lines.append(
            f"- {role} ({model}): {usage['calls']} calls, {usage['input']} in, {usage['output']} out, about ${cost:.3f}"
        )
    lines.append(
        f"- Total: about ${total:.2f}. Input is counted at full price, so prompt caching makes the real cost lower."
    )
    return lines


def _audit_lines(slog: SessionLog) -> list[str]:
    audited = [t.judge for t in slog.turns if "overall" in t.judge]
    if not audited:
        lines = ["No turns audited."]
    else:
        means = {c: statistics.mean(a[c] for a in audited) for c in (*CRITERIA, "overall")}
        lines = [f"{len(audited)} turns audited. Overall {means['overall']:.1f} out of 10."]
        lines += [f"- {c}: {means[c]:.1f} out of 5" for c in CRITERIA]
    failed = sum(1 for t in slog.turns if "error" in t.judge)
    if failed:
        lines.append(f"{failed} audit(s) failed to produce a verdict.")
    return lines


def _stream_lines(slog: SessionLog) -> list[str]:
    streamed = [t for t in slog.turns if t.stream_first_sentence_secs is not None]
    if not streamed:
        return ["No turns streamed."]
    firsts = [t.stream_first_sentence_secs for t in streamed if t.stream_first_sentence_secs is not None]
    complete = sum(1 for t in streamed if t.stream_complete)
    matching = sum(1 for t in streamed if t.stream_matches)
    return [
        f"{len(streamed)} turns streamed; first sentence after {statistics.median(firsts):.1f} seconds (median).",
        f"{complete} complete, {matching} identical to the final text.",
    ]


def _speed_lines(slog: SessionLog) -> list[str]:
    secs = [t.turn_secs for t in slog.turns if not t.error and t.turn_secs]
    if not secs:
        return ["No timed turns."]
    return [f"Turn time: median {statistics.median(secs):.1f} seconds, longest {max(secs):.1f}."]


def _coverage_lines(coverage: Coverage) -> list[str]:
    exercised = [f"{t} ({coverage.counts[t]})" for t in coverage.exercised()]
    missing = coverage.missing()
    return [
        f"Exercised: {', '.join(exercised)}." if exercised else "Exercised: nothing.",
        "",
        f"Not exercised: {', '.join(missing)}." if missing else "Not exercised: nothing.",
    ]


def _event_lines(slog: SessionLog) -> list[str]:
    events = [e for t in slog.turns for e in t.engine_events]
    if not events:
        return ["No engine events captured."]
    new_npcs = sum(int(m.group(1)) for e in events if (m := re.match(r"\[Metadata\] Extracted: (\d+) new NPCs", e)))
    lines = [f"New NPCs extracted from narration: {new_npcs}."]
    for label, prefix in (("Bonuses", "[Bonus]"), ("Chained moves", "[Chain]"), ("Pay the Price", "[PayThePrice]")):
        found = [e for e in events if e.startswith(prefix)]
        lines.append(f"{label}: {len(found)}.")
        lines += [f"- {e[len(prefix) :].strip()}" for e in found[:8]]
    lines.append(f"Director tool rounds: {sum(1 for e in events if e.startswith('[Tools]'))}.")
    return lines


def write_report(slog: SessionLog, coverage: Coverage, path: Path, prices: dict[str, list[float]]) -> Path:
    problems = collect_problems(slog)
    verdict = "no problems found" if not problems else f"{len(problems)} problem(s) found"
    out: list[str] = [
        f"# Elvira report: {slog.config['game']['setting_id']}, {slog.style}, {len(slog.turns)} turns",
        "",
    ]
    out += [f"Verdict: {verdict}.", ""]
    if problems:
        out += ["## Problems", "", *[f"- {p}" for p in problems], ""]
    for title, lines in (
        ("Coverage", _coverage_lines(coverage)),
        ("Narration audit", _audit_lines(slog)),
        ("Streaming", _stream_lines(slog)),
        ("Engine events", _event_lines(slog)),
        ("Speed", _speed_lines(slog)),
        ("Cost", _cost_lines(slog, prices)),
    ):
        out += [f"## {title}", "", *lines, ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out), encoding="utf-8")
    return path
