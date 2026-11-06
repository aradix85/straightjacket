from __future__ import annotations

from typing import TYPE_CHECKING

from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.setting.packages import load_package

if TYPE_CHECKING:
    from straightjacket.engine.models import BrainResult, GameState


def is_dialog_branch(brain: BrainResult) -> bool:
    return brain.dialog_only or brain.move in gm().moves


def asks_the_oracle(move: str) -> bool:
    return move == "ask_the_oracle"


def roll_oracle_answer(game: GameState) -> str:
    action, theme = load_package(game.setting_id).roll_action_theme()
    return f"{action} / {theme}"
