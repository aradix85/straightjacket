from __future__ import annotations

from ..models import BrainResult, GameState
from ..setting.packages import load_package
from .config import gm


def is_dialog_branch(brain: BrainResult) -> bool:
    return brain.dialog_only or brain.move in gm().moves


def is_dialog_memory(brain: BrainResult, roll_present: bool) -> bool:
    return is_dialog_branch(brain) or not roll_present


def asks_the_oracle(move: str) -> bool:
    return move == "ask_the_oracle"


def roll_oracle_answer(game: GameState) -> str:
    action, theme = load_package(game.setting_id).roll_action_theme()
    return f"{action} / {theme}"
