from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from straightjacket.engine.gamemaster.config import gm

if TYPE_CHECKING:
    from straightjacket.engine.models import ClockData, GameState, NpcData


@dataclass(frozen=True)
class Danger:
    id: str
    name: str
    progress: int
    open: bool


class RulesetAnswers(Protocol):
    def outcome(self, result: str) -> str: ...
    def action_kind(self, move: str) -> str: ...
    def action_phrase(self, move: str) -> str: ...
    def time_taken(self, move: str) -> str: ...
    def effect_bonus(self, move: str) -> int: ...
    def closeness(self, game: GameState, npc_id: str) -> int: ...
    def strain(self, game: GameState) -> list[str]: ...
    def gained_advantage(self, game: GameState) -> bool: ...
    def gathers_information(self, move: str) -> bool: ...
    def dangers(self, game: GameState) -> list[Danger]: ...
    def add_danger(self, game: GameState, origin: str, source: str, named: tuple[str, str] | None) -> None: ...
    def merge_npcs(self, game: GameState, kept: NpcData, merged: NpcData) -> None: ...
    def clock_filled(self, game: GameState, clock: ClockData) -> None: ...


_installed: list[RulesetAnswers] = []


def install_answers(ruleset: RulesetAnswers) -> None:
    _installed[:] = [ruleset]


def answers() -> RulesetAnswers:
    if not _installed:
        msg = "No ruleset answers the game master; the server and Elvira install one when they start"
        raise RuntimeError(msg)
    return _installed[0]


def outcome_of(result: str) -> str:
    return result if result in gm().outcomes.unrolled else answers().outcome(result)


def gained(result: str) -> bool:
    return outcome_of(result) in gm().outcomes.gained
