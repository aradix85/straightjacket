"""Tests for consequences.py: dice, clocks, NPC agency, momentum burn.

Move-specific consequence tests are in test_move_outcome.py.
"""

from straightjacket.engine.models import (
    ClockData,
    ClockEvent,
    GameState,
    NpcData,
    Resources,
    RollResult,
)


def _game(health: int = 5, spirit: int = 5, supply: int = 5, momentum: int = 3) -> GameState:
    g = GameState(player_name="Hero")
    g.resources = Resources(health=health, spirit=spirit, supply=supply, momentum=momentum, max_momentum=10)
    return g


# ── Dice rolling ─────────────────────────────────────────────


def test_roll_action_returns_valid_result() -> None:
    from straightjacket.engine.mechanics.consequences import roll_action

    r = roll_action("edge", 3, "adventure/face_danger")
    assert r.result in ("STRONG_HIT", "WEAK_HIT", "MISS")
    assert r.move == "adventure/face_danger"
    assert r.stat_name == "edge"
    assert r.stat_value == 3
    assert r.action_score <= 10
    assert 1 <= r.d1 <= 6
    assert 1 <= r.d2 <= 6
    assert 1 <= r.c1 <= 10
    assert 1 <= r.c2 <= 10


def test_roll_action_match_detection() -> None:
    from straightjacket.engine.mechanics.consequences import roll_action

    matches = 0
    for _ in range(1000):
        r = roll_action("iron", 2, "combat/strike")
        if r.match:
            matches += 1
            assert r.c1 == r.c2
    assert matches > 0


def test_roll_action_score_capped_at_10() -> None:
    from straightjacket.engine.mechanics.consequences import roll_action

    for _ in range(100):
        r = roll_action("edge", 3, "adventure/face_danger")
        assert r.action_score <= 10


# ── Clock ticking ────────────────────────────────────────────


def test_tick_threat_clock() -> None:
    from straightjacket.engine.mechanics.consequences import tick_threat_clock

    game = _game()
    game.world.clocks = [ClockData(name="Storm", clock_type="threat", segments=4, filled=2)]
    events: list[ClockEvent] = []
    tick_threat_clock(game, 1, events)
    assert game.world.clocks[0].filled == 3
    assert len(events) == 0


def test_tick_threat_clock_fires_when_full() -> None:
    from straightjacket.engine.mechanics.consequences import tick_threat_clock

    game = _game()
    game.world.clocks = [ClockData(name="Storm", clock_type="threat", segments=4, filled=3)]
    events: list[ClockEvent] = []
    tick_threat_clock(game, 1, events)
    assert game.world.clocks[0].filled == 4
    assert game.world.clocks[0].fired is True
    assert len(events) == 1
    assert events[0].clock == "Storm"


def test_tick_threat_clock_skips_non_threat() -> None:
    from straightjacket.engine.mechanics.consequences import tick_threat_clock

    game = _game()
    game.world.clocks = [ClockData(name="Progress", clock_type="progress", segments=4, filled=2)]
    events: list[ClockEvent] = []
    tick_threat_clock(game, 1, events)
    assert game.world.clocks[0].filled == 2


def test_tick_threat_clock_skips_full() -> None:
    from straightjacket.engine.mechanics.consequences import tick_threat_clock

    game = _game()
    game.world.clocks = [ClockData(name="Done", clock_type="threat", segments=4, filled=4, fired=True)]
    events: list[ClockEvent] = []
    tick_threat_clock(game, 1, events)
    assert len(events) == 0


# ── Momentum burn ────────────────────────────────────────────


def test_can_burn_momentum_miss_to_strong() -> None:
    from straightjacket.engine.mechanics.consequences import can_burn_momentum

    game = _game(momentum=8)
    roll = RollResult(d1=1, d2=1, c1=5, c2=7, stat_name="wits", stat_value=2, action_score=4, result="MISS", move="x")
    assert can_burn_momentum(game, roll) == "STRONG_HIT"


def test_can_burn_momentum_miss_to_weak() -> None:
    from straightjacket.engine.mechanics.consequences import can_burn_momentum

    game = _game(momentum=6)
    roll = RollResult(d1=1, d2=1, c1=5, c2=7, stat_name="wits", stat_value=2, action_score=4, result="MISS", move="x")
    assert can_burn_momentum(game, roll) == "WEAK_HIT"


def test_can_burn_momentum_weak_to_strong() -> None:
    from straightjacket.engine.mechanics.consequences import can_burn_momentum

    game = _game(momentum=8)
    roll = RollResult(
        d1=3, d2=3, c1=5, c2=7, stat_name="wits", stat_value=2, action_score=8, result="WEAK_HIT", move="x"
    )
    assert can_burn_momentum(game, roll) == "STRONG_HIT"


def test_can_burn_momentum_no_burn_possible() -> None:
    from straightjacket.engine.mechanics.consequences import can_burn_momentum

    game = _game(momentum=2)
    roll = RollResult(d1=1, d2=1, c1=5, c2=7, stat_name="wits", stat_value=2, action_score=4, result="MISS", move="x")
    assert can_burn_momentum(game, roll) is None


def test_can_burn_momentum_zero_momentum() -> None:
    from straightjacket.engine.mechanics.consequences import can_burn_momentum

    game = _game(momentum=0)
    roll = RollResult(d1=1, d2=1, c1=5, c2=7, stat_name="wits", stat_value=2, action_score=4, result="MISS", move="x")
    assert can_burn_momentum(game, roll) is None


# ── NPC agency ───────────────────────────────────────────────


def test_npc_agency_fires_on_scene_5(load_engine: None) -> None:
    from straightjacket.engine.mechanics.consequences import check_npc_agency

    game = _game()
    game.narrative.scene_count = 5
    npc = NpcData(id="npc_1", name="Kira", status="active", agenda="find the vault")
    game.npcs.append(npc)
    actions, _ = check_npc_agency(game)
    assert len(actions) == 1
    assert "Kira" in actions[0]


def test_npc_agency_skips_non_multiple_of_5(load_engine: None) -> None:
    from straightjacket.engine.mechanics.consequences import check_npc_agency

    game = _game()
    game.narrative.scene_count = 3
    npc = NpcData(id="npc_1", name="Kira", status="active", agenda="find the vault")
    game.npcs.append(npc)
    actions, _ = check_npc_agency(game)
    assert len(actions) == 0


def test_npc_agency_ticks_owned_clock(load_engine: None) -> None:
    from straightjacket.engine.mechanics.consequences import check_npc_agency

    game = _game()
    game.narrative.scene_count = 5
    npc = NpcData(id="npc_1", name="Kira", status="active", agenda="find the vault")
    game.npcs.append(npc)
    game.world.clocks = [ClockData(name="Kira's scheme", clock_type="scheme", segments=4, filled=1, owner="Kira")]
    actions, events = check_npc_agency(game)
    assert game.world.clocks[0].filled == 2
    assert len(events) == 1


# ── Autonomous clocks ────────────────────────────────────────


def test_autonomous_clock_tick(load_engine: None) -> None:
    from straightjacket.engine.mechanics.consequences import tick_autonomous_clocks

    game = _game()
    game.world.clocks = [ClockData(name="Plague", clock_type="threat", segments=6, filled=2, owner="world")]
    ticked = False
    for _ in range(100):
        game.world.clocks[0].filled = 2
        events = tick_autonomous_clocks(game)
        if events:
            ticked = True
            break
    assert ticked


# ── Purge fired clocks ───────────────────────────────────────


def test_purge_old_fired_clocks(load_engine: None) -> None:
    from straightjacket.engine.mechanics.consequences import purge_old_fired_clocks

    game = _game()
    game.narrative.scene_count = 10
    game.world.clocks = [
        ClockData(name="Old", clock_type="threat", segments=4, filled=4, fired=True, fired_at_scene=3),
        ClockData(name="Recent", clock_type="threat", segments=4, filled=4, fired=True, fired_at_scene=9),
        ClockData(name="Active", clock_type="threat", segments=4, filled=2),
    ]
    purge_old_fired_clocks(game)
    names = [c.name for c in game.world.clocks]
    assert "Old" not in names
    assert "Recent" in names
    assert "Active" in names


# ── Progress roll ────────────────────────────────────────────


def test_roll_progress_returns_valid_result() -> None:
    from straightjacket.engine.mechanics.consequences import roll_progress

    r = roll_progress("Test Vow", 6, "quest/fulfill_your_vow")
    assert r.result in ("STRONG_HIT", "WEAK_HIT", "MISS")
    assert r.move == "quest/fulfill_your_vow"
    assert r.stat_name == "Test Vow"
    assert r.stat_value == 6
    assert r.action_score == 6
    assert r.d1 == 0  # no action dice
    assert r.d2 == 0
    assert 1 <= r.c1 <= 10
    assert 1 <= r.c2 <= 10


def test_roll_progress_score_capped_at_10() -> None:
    from straightjacket.engine.mechanics.consequences import roll_progress

    r = roll_progress("Epic", 15, "quest/fulfill_your_vow")
    assert r.action_score == 10


def test_roll_progress_zero_boxes() -> None:
    from straightjacket.engine.mechanics.consequences import roll_progress

    r = roll_progress("Empty", 0, "quest/fulfill_your_vow")
    assert r.action_score == 0
    # With score 0, can only beat challenge dice of 0 (impossible), so always MISS
    # unless both challenge dice are somehow 0 (they can't be, range 1-10)
    # Actually score 0 can never be > c1 or > c2 since minimum c is 1
    assert r.result == "MISS"


def test_roll_progress_match_detection() -> None:
    from straightjacket.engine.mechanics.consequences import roll_progress

    matches = 0
    for _ in range(1000):
        r = roll_progress("Vow", 5, "quest/fulfill_your_vow")
        if r.match:
            matches += 1
            assert r.c1 == r.c2
    assert matches > 0
