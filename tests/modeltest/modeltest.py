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
from tests.modeltest.measure import check_models, contestants, judges_from, measure, report, summarize


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
    args = parser.parse_args()

    settings = _load("modeltest_config.yaml")
    if args.capture:
        for line in capture_all(_load("modeltest_scenarios.yaml"), _HERE / "scenarios", settings):
            print(line)
        return

    scenarios = _scenarios()
    voices = contestants(args.models, settings)
    judges = judges_from(settings)
    check_models([*voices, *judges])
    attempts = args.attempts if args.attempts is not None else settings["attempts"]
    print(f"Measuring {', '.join(v.label for v in voices)}: {len(scenarios)} scenes, {attempts} attempts each")
    generations = measure(voices, scenarios, judges, settings, _load("modeltest_prompts.yaml"), attempts)

    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    runs = _HERE / "runs"
    runs.mkdir(exist_ok=True)
    (runs / f"modeltest_{stamp}.json").write_text(
        json.dumps(generations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    miss = {name for name, scenario in scenarios.items() if scenario["result"] == "MISS"}
    baseline = json.loads((_HERE / settings["baseline"]).read_text(encoding="utf-8"))
    text = report(summarize(generations, miss), summarize(baseline, miss), stamp)
    (runs / f"modeltest_{stamp}.md").write_text(text, encoding="utf-8")
    print(text)
    print(f"\nSaved to {runs / f'modeltest_{stamp}.json'}")


if __name__ == "__main__":
    main()
