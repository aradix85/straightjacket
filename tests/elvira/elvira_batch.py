#!/usr/bin/env python3
"""Elvira batch runner — compliance validation across all settings and playstyles.

Runs Elvira for every combination of setting × playstyle (or a configured subset),
aggregates the results, and writes a single compliance report.

Covers roadmap step 1: compliance baseline, violation patterns, token budgets.

Usage:
    python elvira/elvira_batch.py
    python elvira/elvira_batch.py --turns 15 --repeats 2
    python elvira/elvira_batch.py --settings starforged classic --styles explorer aggressor
    python elvira/elvira_batch.py --turns 10 --repeats 1 --styles explorer
"""

import argparse
import copy
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT / "src"))

# Console logging (same as elvira.py)
import logging

_logger = logging.getLogger("rpg_engine")
if not _logger.handlers:
    _ch = logging.StreamHandler(sys.stdout)
    _ch.setFormatter(logging.Formatter("%(message)s"))
    _logger.setLevel(logging.DEBUG)
    _logger.addHandler(_ch)

from straightjacket.engine.datasworn.settings import list_packages

from elvira_bot.models import SessionLog
from elvira_bot.runner import load_config, run_session

DEFAULT_CONFIG = _HERE / "elvira_config.yaml"
ALL_STYLES = ["explorer", "aggressor", "dialogist", "chaosagent", "balanced"]
SEPARATOR = "=" * 62


def run_batch(
    base_cfg: dict,
    settings: list[str],
    styles: list[str],
    repeats: int,
) -> list[dict]:
    """Run all combinations and return per-session result dicts."""
    results: list[dict] = []
    total = len(settings) * len(styles) * repeats
    run_num = 0

    for setting_id in settings:
        for style in styles:
            for rep in range(repeats):
                run_num += 1
                label = f"{setting_id}/{style}"
                if repeats > 1:
                    label += f" #{rep + 1}"
                print(f"\n{'#' * 62}")
                print(f"  BATCH RUN {run_num}/{total}: {label}")
                print(f"{'#' * 62}\n")

                cfg = copy.deepcopy(base_cfg)
                cfg.setdefault("game", {})["setting_id"] = setting_id
                cfg.setdefault("game", {})["load_existing"] = False
                cfg.setdefault("bot_behavior", {})["style"] = style
                cfg.setdefault("session", {})["clean_before_run"] = True

                result: dict = {
                    "setting": setting_id,
                    "style": style,
                    "repeat": rep + 1,
                }

                try:
                    slog = run_session(cfg, auto_override=True)
                    result.update(_extract_session_stats(slog))
                except Exception as e:
                    tb = traceback.format_exc()
                    print(f"\n  [BATCH] CRASHED: {e}")
                    print(tb[-500:])
                    result["crashed"] = True
                    result["error"] = f"{type(e).__name__}: {e}"

                results.append(result)

    return results


def _extract_session_stats(slog: SessionLog) -> dict:
    """Extract the numbers that matter for compliance reporting."""
    vs = slog.validator_summary or {}
    qs = slog.quality_summary or {}

    turns_checked = vs.get("turns_checked", 0)
    turns_failed = vs.get("turns_failed", 0)
    turns_retried = vs.get("turns_retried", 0)
    compliance_rate = ((turns_checked - turns_failed) / turns_checked * 100) if turns_checked > 0 else 0.0

    return {
        "crashed": False,
        "total_turns": slog.total_turns,
        "ended_reason": slog.ended_reason,
        "turns_checked": turns_checked,
        "turns_retried": turns_retried,
        "turns_failed": turns_failed,
        "total_retries": vs.get("total_retries", 0),
        "compliance_rate": round(compliance_rate, 1),
        "top_violations": vs.get("top_violations", []),
        "invariant_violations": len(slog.violations),
        "quality_issues": qs.get("narration_quality_total", 0),
        "spatial_issues": qs.get("spatial_issues_total", 0),
        "correction_tests": qs.get("correction_tests_total", 0),
        "correction_failures": qs.get("correction_tests_failed", 0),
        "burn_stats": slog.burn_stats,
        "token_summary": slog.token_summary,
    }


def build_report(results: list[dict], settings: list[str], styles: list[str], turns: int, repeats: int) -> str:
    """Build a human-readable compliance report."""
    lines: list[str] = []
    lines.append(f"Elvira Batch Compliance Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Settings: {', '.join(settings)}")
    lines.append(f"Styles: {', '.join(styles)}")
    lines.append(f"Turns per session: {turns}, repeats: {repeats}")
    lines.append(f"Total sessions: {len(results)}")
    lines.append("")

    # Per-session results
    lines.append("Per-session results:")
    lines.append("")
    for r in results:
        label = f"{r['setting']}/{r['style']}"
        if repeats > 1:
            label += f" #{r['repeat']}"
        if r.get("crashed"):
            lines.append(f"  {label}: CRASHED — {r.get('error', '?')}")
            continue
        lines.append(
            f"  {label}: {r['compliance_rate']}% compliance "
            f"({r['turns_checked']} checked, {r['turns_failed']} failed, "
            f"{r['turns_retried']} retried, {r['total_retries']} total retries)"
        )
        if r["invariant_violations"]:
            lines.append(f"    invariant violations: {r['invariant_violations']}")
        if r["quality_issues"]:
            lines.append(f"    quality issues: {r['quality_issues']}")
        if r["spatial_issues"]:
            lines.append(f"    spatial issues: {r['spatial_issues']}")

    # Aggregated stats
    valid = [r for r in results if not r.get("crashed")]
    if valid:
        lines.append("")
        lines.append("Aggregated:")
        rates = [r["compliance_rate"] for r in valid]
        lines.append(f"  compliance: min {min(rates):.1f}%, max {max(rates):.1f}%, avg {sum(rates) / len(rates):.1f}%")
        total_inv = sum(r["invariant_violations"] for r in valid)
        total_qual = sum(r["quality_issues"] for r in valid)
        total_spatial = sum(r["spatial_issues"] for r in valid)
        lines.append(f"  invariant violations: {total_inv}")
        lines.append(f"  quality issues: {total_qual}")
        lines.append(f"  spatial issues: {total_spatial}")

        # Aggregate violation patterns across all sessions
        violation_totals: dict[str, int] = {}
        for r in valid:
            for v, count in r.get("top_violations", []):
                violation_totals[v] = violation_totals.get(v, 0) + count
        if violation_totals:
            lines.append("")
            lines.append("Top violations across all sessions:")
            for v, count in sorted(violation_totals.items(), key=lambda x: -x[1])[:15]:
                lines.append(f"  {count}x: {v[:120]}")

    crashed = [r for r in results if r.get("crashed")]
    if crashed:
        lines.append("")
        lines.append(f"Crashed sessions: {len(crashed)}/{len(results)}")
        for r in crashed:
            lines.append(f"  {r['setting']}/{r['style']}: {r.get('error', '?')}")

    # Pass/fail verdict
    lines.append("")
    if valid:
        avg_rate = sum(rates) / len(rates)
        if avg_rate >= 70:
            lines.append(f"VERDICT: PASS — average compliance {avg_rate:.1f}% >= 70% threshold")
        elif avg_rate >= 60:
            lines.append(f"VERDICT: MARGINAL — average compliance {avg_rate:.1f}% (60-70% range)")
        else:
            lines.append(f"VERDICT: FAIL — average compliance {avg_rate:.1f}% < 60% threshold")

    # Token budget summary
    token_sessions = [r for r in valid if r.get("token_summary", {}).get("total", 0) > 0]
    if token_sessions:
        lines.append("")
        lines.append("Token budget:")
        totals_by_role: dict[str, dict[str, int]] = {}
        for r in token_sessions:
            for role, stats in r["token_summary"].get("by_role", {}).items():
                if role not in totals_by_role:
                    totals_by_role[role] = {"calls": 0, "input": 0, "output": 0}
                totals_by_role[role]["calls"] += stats.get("calls", 0)
                totals_by_role[role]["input"] += stats.get("input", 0)
                totals_by_role[role]["output"] += stats.get("output", 0)
        for role, stats in sorted(totals_by_role.items(), key=lambda x: -x[1]["input"]):
            avg_in = stats["input"] // max(stats["calls"], 1)
            lines.append(
                f"  {role:<22} {stats['calls']:>4}x  avg_in {avg_in:>5}  total {stats['input'] + stats['output']}"
            )
        grand = sum(s["input"] + s["output"] for s in totals_by_role.values())
        lines.append(f"  total: {grand} tokens across {len(token_sessions)} sessions")
        narrator_stats = totals_by_role.get("narrator", {})
        if narrator_stats.get("calls"):
            avg_narrator = narrator_stats["input"] // narrator_stats["calls"]
            flag = " *** ABOVE 8K THRESHOLD ***" if avg_narrator > 8000 else ""
            lines.append(f"  avg narrator input: {avg_narrator} tokens{flag}")
    else:
        lines.append("VERDICT: NO DATA — all sessions crashed")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Elvira batch runner — compliance validation")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Base config file")
    parser.add_argument("--repeats", type=int, default=1, help="Repeat each combination N times (default: 1)")
    parser.add_argument("--settings", nargs="+", default=None, help="Settings to test (default: all except delve)")
    parser.add_argument("--styles", nargs="+", default=None, help="Styles to test (default: all 5)")
    parser.add_argument(
        "--output", type=Path, default=None, help="Report output path (default: elvira/batch_report.txt)"
    )
    args = parser.parse_args()

    base_cfg = load_config(args.config)
    max_turns = base_cfg.get("session", {}).get("max_turns", 25)

    available_settings = [s for s in list_packages() if s != "delve"]
    settings = args.settings or available_settings
    styles = args.styles or ALL_STYLES

    # Validate inputs
    for s in settings:
        if s not in available_settings:
            print(f"[ERROR] Unknown setting: {s} (available: {', '.join(available_settings)})")
            raise SystemExit(1)
    for s in styles:
        if s not in ALL_STYLES:
            print(f"[ERROR] Unknown style: {s} (available: {', '.join(ALL_STYLES)})")
            raise SystemExit(1)

    total = len(settings) * len(styles) * args.repeats
    print(f"\n{SEPARATOR}")
    print("  Elvira Batch Runner")
    print(f"  {len(settings)} settings × {len(styles)} styles × {args.repeats} repeats = {total} sessions")
    print(f"  {max_turns} turns per session (from config)")
    print(SEPARATOR)

    results = run_batch(base_cfg, settings, styles, args.repeats)

    report = build_report(results, settings, styles, max_turns, args.repeats)
    print(f"\n{SEPARATOR}")
    print(report)
    print(SEPARATOR)

    # Write report
    report_path = args.output or (_HERE / "batch_report.txt")
    report_path.write_text(report, encoding="utf-8")
    print(f"\n[BATCH] Report written to: {report_path}")

    # Write raw JSON for programmatic analysis
    json_path = report_path.with_suffix(".json")
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[BATCH] Raw data written to: {json_path}")


if __name__ == "__main__":
    main()
