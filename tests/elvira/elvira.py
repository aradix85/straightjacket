#!/usr/bin/env python3
"""Straightjacket — Elvira Test Player Bot.

Headless AI-driven test player. Two modes:

  Direct mode (default): drives the engine directly, bypassing the UI.
  WebSocket mode (--ws): plays through the WebSocket server, testing
    the full stack: protocol → handlers → engine → serializers.

Usage:
    python elvira/elvira.py
    python elvira/elvira.py --ws
    python elvira/elvira.py --config my_cfg.yaml
    python elvira/elvira.py --auto
    python elvira/elvira.py --turns 50
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Path setup — works regardless of cwd
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent  # tests/elvira/ → tests/ → repo root
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

# Console logging (no log files)
_logger = logging.getLogger("rpg_engine")
if not _logger.handlers:
    _ch = logging.StreamHandler(sys.stdout)
    _ch.setFormatter(logging.Formatter("%(message)s"))
    _logger.setLevel(logging.DEBUG)
    _logger.addHandler(_ch)

from tests.elvira.elvira_bot.runner import load_config, run_session

DEFAULT_CONFIG = _HERE / "elvira_config.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(description="Straightjacket — Elvira Test Player Bot")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to elvira_config.yaml")
    parser.add_argument("--auto", action="store_true", help="Override: enable full auto mode")
    parser.add_argument("--turns", type=int, default=None, help="Override: max turns per chapter")
    parser.add_argument(
        "--ws", action="store_true", help="WebSocket mode: play through the server instead of direct engine calls"
    )
    parser.add_argument("--port", type=int, default=None, help="Server port for --ws mode (default: from config.yaml)")
    parser.add_argument(
        "--setting", type=str, default=None, help="Override: setting_id (starforged, classic, sundered_isles)"
    )
    parser.add_argument(
        "--style",
        type=str,
        default=None,
        help="Override: play style (explorer, aggressor, dialogist, chaosagent, balanced)",
    )
    args = parser.parse_args()

    bot_cfg = load_config(args.config)

    if args.setting:
        bot_cfg.setdefault("game", {})["setting_id"] = args.setting
    if args.style:
        bot_cfg.setdefault("bot_behavior", {})["style"] = args.style

    if args.ws:
        if args.port:
            bot_cfg["ws_port"] = args.port
        from tests.elvira.elvira_bot.ws_runner import run_ws_session

        asyncio.run(run_ws_session(bot_cfg, auto_override=args.auto, turns_override=args.turns))
    else:
        run_session(bot_cfg, auto_override=args.auto, turns_override=args.turns)


if __name__ == "__main__":
    main()
