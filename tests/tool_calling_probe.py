#!/usr/bin/env python3
"""Tool calling probe: evaluate tool calling reliability across models via Cerebras.

Standalone script. Reads config.yaml for provider settings.
Runs 15 test cases per model covering Brain and Director tool calling patterns.
Compares results across models and reports a winner.

Usage:
    python tests/tool_calling_probe.py                        # both models
    python tests/tool_calling_probe.py --model qwen-3-235b    # single model
    python tests/tool_calling_probe.py --models qwen zai-glm  # custom list

Requires CEREBRAS_API_KEY environment variable.
"""

import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from straightjacket.engine.ai.provider_base import AIProvider

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Default models to test
DEFAULT_MODELS = [
    "qwen-3-235b-a22b-instruct-2507",
    "zai-glm-4.7",
]


@dataclass
class ProbeResult:
    """Result of a single tool calling test case."""

    name: str
    passed: bool
    tool_calls: list[dict] = field(default_factory=list)
    error: str = ""
    latency_ms: int = 0
    raw_response: str = ""


@dataclass
class ModelReport:
    """Aggregated results for one model."""

    model: str
    results: list[ProbeResult]
    passed: int = 0
    failed: int = 0
    avg_latency_ms: int = 0
    failure_rate: float = 0.0

    def __post_init__(self) -> None:
        total = len(self.results)
        self.passed = sum(1 for r in self.results if r.passed)
        self.failed = total - self.passed
        self.avg_latency_ms = sum(r.latency_ms for r in self.results) // max(1, total)
        self.failure_rate = (self.failed / total) * 100 if total else 0.0


# ── Tool definitions ──────────────────────────────────────────


TOOLS_BRAIN = [
    {
        "type": "function",
        "function": {
            "name": "roll_oracle",
            "description": "Roll on a Datasworn oracle table by path. Returns the rolled result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_path": {
                        "type": "string",
                        "description": "Oracle table path, e.g. 'oracles/character/name/given'",
                    },
                },
                "required": ["table_path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fate_question",
            "description": "Ask a yes/no fate question about the fiction. Engine determines likelihood and rolls.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The yes/no question about the fiction",
                    },
                    "context_hint": {
                        "type": "string",
                        "description": "Context that helps determine likelihood: 'likely', 'unlikely', '50/50', etc.",
                    },
                },
                "required": ["question", "context_hint"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_move",
            "description": "Look up a Starforged/Ironsworn move by name. Returns move details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "move_name": {
                        "type": "string",
                        "description": "Move name, e.g. 'face_danger', 'compel', 'gather_information'",
                    },
                },
                "required": ["move_name"],
                "additionalProperties": False,
            },
        },
    },
]

TOOLS_DIRECTOR = [
    {
        "type": "function",
        "function": {
            "name": "query_npc",
            "description": "Query an NPC's current state: disposition, bond, recent memories, agenda.",
            "parameters": {
                "type": "object",
                "properties": {
                    "npc_id": {
                        "type": "string",
                        "description": "NPC identifier",
                    },
                },
                "required": ["npc_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_threads",
            "description": "List active story threads with their types and weights.",
            "parameters": {
                "type": "object",
                "properties": {
                    "active_only": {
                        "type": "boolean",
                        "description": "If true, return only active threads",
                    },
                },
                "required": ["active_only"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_clocks",
            "description": "List clocks filtered by type or status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "clock_type": {
                        "type": "string",
                        "description": "Filter by type: 'threat', 'scheme', 'progress'",
                    },
                    "unfired_only": {
                        "type": "boolean",
                        "description": "If true, return only unfired clocks",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
]


# ── Test cases ────────────────────────────────────────────────


BRAIN_SYSTEM = (
    "You are the Brain agent for a solo RPG engine. You classify player actions into game moves "
    "and call tools when needed. You have access to oracle tables, fate questions, and move lookups. "
    "When the player asks a yes/no question about the fiction, call fate_question. "
    "When you need to roll on an oracle table, call roll_oracle. "
    "When you need move details, call lookup_move. "
    "If no tool is needed, respond with a brief JSON classification."
)

DIRECTOR_SYSTEM = (
    "You are the Director agent for a solo RPG engine. You steer story pacing and NPC development. "
    "You have tools to query NPC state, story threads, and clocks. "
    "Use these tools to gather the information you need before providing guidance. "
    "Query what you need, then provide your analysis."
)

CASES: list[dict[str, Any]] = [
    # ── Brain: should call tools ──
    {
        "name": "brain_fate_simple",
        "system": BRAIN_SYSTEM,
        "user": "Is the door locked?",
        "tools": TOOLS_BRAIN,
        "expect_tool": "fate_question",
        "expect_no_tool": False,
    },
    {
        "name": "brain_fate_with_context",
        "system": BRAIN_SYSTEM,
        "user": "Would Kira help me escape? She's distrustful but we have history.",
        "tools": TOOLS_BRAIN,
        "expect_tool": "fate_question",
        "expect_no_tool": False,
    },
    {
        "name": "brain_oracle_name",
        "system": BRAIN_SYSTEM,
        "user": "I meet a stranger at the tavern. What's their name?",
        "tools": TOOLS_BRAIN,
        "expect_tool": "roll_oracle",
        "expect_no_tool": False,
    },
    {
        "name": "brain_move_lookup",
        "system": BRAIN_SYSTEM,
        "user": "What exactly happens on a Compel move?",
        "tools": TOOLS_BRAIN,
        "expect_tool": "lookup_move",
        "expect_no_tool": False,
    },
    {
        "name": "brain_fate_npc_behavior",
        "system": BRAIN_SYSTEM,
        "user": "Does the guard notice me sneaking past?",
        "tools": TOOLS_BRAIN,
        "expect_tool": "fate_question",
        "expect_no_tool": False,
    },
    # ── Brain: should NOT call tools ──
    {
        "name": "brain_action_no_tool",
        "system": BRAIN_SYSTEM,
        "user": "I draw my sword and attack the creature.",
        "tools": TOOLS_BRAIN,
        "expect_tool": None,
        "expect_no_tool": True,
    },
    {
        "name": "brain_dialog_no_tool",
        "system": BRAIN_SYSTEM,
        "user": 'I say to Rowan: "We need to leave before dawn."',
        "tools": TOOLS_BRAIN,
        "expect_tool": None,
        "expect_no_tool": True,
    },
    # ── Director: should call tools ──
    {
        "name": "director_query_npc",
        "system": DIRECTOR_SYSTEM,
        "user": "Provide a reflection for Kira (npc_1). How has she changed?",
        "tools": TOOLS_DIRECTOR,
        "expect_tool": "query_npc",
        "expect_no_tool": False,
    },
    {
        "name": "director_query_threads",
        "system": DIRECTOR_SYSTEM,
        "user": "What threads are active? I need to decide on pacing.",
        "tools": TOOLS_DIRECTOR,
        "expect_tool": "query_threads",
        "expect_no_tool": False,
    },
    {
        "name": "director_query_clocks",
        "system": DIRECTOR_SYSTEM,
        "user": "Are any threat clocks close to firing?",
        "tools": TOOLS_DIRECTOR,
        "expect_tool": "query_clocks",
        "expect_no_tool": False,
    },
    {
        "name": "director_multi_query",
        "system": DIRECTOR_SYSTEM,
        "user": "Scene 12 just ended with a MISS. Kira (npc_1) was present. Review her state and active threads.",
        "tools": TOOLS_DIRECTOR,
        "expect_tool": "query_npc",
        "expect_no_tool": False,
    },
    # ── Edge cases ──
    {
        "name": "brain_ambiguous_fate",
        "system": BRAIN_SYSTEM,
        "user": "I search the room carefully. Is there anything hidden?",
        "tools": TOOLS_BRAIN,
        "expect_tool": "fate_question",
        "expect_no_tool": False,
    },
    {
        "name": "brain_chained_question",
        "system": BRAIN_SYSTEM,
        "user": "The fate question returned Yes — the door is locked. Can I pick it with my tools?",
        "tools": TOOLS_BRAIN,
        "expect_tool": "fate_question",
        "expect_no_tool": False,
    },
    {
        "name": "director_no_tool_needed",
        "system": DIRECTOR_SYSTEM,
        "user": "The story is in act 2, climax phase. Pacing should be intense. No specific NPC to review.",
        "tools": TOOLS_DIRECTOR,
        "expect_tool": None,
        "expect_no_tool": True,
    },
    {
        "name": "brain_mixed_action_and_fate",
        "system": BRAIN_SYSTEM,
        "user": "I try to convince the merchant to lower the price. Would he be open to haggling?",
        "tools": TOOLS_BRAIN,
        "expect_tool": "fate_question",
        "expect_no_tool": False,
    },
]


# ── Runner ────────────────────────────────────────────────────


def run_probe(provider: "AIProvider", model: str) -> list[ProbeResult]:
    """Run all test cases for one model."""
    results = []

    for case in CASES:
        name = case["name"]
        print(f"  {name}...", end=" ", flush=True)

        start = time.monotonic()
        try:
            response = provider.create_message(
                model=model,
                system=case["system"],
                messages=[{"role": "user", "content": case["user"]}],
                max_tokens=1024,
                tools=case["tools"],
                temperature=0.3,
            )
            latency = int((time.monotonic() - start) * 1000)

            tool_calls = response.tool_calls
            content = response.content
            stop = response.stop_reason

            result = ProbeResult(
                name=name,
                passed=False,
                tool_calls=tool_calls,
                latency_ms=latency,
                raw_response=content[:200] if content else f"[tool_use: {len(tool_calls)} calls]",
            )

            expect_tool = case["expect_tool"]
            expect_no_tool = case["expect_no_tool"]

            if expect_no_tool:
                if not tool_calls and stop != "tool_use":
                    result.passed = True
                else:
                    called = [tc["name"] for tc in tool_calls] if tool_calls else []
                    result.error = f"expected no tool call, got {called}"
            elif expect_tool:
                if tool_calls:
                    called_names = [tc["name"] for tc in tool_calls]
                    if expect_tool in called_names:
                        tc = next(t for t in tool_calls if t["name"] == expect_tool)
                        args = tc.get("arguments", {})
                        if isinstance(args, dict):
                            result.passed = True
                        else:
                            result.error = f"arguments not a dict: {type(args).__name__}"
                    else:
                        result.error = f"expected {expect_tool}, got {called_names}"
                else:
                    if content and ("function" in content.lower() or "tool" in content.lower()):
                        result.error = f"tool call attempted as text, not structured (stop={stop})"
                    else:
                        result.error = f"no tool call, got text response (stop={stop})"
            else:
                result.passed = True

        except Exception as e:
            latency = int((time.monotonic() - start) * 1000)
            error_msg = f"{type(e).__name__}: {e}"
            if "json" in error_msg.lower() or "JSONDecode" in error_msg:
                error_msg = f"malformed tool call JSON: {error_msg}"
            result = ProbeResult(name=name, passed=False, error=error_msg, latency_ms=latency)

        status = "PASS" if result.passed else f"FAIL ({result.error})"
        print(f"{status} [{result.latency_ms}ms]")
        results.append(result)

    return results


def print_model_report(report: ModelReport) -> None:
    """Print results for a single model."""
    print(f"\n{'—' * 60}")
    print(f"  {report.model}")
    print(f"{'—' * 60}")
    print(f"  Passed: {report.passed}/{report.passed + report.failed} ({100 - report.failure_rate:.0f}%)")
    print(f"  Average latency: {report.avg_latency_ms}ms")

    if report.failed:
        print("  Failures:")
        for r in report.results:
            if not r.passed:
                print(f"    {r.name}: {r.error}")


def _failure_breakdown(results: list[ProbeResult]) -> dict[str, int]:
    """Categorize failures."""
    cats: dict[str, int] = {}
    for r in results:
        if r.passed:
            continue
        if "malformed" in r.error:
            cats["malformed_json"] = cats.get("malformed_json", 0) + 1
        elif "expected" in r.error and "got [" in r.error:
            cats["wrong_tool"] = cats.get("wrong_tool", 0) + 1
        elif "no tool call" in r.error:
            cats["no_call"] = cats.get("no_call", 0) + 1
        elif "as text" in r.error:
            cats["text_call"] = cats.get("text_call", 0) + 1
        elif "expected no tool" in r.error:
            cats["unwanted_call"] = cats.get("unwanted_call", 0) + 1
        else:
            cats["other"] = cats.get("other", 0) + 1
    return cats


def print_comparison(reports: list[ModelReport], api_base: str) -> None:
    """Print comparative report across all models."""
    threshold = 5

    print(f"\n{'=' * 60}")
    print("TOOL CALLING PROBE — COMPARISON")
    print(f"{'=' * 60}")
    print(f"Provider: {api_base}")
    print(f"Cases per model: {len(CASES)}")
    print(f"Threshold: {threshold}% failure rate")

    for report in reports:
        print_model_report(report)
        breakdown = _failure_breakdown(report.results)
        if breakdown:
            labels = {
                "malformed_json": "Malformed JSON args",
                "wrong_tool": "Called wrong tool",
                "no_call": "Didn't call tool",
                "text_call": "Tool as text (not structured)",
                "unwanted_call": "Called tool when shouldn't",
                "other": "Other",
            }
            print("  Breakdown:")
            for key, count in breakdown.items():
                print(f"    {labels.get(key, key)}: {count}")

    # Verdicts
    print(f"\n{'=' * 60}")
    print("VERDICTS")
    print(f"{'=' * 60}")

    viable = []
    for report in reports:
        passed = report.failure_rate <= threshold
        verdict = "PASS" if passed else "FAIL"
        print(f"  {report.model}: {verdict} ({report.failure_rate:.0f}% failures, {report.avg_latency_ms}ms avg)")
        if passed:
            viable.append(report)

    if not viable:
        print("\n  No model passed the threshold.")
        print("  Recommendation: keep prompt-based as primary path.")
    elif len(viable) == 1:
        print(f"\n  Winner: {viable[0].model}")
        print("  Recommendation: use for Brain and Director tool calling.")
    else:
        # Multiple viable — pick by failure rate, then latency
        best = min(viable, key=lambda r: (r.failure_rate, r.avg_latency_ms))
        print(f"\n  Both viable. Best: {best.model}")
        print(f"  ({best.failure_rate:.0f}% failures, {best.avg_latency_ms}ms avg)")
        runner_up = [r for r in viable if r is not best][0]
        print(
            f"  Runner-up: {runner_up.model} ({runner_up.failure_rate:.0f}% failures, {runner_up.avg_latency_ms}ms avg)"
        )

    print(f"{'=' * 60}")


# ── Main ──────────────────────────────────────────────────────


if __name__ == "__main__":
    import argparse

    import yaml

    parser = argparse.ArgumentParser(description="Evaluate tool calling reliability across models via Cerebras.")
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Test a single model (default: test both Qwen and GLM)",
    )
    parser.add_argument(
        "--models",
        type=str,
        nargs="+",
        default=None,
        help="Test specific model slugs (space-separated)",
    )
    args = parser.parse_args()

    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    if not config_path.exists():
        print(f"ERROR: config.yaml not found at {config_path}")
        sys.exit(1)

    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    ai = cfg["ai"]
    api_base = ai["api_base"]
    api_key_env = ai["api_key_env"]

    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        print(f"ERROR: {api_key_env} environment variable not set")
        sys.exit(1)

    # Determine which models to test
    if args.model:
        models = [args.model]
    elif args.models:
        models = args.models
    else:
        models = DEFAULT_MODELS

    from straightjacket.engine.ai.provider_openai import OpenAICompatibleProvider

    provider = OpenAICompatibleProvider(api_key=api_key, api_base=api_base)

    print("Tool Calling Probe")
    print(f"Provider: {api_base}")
    print(f"Models: {', '.join(models)}")
    print(f"Cases per model: {len(CASES)}")

    all_reports = []
    for model in models:
        print(f"\n{'=' * 60}")
        print(f"Testing: {model}")
        print(f"{'=' * 60}")

        results = run_probe(provider, model)
        report = ModelReport(model=model, results=results)
        all_reports.append(report)

    print_comparison(all_reports, api_base)
