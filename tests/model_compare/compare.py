import argparse
import copy
import io
import os
import sys
from functools import partial
from pathlib import Path
from unittest import mock

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))
os.environ.setdefault("STRAIGHTJACKET_USERS_DIR", str(_ROOT / "tests" / "elvira" / "users"))

from straightjacket.engine.ai.api_client import get_provider
from tests.elvira import elvira
from tests.elvira.elvira_bot import runner
from tests.elvira.elvira_bot.console import say, show_on_console
from tests.model_compare.calls import RecordingProvider
from tests.model_compare.judging import write_packets, write_summary
from tests.model_compare.replay import CALLS, replay
from tests.model_compare.settings import RUNS, CompareSettings, load_settings


def _recorded(path: Path, source: str) -> RecordingProvider:
    return RecordingProvider(get_provider(), path, source)


def capture(run_dir: Path, settings: CompareSettings) -> None:
    run_dir.mkdir(parents=True)
    bot_cfg = runner.load_config(elvira.DEFAULT_CONFIG)
    for source in settings.sources:
        run_cfg = elvira.scenario_cfg(bot_cfg, source.scenario) if source.scenario else copy.deepcopy(bot_cfg)
        if source.style:
            run_cfg["bot_behavior"]["style"] = source.style
        with mock.patch.object(runner, "get_provider", partial(_recorded, run_dir / CALLS, source.name)):
            runner.run_session(run_cfg, auto_override=True, turns_override=source.turns)


def replay_round(run_dir: Path, settings: CompareSettings, args: argparse.Namespace) -> None:
    names = args.configs or list(settings.configurations)
    chosen = {name: settings.configurations[name] for name in names}
    ids = set(args.calls or [])
    done = replay(run_dir, chosen, settings.prices, lambda c: not ids or c.call_id in ids, again=args.again)
    say(f"{done.answered} answered, {done.failed} failed, {done.truncated} cut off, ${done.cost:.2f} in all")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Straightjacket: compare models on captured AI calls, judged blind")
    parser.add_argument("command", choices=["capture", "replay", "packets", "summary"])
    parser.add_argument("run", help="the run's folder under tests/model_compare/runs")
    parser.add_argument("--configs", nargs="*", default=[], help="replay: configurations by name, all when none")
    parser.add_argument("--calls", nargs="*", default=[], help="replay: captured calls by id, all when none")
    parser.add_argument("--again", action="store_true", help="replay: answer every pair once more")
    return parser.parse_args()


def main() -> None:
    show_on_console()
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = _parse_args()
    settings = load_settings()
    run_dir = RUNS / args.run
    if args.command == "capture":
        capture(run_dir, settings)
    elif args.command == "replay":
        replay_round(run_dir, settings, args)
    elif args.command == "packets":
        say(f"{write_packets(run_dir, settings.rubrics)} packets written")
    else:
        say(write_summary(run_dir, settings.configurations, settings.prices))


if __name__ == "__main__":
    main()
