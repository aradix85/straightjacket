from __future__ import annotations

from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.models import ClockData, GameState, MemoryEntry, NpcData
from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.meters import condition_meters, in_crisis, max_momentum, momentum


def assert_game_state(game: GameState, turn: int) -> list[str]:
    violations: list[str] = []

    def check(condition: bool, msg: str) -> None:
        if not condition:
            violations.append(f"[TURN {turn}] {msg}")

    meters = game.resources.meters
    world = game.world

    for name, meter in condition_meters(game.setting_id).items():
        check(meter.min <= meters[name] <= meter.max, f"{name}={meters[name]} out of [{meter.min},{meter.max}]")
    floor, ceiling = rules().momentum.floor, max_momentum(game)
    check(floor <= momentum(game) <= ceiling, f"momentum={momentum(game)} out of [{floor},{ceiling}]")

    check(
        gm().chaos.min <= world.chaos_factor <= gm().chaos.max,
        f"chaos_factor={world.chaos_factor} out of [{gm().chaos.min},{gm().chaos.max}]",
    )

    check(game.narrative.scene_count >= 1, f"scene_count={game.narrative.scene_count} < 1")

    crisis_meters = {name: meters[name] for name in rules().meters.crisis_at_zero}
    check(game.crisis_mode == in_crisis(game), f"crisis_mode={game.crisis_mode} but {crisis_meters}")

    for npc in game.npcs:
        _check_npc(npc, turn, violations)

    for clock in world.clocks:
        _check_clock(clock, turn, violations)

    check(
        world.combat_position in ("", "in_control", "bad_spot"),
        f"invalid combat_position '{world.combat_position}'",
    )

    for track in game.progress_tracks:
        check(track.id != "", "progress_track with empty id")
        check(track.name != "", f"progress_track '{track.id}' with empty name")
        check(
            track.rank in ("troublesome", "dangerous", "formidable", "extreme", "epic"),
            f"progress_track '{track.id}' invalid rank '{track.rank}'",
        )
        check(
            0 <= track.ticks <= track.max_ticks,
            f"progress_track '{track.id}' ticks={track.ticks} out of [0,{track.max_ticks}]",
        )

    thread_ids = set()
    for t in game.narrative.threads:
        check(t.id != "", "thread with empty id")
        check(t.id not in thread_ids, f"duplicate thread id '{t.id}'")
        thread_ids.add(t.id)
        check(t.weight > 0, f"thread '{t.id}' weight={t.weight} <= 0")

    char_ids = set()
    for c in game.narrative.characters_list:
        check(c.id != "", "character_list entry with empty id")
        check(c.id not in char_ids, f"duplicate character_list id '{c.id}'")
        char_ids.add(c.id)

    for truth_id, summary in game.truths.items():
        check(bool(summary.strip()), f"truth '{truth_id}' has empty summary")

    for asset_id in game.assets:
        check(bool(asset_id.strip()), "empty asset id in assets list")

    if game.narrative.session_log:
        last = game.narrative.session_log[-1]
        check(
            last.scene == game.narrative.scene_count,
            f"session_log last scene={last.scene} != scene_count={game.narrative.scene_count}",
        )

    _check_combat_track_sync(game, turn, violations)

    return violations


def _check_npc(npc: NpcData, turn: int, violations: list[str]) -> None:
    def check(condition: bool, msg: str) -> None:
        if not condition:
            violations.append(f"[TURN {turn}] NPC '{npc.name}': {msg}")

    check(npc.id != "", "empty id")
    check(npc.name != "", "empty name")
    check(npc.status in ("active", "background", "deceased", "lore"), f"invalid status '{npc.status}'")
    check(
        npc.disposition in ("hostile", "distrustful", "neutral", "friendly", "loyal"),
        f"invalid disposition '{npc.disposition}'",
    )
    check(isinstance(npc.memory, list), f"memory is {type(npc.memory).__name__}, not list")
    check(isinstance(npc.aliases, list), f"aliases is {type(npc.aliases).__name__}, not list")

    for i, m in enumerate(npc.memory):
        if isinstance(m, MemoryEntry):
            check(bool(m.event), f"memory[{i}] missing 'event'")
            check(bool(m.type), f"memory[{i}] missing 'type'")
            check(m.importance > 0, f"memory[{i}] missing 'importance'")
        else:
            violations.append(f"[TURN {turn}] NPC '{npc.name}': memory[{i}] is {type(m).__name__}, not MemoryEntry")

    name_lower = npc.name.lower()
    for alias in npc.aliases:
        check(alias.lower() != name_lower, f"alias '{alias}' duplicates primary name")

    max_mem = gm().npc.max_memory_entries
    check(
        len(npc.memory) <= max_mem + 5,
        f"memory count {len(npc.memory)} exceeds limit {max_mem}",
    )


def _check_clock(clock: ClockData, turn: int, violations: list[str]) -> None:
    def check(condition: bool, msg: str) -> None:
        if not condition:
            violations.append(f"[TURN {turn}] Clock '{clock.name}': {msg}")

    check(clock.name != "", "empty name")
    clock_types = ("threat", "scheme", "progress", rules().suffer.dying_clock.clock_type)
    check(clock.clock_type in clock_types, f"invalid clock_type '{clock.clock_type}'")
    check(clock.segments > 0, f"segments={clock.segments} <= 0")
    check(0 <= clock.filled <= clock.segments, f"filled={clock.filled} out of [0,{clock.segments}]")
    if clock.fired:
        check(clock.filled >= clock.segments, f"fired=True but filled={clock.filled} < segments={clock.segments}")


def _check_combat_track_sync(game: GameState, turn: int, violations: list[str]) -> None:
    cp = game.world.combat_position
    active_combat_tracks = [
        t for t in game.progress_tracks if t.status == "active" and getattr(t, "track_type", "") == "combat"
    ]
    if cp in ("in_control", "bad_spot") and not active_combat_tracks:
        violations.append(f"[TURN {turn}] Combat sync: combat_position='{cp}' but no active combat track")
    if cp == "" and active_combat_tracks:
        names = ", ".join(t.name for t in active_combat_tracks)
        violations.append(
            f"[TURN {turn}] Combat sync: combat_position cleared but orphan active combat track(s): {names}"
        )


def check_turn_replacement(
    before: GameState, after: GameState, narration: str, turn: int, kind: str, keeps_location: bool
) -> list[str]:
    violations: list[str] = []

    def check(condition: bool, msg: str) -> None:
        if not condition:
            violations.append(f"[TURN {turn}] {kind}: {msg}")

    old_history, new_history = before.narrative.narration_history, after.narrative.narration_history
    check(len(new_history) == len(old_history), f"narration history {len(old_history)} → {len(new_history)} entries")
    check(
        [h.to_dict() for h in new_history[:-1]] == [h.to_dict() for h in old_history[:-1]],
        "an earlier narration entry changed",
    )
    check(bool(new_history) and new_history[-1].narration == narration, "last narration entry is not the new one")

    old_log, new_log = before.narrative.session_log, after.narrative.session_log
    check(len(new_log) == len(old_log), f"session log {len(old_log)} → {len(new_log)} entries")
    check(
        [e.to_dict() for e in new_log[:-1]] == [e.to_dict() for e in old_log[:-1]],
        "an earlier session log entry changed",
    )
    check(
        after.narrative.scene_count == before.narrative.scene_count,
        f"scene count {before.narrative.scene_count} → {after.narrative.scene_count}",
    )
    if keeps_location:
        check(
            after.world.current_location == before.world.current_location,
            f"location {before.world.current_location!r} → {after.world.current_location!r}",
        )
    snap = after.last_turn_snapshot
    check(snap is not None and snap.narration == narration, "turn snapshot does not hold the new narration")
    return violations
