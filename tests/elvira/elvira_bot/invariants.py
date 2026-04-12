"""State invariant checker. Reads limits from engine.yaml — no hardcoded values."""

from __future__ import annotations

from straightjacket.engine.engine_config import EngineSettings
from straightjacket.engine.engine_loader import eng
from straightjacket.engine.models import ClockData, GameState, MemoryEntry, NpcData


def assert_game_state(game: GameState, turn: int) -> list[str]:
    """Check all game state invariants. Returns list of violation strings."""
    violations: list[str] = []
    _e = eng()

    def check(condition: bool, msg: str) -> None:
        if not condition:
            violations.append(f"[TURN {turn}] {msg}")

    res = game.resources
    world = game.world

    # Resource ranges (from engine.yaml)
    check(0 <= res.health <= _e.resources.health_max, f"health={res.health} out of [0,{_e.resources.health_max}]")
    check(0 <= res.spirit <= _e.resources.spirit_max, f"spirit={res.spirit} out of [0,{_e.resources.spirit_max}]")
    check(0 <= res.supply <= _e.resources.supply_max, f"supply={res.supply} out of [0,{_e.resources.supply_max}]")
    check(
        _e.momentum.floor <= res.momentum <= _e.momentum.max,
        f"momentum={res.momentum} out of [{_e.momentum.floor},{_e.momentum.max}]",
    )
    check(res.momentum <= res.max_momentum, f"momentum={res.momentum} > max_momentum={res.max_momentum}")

    # Chaos factor (from engine.yaml)
    check(
        _e.chaos.min <= world.chaos_factor <= _e.chaos.max,
        f"chaos_factor={world.chaos_factor} out of [{_e.chaos.min},{_e.chaos.max}]",
    )

    # Scene count
    check(game.narrative.scene_count >= 1, f"scene_count={game.narrative.scene_count} < 1")

    # Crisis/game_over consistency
    if res.health > 0 and res.spirit > 0:
        check(not game.crisis_mode, f"crisis_mode=True but health={res.health} spirit={res.spirit} (both > 0)")
    if res.health <= 0 and res.spirit <= 0:
        check(game.game_over, f"game_over=False but health={res.health} spirit={res.spirit} (both <= 0)")

    # NPC invariants
    for npc in game.npcs:
        _check_npc(npc, turn, violations, _e)

    # Clock invariants
    for clock in world.clocks:
        _check_clock(clock, turn, violations)

    # Combat position
    check(
        world.combat_position in ("", "in_control", "bad_spot"),
        f"invalid combat_position '{world.combat_position}'",
    )

    # Progress track invariants (progress_tracks)
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

    # Mythic threads invariants
    thread_ids = set()
    for t in game.narrative.threads:
        check(t.id != "", "thread with empty id")
        check(t.id not in thread_ids, f"duplicate thread id '{t.id}'")
        thread_ids.add(t.id)
        check(t.weight > 0, f"thread '{t.id}' weight={t.weight} <= 0")

    # Mythic characters list invariants
    char_ids = set()
    for c in game.narrative.characters_list:
        check(c.id != "", "character_list entry with empty id")
        check(c.id not in char_ids, f"duplicate character_list id '{c.id}'")
        char_ids.add(c.id)

    # Truths consistency (if present, should be non-empty strings)
    for truth_id, summary in game.truths.items():
        check(bool(summary.strip()), f"truth '{truth_id}' has empty summary")

    # Assets (if present, should be non-empty strings)
    for asset_id in game.assets:
        check(bool(asset_id.strip()), "empty asset id in assets list")

    # Session log consistency
    if game.narrative.session_log:
        last = game.narrative.session_log[-1]
        check(
            last.scene == game.narrative.scene_count,
            f"session_log last scene={last.scene} != scene_count={game.narrative.scene_count}",
        )

    return violations


def _check_npc(npc: NpcData, turn: int, violations: list[str], _e: EngineSettings) -> None:
    """Check NPC field invariants."""

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
    check(0 <= npc.bond <= npc.bond_max, f"bond={npc.bond} out of [0,{npc.bond_max}]")
    check(isinstance(npc.memory, list), f"memory is {type(npc.memory).__name__}, not list")
    check(isinstance(npc.aliases, list), f"aliases is {type(npc.aliases).__name__}, not list")

    # Memory entry structure
    for i, m in enumerate(npc.memory):
        if isinstance(m, MemoryEntry):
            check(bool(m.event), f"memory[{i}] missing 'event'")
            check(bool(m.type), f"memory[{i}] missing 'type'")
            check(m.importance > 0, f"memory[{i}] missing 'importance'")
        else:
            violations.append(f"[TURN {turn}] NPC '{npc.name}': memory[{i}] is {type(m).__name__}, not MemoryEntry")

    # Alias sanity: name should not be in aliases
    name_lower = npc.name.lower()
    for alias in npc.aliases:
        check(alias.lower() != name_lower, f"alias '{alias}' duplicates primary name")

    # Memory limits
    max_mem = _e.npc.max_memory_entries
    check(
        len(npc.memory) <= max_mem + 5,  # +5 tolerance for mid-turn state
        f"memory count {len(npc.memory)} exceeds limit {max_mem}",
    )


def _check_clock(clock: ClockData, turn: int, violations: list[str]) -> None:
    """Check clock field invariants."""

    def check(condition: bool, msg: str) -> None:
        if not condition:
            violations.append(f"[TURN {turn}] Clock '{clock.name}': {msg}")

    check(clock.name != "", "empty name")
    check(clock.clock_type in ("threat", "scheme", "progress"), f"invalid clock_type '{clock.clock_type}'")
    check(clock.segments > 0, f"segments={clock.segments} <= 0")
    check(0 <= clock.filled <= clock.segments, f"filled={clock.filled} out of [0,{clock.segments}]")
    if clock.fired:
        check(clock.filled >= clock.segments, f"fired=True but filled={clock.filled} < segments={clock.segments}")
