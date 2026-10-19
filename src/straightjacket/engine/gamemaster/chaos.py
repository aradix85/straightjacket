from __future__ import annotations

from ..logging_util import log
from ..models import GameState, WorldState
from .config import gm
from .npc.matching import find_npc


def tick_chaos(world: WorldState, direction: int) -> None:
    old = world.chaos_factor
    chaos = gm().chaos
    world.chaos_factor = max(chaos.min, min(chaos.max, world.chaos_factor + direction))
    if world.chaos_factor != old:
        log(f"[World] chaos {old}→{world.chaos_factor}")


def update_chaos_factor(game: GameState, outcome: str, target_npc_id: str | None) -> None:
    _c = gm().chaos
    if outcome in _c.adjust_by_outcome:
        tick_chaos(game.world, _c.adjust_by_outcome[outcome])
    elif outcome == "dialog" and target_npc_id:
        npc = find_npc(game, target_npc_id)
        if npc:
            if npc.disposition in _c.dialog_raising_dispositions:
                tick_chaos(game.world, _c.adjust_dialog_hostile)
            elif npc.disposition in _c.dialog_lowering_dispositions:
                tick_chaos(game.world, _c.adjust_dialog_friendly)
