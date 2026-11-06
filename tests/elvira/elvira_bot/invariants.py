from __future__ import annotations

from typing import TYPE_CHECKING

from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.models import MemoryEntry
from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.meters import condition_meters, in_crisis, max_momentum, momentum

if TYPE_CHECKING:
    from straightjacket.engine.models import ClockData, GameState, NpcData


def assert_game_state(game: GameState, turn: int) -> list[str]:
    violations: list[str] = []

    def check(*, condition: bool, msg: str) -> None:
        if not condition:
            violations.append(f"[TURN {turn}] {msg}")

    meters = game.resources.meters
    world = game.world

    for name, meter in condition_meters(game.setting_id).items():
        check(
            condition=meter.min <= meters[name] <= meter.max,
            msg=f"{name}={meters[name]} out of [{meter.min},{meter.max}]",
        )
    floor, ceiling = rules().momentum.floor, max_momentum(game)
    check(condition=floor <= momentum(game) <= ceiling, msg=f"momentum={momentum(game)} out of [{floor},{ceiling}]")

    check(
        condition=gm().chaos.min <= world.chaos_factor <= gm().chaos.max,
        msg=f"chaos_factor={world.chaos_factor} out of [{gm().chaos.min},{gm().chaos.max}]",
    )

    check(condition=game.narrative.scene_count >= 1, msg=f"scene_count={game.narrative.scene_count} < 1")

    crisis_meters = {name: meters[name] for name in rules().meters.crisis_at_zero}
    check(condition=game.crisis_mode == in_crisis(game), msg=f"crisis_mode={game.crisis_mode} but {crisis_meters}")

    for npc in game.npcs:
        _check_npc(npc, turn, violations)

    for clock in world.clocks:
        _check_clock(clock, turn, violations)

    check(
        condition=world.combat_position in {"", "in_control", "bad_spot"},
        msg=f"invalid combat_position '{world.combat_position}'",
    )

    for track in game.progress_tracks:
        check(condition=bool(track.id), msg="progress_track with empty id")
        check(condition=bool(track.name), msg=f"progress_track '{track.id}' with empty name")
        check(
            condition=track.rank in {"troublesome", "dangerous", "formidable", "extreme", "epic"},
            msg=f"progress_track '{track.id}' invalid rank '{track.rank}'",
        )
        check(
            condition=0 <= track.ticks <= track.max_ticks,
            msg=f"progress_track '{track.id}' ticks={track.ticks} out of [0,{track.max_ticks}]",
        )

    thread_ids = set()
    for t in game.narrative.threads:
        check(condition=bool(t.id), msg="thread with empty id")
        check(condition=t.id not in thread_ids, msg=f"duplicate thread id '{t.id}'")
        thread_ids.add(t.id)
        check(condition=t.weight > 0, msg=f"thread '{t.id}' weight={t.weight} <= 0")

    char_ids = set()
    for c in game.narrative.characters_list:
        check(condition=bool(c.id), msg="character_list entry with empty id")
        check(condition=c.id not in char_ids, msg=f"duplicate character_list id '{c.id}'")
        char_ids.add(c.id)

    for truth_id, summary in game.truths.items():
        check(condition=bool(summary.strip()), msg=f"truth '{truth_id}' has empty summary")

    for asset_id in game.assets:
        check(condition=bool(asset_id.strip()), msg="empty asset id in assets list")

    if game.narrative.session_log:
        last = game.narrative.session_log[-1]
        check(
            condition=last.scene == game.narrative.scene_count,
            msg=f"session_log last scene={last.scene} != scene_count={game.narrative.scene_count}",
        )

    _check_combat_track_sync(game, turn, violations)

    return violations


def _check_npc(npc: NpcData, turn: int, violations: list[str]) -> None:
    def check(*, condition: bool, msg: str) -> None:
        if not condition:
            violations.append(f"[TURN {turn}] NPC '{npc.name}': {msg}")

    check(condition=bool(npc.id), msg="empty id")
    check(condition=bool(npc.name), msg="empty name")
    check(condition=npc.status in {"active", "background", "deceased", "lore"}, msg=f"invalid status '{npc.status}'")
    check(
        condition=npc.disposition in {"hostile", "distrustful", "neutral", "friendly", "loyal"},
        msg=f"invalid disposition '{npc.disposition}'",
    )
    check(condition=isinstance(npc.memory, list), msg=f"memory is {type(npc.memory).__name__}, not list")
    check(condition=isinstance(npc.aliases, list), msg=f"aliases is {type(npc.aliases).__name__}, not list")

    memory: list[object] = list(npc.memory)
    for i, m in enumerate(memory):
        if isinstance(m, MemoryEntry):
            check(condition=bool(m.event), msg=f"memory[{i}] missing 'event'")
            check(condition=bool(m.type), msg=f"memory[{i}] missing 'type'")
            check(condition=m.importance > 0, msg=f"memory[{i}] missing 'importance'")
        else:
            violations.append(f"[TURN {turn}] NPC '{npc.name}': memory[{i}] is {type(m).__name__}, not MemoryEntry")

    name_lower = npc.name.lower()
    for alias in npc.aliases:
        check(condition=alias.lower() != name_lower, msg=f"alias '{alias}' duplicates primary name")

    max_mem = gm().npc.max_memory_entries
    check(
        condition=len(npc.memory) <= max_mem + 5,
        msg=f"memory count {len(npc.memory)} exceeds limit {max_mem}",
    )


def _check_clock(clock: ClockData, turn: int, violations: list[str]) -> None:
    def check(*, condition: bool, msg: str) -> None:
        if not condition:
            violations.append(f"[TURN {turn}] Clock '{clock.name}': {msg}")

    check(condition=bool(clock.name), msg="empty name")
    clock_types = ("threat", "scheme", "progress", rules().suffer.dying_clock.clock_type)
    check(condition=clock.clock_type in clock_types, msg=f"invalid clock_type '{clock.clock_type}'")
    check(condition=clock.segments > 0, msg=f"segments={clock.segments} <= 0")
    check(condition=0 <= clock.filled <= clock.segments, msg=f"filled={clock.filled} out of [0,{clock.segments}]")
    if clock.fired:
        check(
            condition=clock.filled >= clock.segments,
            msg=f"fired=True but filled={clock.filled} < segments={clock.segments}",
        )


def _check_combat_track_sync(game: GameState, turn: int, violations: list[str]) -> None:
    cp = game.world.combat_position
    active_combat_tracks = [
        t for t in game.progress_tracks if t.status == "active" and getattr(t, "track_type", "") == "combat"
    ]
    if cp in {"in_control", "bad_spot"} and not active_combat_tracks:
        violations.append(f"[TURN {turn}] Combat sync: combat_position='{cp}' but no active combat track")
    if not cp and active_combat_tracks:
        names = ", ".join(t.name for t in active_combat_tracks)
        violations.append(
            f"[TURN {turn}] Combat sync: combat_position cleared but orphan active combat track(s): {names}"
        )


def check_turn_replacement(
    before: GameState, after: GameState, narration: str, turn: int, kind: str, *, keeps_location: bool
) -> list[str]:
    violations: list[str] = []

    def check(*, condition: bool, msg: str) -> None:
        if not condition:
            violations.append(f"[TURN {turn}] {kind}: {msg}")

    old_history, new_history = before.narrative.narration_history, after.narrative.narration_history
    check(
        condition=len(new_history) == len(old_history),
        msg=f"narration history {len(old_history)} → {len(new_history)} entries",
    )
    check(
        condition=[h.to_dict() for h in new_history[:-1]] == [h.to_dict() for h in old_history[:-1]],
        msg="an earlier narration entry changed",
    )
    check(
        condition=bool(new_history) and new_history[-1].narration == narration,
        msg="last narration entry is not the new one",
    )

    old_log, new_log = before.narrative.session_log, after.narrative.session_log
    check(condition=len(new_log) == len(old_log), msg=f"session log {len(old_log)} → {len(new_log)} entries")
    check(
        condition=[e.to_dict() for e in new_log[:-1]] == [e.to_dict() for e in old_log[:-1]],
        msg="an earlier session log entry changed",
    )
    check(
        condition=after.narrative.scene_count == before.narrative.scene_count,
        msg=f"scene count {before.narrative.scene_count} → {after.narrative.scene_count}",
    )
    if keeps_location:
        check(
            condition=after.world.current_location == before.world.current_location,
            msg=f"location {before.world.current_location!r} → {after.world.current_location!r}",
        )
    snap = after.last_turn_snapshot
    check(
        condition=snap is not None and snap.narration == narration, msg="turn snapshot does not hold the new narration"
    )
    return violations
