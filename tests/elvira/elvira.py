import argparse
import asyncio
import copy
import logging
import sys
from pathlib import Path


_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))


_logger = logging.getLogger("rpg_engine")
if not _logger.handlers:
    _ch = logging.StreamHandler(sys.stdout)
    _ch.setFormatter(logging.Formatter("%(message)s"))
    _logger.setLevel(logging.DEBUG)
    _logger.addHandler(_ch)

from tests.elvira.elvira_bot.ai_helpers import available_styles
from tests.elvira.elvira_bot.runner import load_config, run_session, selectable_settings

DEFAULT_CONFIG = _HERE / "elvira_config.yaml"


def _scenario_cfg(bot_cfg: dict, name: str) -> dict:
    spec = bot_cfg["scenarios"][name]
    run_cfg = copy.deepcopy(bot_cfg)
    run_cfg["session"]["scenario"] = name
    run_cfg["session"]["max_turns"] = spec["turns"]
    if "max_chapters" in spec:
        run_cfg["session"]["max_chapters"] = spec["max_chapters"]
    for key in ("style", "burn_momentum"):
        if key in spec:
            run_cfg["bot_behavior"][key] = spec[key]
    return run_cfg


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Straightjacket — Elvira Test Player Bot")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to elvira_config.yaml")
    parser.add_argument("--auto", action="store_true", help="Override: enable full auto mode")
    parser.add_argument("--turns", type=int, default=None, help="Override: max turns per chapter")
    parser.add_argument(
        "--ws", action="store_true", help="WebSocket mode: play through the server instead of direct engine calls"
    )
    parser.add_argument("--port", type=int, default=None, help="Server port for --ws mode (default: from config.yaml)")
    parser.add_argument(
        "--setting", type=str, default=None, help="Override: setting_id; random per run when empty in the config"
    )
    parser.add_argument(
        "--style",
        type=str,
        default=None,
        help="Override: play style; random per run when empty in the config",
    )
    parser.add_argument("--matrix", action="store_true", help="Play one session for every setting and style in turn")
    parser.add_argument(
        "--scenario", type=str, default=None, help="Play a prepared situation from the config, or 'all'"
    )
    args = parser.parse_args()

    bot_cfg = load_config(args.config)

    if args.setting:
        bot_cfg.setdefault("game", {})["setting_id"] = args.setting
    if args.style:
        bot_cfg.setdefault("bot_behavior", {})["style"] = args.style

    if args.scenario:
        names = list(bot_cfg["scenarios"]) if args.scenario == "all" else [args.scenario]
        for name in names:
            run_session(_scenario_cfg(bot_cfg, name), auto_override=args.auto, turns_override=args.turns)
        return

    if args.matrix:
        for setting_id in selectable_settings():
            for style in available_styles():
                run_cfg = copy.deepcopy(bot_cfg)
                run_cfg["game"]["setting_id"] = setting_id
                run_cfg["bot_behavior"]["style"] = style
                run_session(run_cfg, auto_override=args.auto, turns_override=args.turns)
        return

    if args.ws:
        if args.port:
            bot_cfg["ws_port"] = args.port
        from tests.elvira.elvira_bot.ws_runner import run_ws_session

        asyncio.run(run_ws_session(bot_cfg, auto_override=args.auto, turns_override=args.turns))
    else:
        run_session(bot_cfg, auto_override=args.auto, turns_override=args.turns)


if __name__ == "__main__":
    main()
