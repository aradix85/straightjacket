#!/usr/bin/env python3
"""Per-role model evaluation.

Tests individual AI roles with fixed inputs and expected outputs.
Uses the same provider and config infrastructure as the engine.

Usage:
    python tests/model_eval/eval.py                          # all roles, configured models
    python tests/model_eval/eval.py --role brain             # brain only
    python tests/model_eval/eval.py --role brain --model gpt-oss-120b  # override model
    python tests/model_eval/eval.py --verbose                # show full model output
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Engine imports — uses real config, real provider, real schemas
from straightjacket.engine.ai.api_client import get_provider
from straightjacket.engine.ai.provider_base import AIProvider, create_with_retry
from straightjacket.engine.ai.schemas import (
    get_brain_output_schema,
    get_narrator_metadata_schema,
)
from straightjacket.engine.config_loader import (
    model_for_role,
    reload_config,
    sampling_params,
)
from straightjacket.engine.prompt_loader import get_prompt

_HERE = Path(__file__).resolve().parent
_CASES_PATH = _HERE / "cases.yaml"


# ── Result tracking ──────────────────────────────────────────


@dataclass
class CaseResult:
    """Outcome of one test case."""

    case_id: str
    role: str
    passed: bool = True
    checks: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    raw_output: str = ""
    error: str = ""


@dataclass
class RoleReport:
    """Aggregate results for one role."""

    role: str
    model: str
    results: list[CaseResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def total(self) -> int:
        return len(self.results)


# ── Brain evaluator ──────────────────────────────────────────


def _build_brain_context() -> tuple[str, str]:
    """Build minimal but realistic Brain prompt context."""
    from straightjacket.engine.models import GameState, NpcData

    game = GameState(
        player_name="Ash",
        setting_id="starforged",
        setting_genre="starforged",
        setting_tone="serious",
        edge=2,
        heart=1,
        iron=2,
        shadow=1,
        wits=3,
    )
    game.world.current_location = "Cargo Bay"
    game.world.current_scene_context = "Investigating missing shipment"
    game.world.time_of_day = "evening"
    game.npcs = [
        NpcData(id="npc_1", name="Kira", disposition="friendly", status="active"),
        NpcData(id="npc_2", name="Borin", disposition="neutral", status="active"),
    ]

    from straightjacket.engine.ai.brain import _build_moves_block, _build_tracks_block
    from straightjacket.engine.prompt_blocks import content_boundaries_block

    system = get_prompt(
        "brain_parser",
        lang="English",
        content_boundaries_block=content_boundaries_block(game),
        moves_block=_build_moves_block(game),
    )

    npc_block = "<npcs>\n"
    for n in game.npcs:
        npc_block += f"  {n.name} (id:{n.id}, {n.disposition})\n"
    npc_block += "</npcs>"

    tracks_block = _build_tracks_block(game)

    user_template = f"""<state>
loc:{game.world.current_location} | ctx:{game.world.current_scene_context}
time:{game.world.time_of_day}
{game.player_name} E{game.edge} H{game.heart} I{game.iron} Sh{game.shadow} W{game.wits}
</state>
{npc_block}
{tracks_block}
<input>{{input}}</input>"""

    return system, user_template


def eval_brain(provider: AIProvider, case: dict, model: str, params: dict) -> CaseResult:
    """Evaluate one Brain test case."""
    system, user_template = _build_brain_context()
    user_msg = user_template.format(input=case["input"])
    result = CaseResult(case_id=case["id"], role="brain")

    try:
        response = create_with_retry(
            provider,
            model=model,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
            json_schema=get_brain_output_schema(),
            log_role="eval_brain",
            **params,
        )
        data = json.loads(response.content)
        result.raw_output = json.dumps(data, indent=2)
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        result.passed = False
        return result

    expect = case["expect"]
    result.passed = True

    if "move" in expect:
        if data.get("move") == expect["move"]:
            result.checks.append(f"move={expect['move']}")
        else:
            result.failures.append(f"move: expected {expect['move']}, got {data.get('move')}")
            result.passed = False

    if "move_prefix" in expect:
        move = data.get("move", "")
        if move.startswith(expect["move_prefix"]):
            result.checks.append(f"move starts with {expect['move_prefix']}")
        else:
            result.failures.append(f"move_prefix: expected {expect['move_prefix']}*, got {move}")
            result.passed = False

    if "stat" in expect:
        if data.get("stat") == expect["stat"]:
            result.checks.append(f"stat={expect['stat']}")
        else:
            result.failures.append(f"stat: expected {expect['stat']}, got {data.get('stat')}")
            result.passed = False

    if "stat_oneof" in expect:
        if data.get("stat") in expect["stat_oneof"]:
            result.checks.append(f"stat in {expect['stat_oneof']}")
        else:
            result.failures.append(f"stat: expected one of {expect['stat_oneof']}, got {data.get('stat')}")
            result.passed = False

    if "dialog_only" in expect:
        if data.get("dialog_only") == expect["dialog_only"]:
            result.checks.append(f"dialog_only={expect['dialog_only']}")
        else:
            result.failures.append(f"dialog_only: expected {expect['dialog_only']}, got {data.get('dialog_only')}")
            result.passed = False

    if "target_npc" in expect:
        if data.get("target_npc") == expect["target_npc"]:
            result.checks.append(f"target_npc={expect['target_npc']}")
        else:
            result.failures.append(f"target_npc: expected {expect['target_npc']}, got {data.get('target_npc')}")
            result.passed = False

    if expect.get("fate_question_present"):
        if data.get("fate_question"):
            result.checks.append("fate_question present")
        else:
            result.failures.append("fate_question: expected present, got empty/null")
            result.passed = False

    if expect.get("world_addition_present"):
        if data.get("world_addition"):
            result.checks.append("world_addition present")
        else:
            result.failures.append("world_addition: expected present, got empty/null")
            result.passed = False

    if expect.get("location_change_present"):
        if data.get("location_change"):
            result.checks.append("location_change present")
        else:
            result.failures.append("location_change: expected present, got empty/null")
            result.passed = False

    return result


# ── Validator evaluator ──────────────────────────────────────


def eval_validator(provider: AIProvider, case: dict, model: str, params: dict) -> CaseResult:
    """Evaluate one Validator test case."""
    from straightjacket.engine.ai.rule_validator import run_rule_checks
    from straightjacket.engine.ai.schemas import VALIDATOR_SCHEMA

    result = CaseResult(case_id=case["id"], role="validator")
    narration = case["narration"]
    result_type = case.get("result_type", "STRONG_HIT")

    # Layer 1: rule-based checks (always the same, model-independent)
    rule_result = run_rule_checks(narration, result_type)
    rule_violations: list[str] = rule_result.get("violations", [])

    # Layer 2: LLM check
    system = """Constraint checker for RPG narration. Be STRICT and PRECISE.
GENRE PHYSICS: Materials MUST NOT exhibit consciousness or transformation. No magic in grounded settings.
PLAYER AGENCY: MUST NOT impose thoughts, feelings, or interpretations on the player character.
RESULT INTEGRITY: MISS = concrete failure, no silver linings. WEAK_HIT = success with tangible cost.
NPC SPEECH: Max two sentences per NPC, then they act or fall silent.
Respond with JSON: {"pass": true/false, "violations": [...], "correction": "..."}"""

    prompt = f"""Genre: {case.get("genre", "starforged")}
Result type: {result_type}
Narration:
{narration}
Check constraints."""

    llm_violations: list[str] = []
    try:
        response = create_with_retry(
            provider,
            model=model,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            json_schema=VALIDATOR_SCHEMA,
            log_role="eval_validator",
            **params,
        )
        data = json.loads(response.content)
        result.raw_output = json.dumps(data, indent=2)
        if not data.get("pass", True):
            llm_violations = data.get("violations", [])
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        result.passed = False
        return result

    all_violations = rule_violations + llm_violations
    did_pass = len(all_violations) == 0

    expect = case["expect"]
    result.passed = True

    if "pass" in expect:
        if did_pass == expect["pass"]:
            result.checks.append(f"pass={expect['pass']}")
        else:
            result.failures.append(f"pass: expected {expect['pass']}, got {did_pass} (violations: {all_violations})")
            result.passed = False

    if "violation_contains" in expect:
        target = expect["violation_contains"].lower()
        found = any(target in v.lower() for v in all_violations)
        if found:
            result.checks.append(f"violation contains '{expect['violation_contains']}'")
        else:
            result.failures.append(
                f"violation_contains: '{expect['violation_contains']}' not found in {all_violations}"
            )
            result.passed = False

    if "violation_contains_any" in expect:
        targets = [t.lower() for t in expect["violation_contains_any"]]
        found = any(any(t in v.lower() for t in targets) for v in all_violations)
        if found:
            result.checks.append(f"violation matches one of {expect['violation_contains_any']}")
        else:
            result.failures.append(
                f"violation_contains_any: none of {expect['violation_contains_any']} found in {all_violations}"
            )
            result.passed = False

    return result


# ── Extraction evaluator ─────────────────────────────────────


def eval_extraction(provider: AIProvider, case: dict, model: str, params: dict) -> CaseResult:
    """Evaluate one extraction (narrator_metadata) test case."""
    result = CaseResult(case_id=case["id"], role="extraction")

    system = get_prompt("narrator_metadata", lang="English")
    known = case.get("known_npcs", [])
    known_block = "\n".join(known) if known else "(none)"

    prompt = f"""<narration>{case["narration"]}</narration>
<player_character>{case["player_name"]}</player_character>
<known_npcs>{known_block}</known_npcs>
<current_location>Cargo Bay</current_location>
<current_time>evening</current_time>
Extract all metadata from the narration above. Remember: {case["player_name"]} is the PLAYER CHARACTER, not an NPC."""

    try:
        response = create_with_retry(
            provider,
            model=model,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            json_schema=get_narrator_metadata_schema(),
            log_role="eval_extraction",
            **params,
        )
        data = json.loads(response.content)
        result.raw_output = json.dumps(data, indent=2)
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        result.passed = False
        return result

    expect = case["expect"]
    result.passed = True

    new_npcs = data.get("new_npcs", [])
    deceased = data.get("deceased_npcs", [])

    if "new_npc_count" in expect:
        if len(new_npcs) == expect["new_npc_count"]:
            result.checks.append(f"new_npc_count={expect['new_npc_count']}")
        else:
            names = [n.get("name", "?") for n in new_npcs]
            result.failures.append(f"new_npc_count: expected {expect['new_npc_count']}, got {len(new_npcs)} ({names})")
            result.passed = False

    if "new_npc_name" in expect:
        names = [n.get("name", "").lower() for n in new_npcs]
        target = expect["new_npc_name"].lower()
        if any(target in n for n in names):
            result.checks.append(f"new_npc_name contains '{expect['new_npc_name']}'")
        else:
            result.failures.append(f"new_npc_name: '{expect['new_npc_name']}' not in {names}")
            result.passed = False

    if expect.get("deceased_npc_present"):
        if deceased:
            result.checks.append("deceased_npc present")
        else:
            result.failures.append("deceased_npc: expected present, got empty")
            result.passed = False

    return result


# ── Runner ───────────────────────────────────────────────────


_ROLE_EVALUATORS = {
    "brain": eval_brain,
    "validator": eval_validator,
    "extraction": eval_extraction,
}


def load_cases() -> dict[str, list[dict]]:
    """Load test cases from YAML."""
    with open(_CASES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_role(
    provider: AIProvider, role: str, cases: list[dict], model_override: str = "", verbose: bool = False
) -> RoleReport:
    """Run all cases for one role."""
    evaluator = _ROLE_EVALUATORS[role]

    # Resolve model and params
    if model_override:
        model = model_override
        params = sampling_params(role)
    else:
        model = model_for_role(role)
        params = sampling_params(role)

    report = RoleReport(role=role, model=model)

    for case in cases:
        case_id = case["id"]
        print(f"  {case_id} ... ", end="", flush=True)
        case_result = evaluator(provider, case, model, params)
        report.results.append(case_result)

        if case_result.error:
            print(f"ERROR: {case_result.error}")
        elif case_result.passed:
            print(f"PASS ({', '.join(case_result.checks)})")
        else:
            print("FAIL")
            for f in case_result.failures:
                print(f"    {f}")

        if verbose and case_result.raw_output:
            for line in case_result.raw_output.splitlines():
                print(f"    | {line}")

    return report


def print_report(reports: list[RoleReport]) -> None:
    """Print summary across all roles."""
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total_passed = 0
    total_failed = 0

    for r in reports:
        status = "PASS" if r.failed == 0 else "FAIL"
        print(f"  {r.role:20s} {r.model:25s} {r.passed}/{r.total} {status}")
        total_passed += r.passed
        total_failed += r.failed

    total = total_passed + total_failed
    print(f"\n  Total: {total_passed}/{total} passed")
    if total_failed:
        print(f"  {total_failed} failures")


def main() -> None:
    parser = argparse.ArgumentParser(description="Per-role AI model evaluation")
    parser.add_argument("--role", choices=list(_ROLE_EVALUATORS.keys()), help="Evaluate one role only")
    parser.add_argument("--model", default="", help="Override model for all roles")
    parser.add_argument("--verbose", action="store_true", help="Show full model output")
    args = parser.parse_args()

    # Load engine config (needed for schemas, prompts, provider)
    reload_config()
    from straightjacket.engine import engine_loader

    engine_loader._eng = None
    engine_loader.eng()

    provider = get_provider()
    all_cases = load_cases()

    roles = [args.role] if args.role else list(_ROLE_EVALUATORS.keys())
    reports: list[RoleReport] = []

    for role in roles:
        cases = all_cases.get(role, [])
        if not cases:
            print(f"\n{role}: no test cases")
            continue

        model = args.model or model_for_role(role)
        print(f"\n{role} ({model})")
        print("-" * 40)

        report = run_role(provider, role, cases, model_override=args.model, verbose=args.verbose)
        reports.append(report)

    print_report(reports)

    # Exit code: 1 if any failures
    if any(r.failed > 0 for r in reports):
        sys.exit(1)


if __name__ == "__main__":
    main()
