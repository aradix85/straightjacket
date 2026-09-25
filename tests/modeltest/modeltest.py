import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from tests.modeltest.capture import capture_all
from tests.modeltest.measure import (
    check_models,
    compare,
    contestants,
    intervals,
    judge_all,
    judges_from,
    measure,
    per_judge,
    report,
    summarize,
)


def _load(name: str) -> dict:
    loaded: dict = yaml.safe_load((_HERE / name).read_text(encoding="utf-8"))
    return loaded


def _scenarios() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((_HERE / "scenarios").glob("*.json"))}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Straightjacket: narrator model comparison on fixed scenes")
    parser.add_argument("--capture", action="store_true", help="Capture the scenes again with the current engine")
    parser.add_argument(
        "--models", nargs="+", default=["current"], help="Contestants from modeltest_config.yaml, or 'current'"
    )
    parser.add_argument("--attempts", type=int, default=None, help="Narrations per model and scene")
    parser.add_argument("--workers", type=int, default=None, help="Requests at the same time")
    parser.add_argument("--retries", type=int, default=None, help="Retries per request")
    parser.add_argument("--rejudge", nargs="+", default=None, help="Judge the narrations in these run files again")
    parser.add_argument("--report", nargs="+", default=None, help="Report on these run files together, no API calls")
    args = parser.parse_args()

    settings = _load("modeltest_config.yaml")
    if args.workers is not None:
        settings["workers"] = args.workers
    if args.retries is not None:
        settings["max_retries"] = args.retries
    if args.capture:
        for line in capture_all(_load("modeltest_scenarios.yaml"), _HERE / "scenarios", settings):
            print(line)
        return

    scenarios = _scenarios()
    judges = judges_from(settings)
    if args.report:
        _write(_read_runs(args.report), scenarios, settings, "_report")
        return
    if args.rejudge:
        check_models(judges, settings)
        _write(
            judge_all(_read_runs(args.rejudge), scenarios, judges, settings, _load("modeltest_prompts.yaml")),
            scenarios,
            settings,
            "_rejudged",
        )
        return
    voices = contestants(args.models, settings)
    check_models([*voices, *judges], settings)
    attempts = args.attempts if args.attempts is not None else settings["attempts"]
    print(f"Measuring {', '.join(v.label for v in voices)}: {len(scenarios)} scenes, {attempts} attempts each")
    _write(
        measure(voices, scenarios, judges, settings, _load("modeltest_prompts.yaml"), attempts), scenarios, settings, ""
    )


def _read_runs(paths: list[str]) -> list[dict]:
    generations: list[dict] = []
    for path in paths:
        generations += json.loads(Path(path).read_text(encoding="utf-8"))
    return generations


def _write(generations: list[dict], scenarios: dict[str, dict], settings: dict, suffix: str) -> None:
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S") + suffix
    runs = _HERE / "runs"
    runs.mkdir(exist_ok=True)
    (runs / f"modeltest_{stamp}.json").write_text(
        json.dumps(generations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    miss = {name for name, scenario in scenarios.items() if scenario["result"] == "MISS"}
    criteria = settings["criteria"]
    summary = summarize(generations, miss, criteria)
    for model, interval in intervals(generations).items():
        summary[model]["interval"] = interval
    models = list(summary)
    reference = next((m for m in models if m.startswith("current narrator")), models[0])
    baseline = json.loads((_HERE / settings["baseline"]).read_text(encoding="utf-8"))
    text = report(
        summary,
        summarize(baseline, miss, criteria),
        stamp,
        compare(generations, reference),
        reference,
        criteria,
        per_judge(generations),
    )
    (runs / f"modeltest_{stamp}.md").write_text(text, encoding="utf-8")
    print(text)
    print(f"\nSaved to {runs / f'modeltest_{stamp}.json'}")


if __name__ == "__main__":
    main()
