import pytest

from straightjacket.engine.models import (
    ClockEvent,
    GameState,
    Resources,
    RollResult,
)
from tests._helpers import make_clock, make_game_state, make_npc


def _game(health: int = 5, spirit: int = 5, supply: int = 5, momentum: int = 3) -> GameState:
    g = make_game_state(player_name="Hero")
    g.resources = Resources(health=health, spirit=spirit, supply=supply, momentum=momentum, max_momentum=10)
    return g


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


def test_tick_threat_clock() -> None:
    from straightjacket.engine.mechanics.consequences import tick_threat_clock

    game = _game()
    game.world.clocks = [make_clock(name="Storm", clock_type="threat", segments=4, filled=2)]
    events: list[ClockEvent] = []
    tick_threat_clock(game, 1, events)
    assert game.world.clocks[0].filled == 3
    assert len(events) == 0


def test_tick_threat_clock_fires_when_full() -> None:
    from straightjacket.engine.mechanics.consequences import tick_threat_clock

    game = _game()
    game.world.clocks = [make_clock(name="Storm", clock_type="threat", segments=4, filled=3)]
    events: list[ClockEvent] = []
    tick_threat_clock(game, 1, events)
    assert game.world.clocks[0].filled == 4
    assert game.world.clocks[0].fired is True
    assert len(events) == 1
    assert events[0].clock == "Storm"


def test_tick_threat_clock_skips_non_threat() -> None:
    from straightjacket.engine.mechanics.consequences import tick_threat_clock

    game = _game()
    game.world.clocks = [make_clock(name="Progress", clock_type="progress", segments=4, filled=2)]
    events: list[ClockEvent] = []
    tick_threat_clock(game, 1, events)
    assert game.world.clocks[0].filled == 2


def test_tick_threat_clock_skips_full() -> None:
    from straightjacket.engine.mechanics.consequences import tick_threat_clock

    game = _game()
    game.world.clocks = [make_clock(name="Done", clock_type="threat", segments=4, filled=4, fired=True)]
    events: list[ClockEvent] = []
    tick_threat_clock(game, 1, events)
    assert len(events) == 0


@pytest.mark.parametrize(
    "momentum, d_value, action_score, roll_result, expected_burn",
    [
        (8, 1, 4, "MISS", "STRONG_HIT"),
        (6, 1, 4, "MISS", "WEAK_HIT"),
        (8, 3, 8, "WEAK_HIT", "STRONG_HIT"),
        (2, 1, 4, "MISS", None),
        (0, 1, 4, "MISS", None),
    ],
)
def test_can_burn_momentum(
    momentum: int, d_value: int, action_score: int, roll_result: str, expected_burn: str | None
) -> None:
    from straightjacket.engine.mechanics.consequences import can_burn_momentum

    game = _game(momentum=momentum)
    roll = RollResult(
        d1=d_value,
        d2=d_value,
        c1=5,
        c2=7,
        stat_name="wits",
        stat_value=2,
        action_score=action_score,
        result=roll_result,
        move="x",
        match=False,
    )
    assert can_burn_momentum(game, roll) == expected_burn


def test_npc_agency_fires_on_scene_5(load_engine: None) -> None:
    from straightjacket.engine.mechanics.consequences import check_npc_agency

    game = _game()
    game.narrative.scene_count = 5
    npc = make_npc(id="npc_1", name="Kira", status="active", agenda="find the vault")
    game.npcs.append(npc)
    actions, _ = check_npc_agency(game)
    assert len(actions) == 1
    assert "Kira" in actions[0]


def test_npc_agency_skips_non_multiple_of_5(load_engine: None) -> None:
    from straightjacket.engine.mechanics.consequences import check_npc_agency

    game = _game()
    game.narrative.scene_count = 3
    npc = make_npc(id="npc_1", name="Kira", status="active", agenda="find the vault")
    game.npcs.append(npc)
    actions, _ = check_npc_agency(game)
    assert len(actions) == 0


def test_npc_agency_ticks_owned_clock(load_engine: None) -> None:
    from straightjacket.engine.mechanics.consequences import check_npc_agency

    game = _game()
    game.narrative.scene_count = 5
    npc = make_npc(id="npc_1", name="Kira", status="active", agenda="find the vault")
    game.npcs.append(npc)
    game.world.clocks = [make_clock(name="Kira's scheme", clock_type="scheme", segments=4, filled=1, owner="Kira")]
    actions, events = check_npc_agency(game)
    assert game.world.clocks[0].filled == 2
    assert len(events) == 1


def test_autonomous_clock_tick(load_engine: None) -> None:
    from straightjacket.engine.mechanics.consequences import tick_autonomous_clocks

    game = _game()
    game.world.clocks = [make_clock(name="Plague", clock_type="threat", segments=6, filled=2, owner="world")]
    ticked = False
    for _ in range(100):
        game.world.clocks[0].filled = 2
        events = tick_autonomous_clocks(game)
        if events:
            ticked = True
            break
    assert ticked


def test_purge_old_fired_clocks(load_engine: None) -> None:
    from straightjacket.engine.mechanics.consequences import purge_old_fired_clocks

    game = _game()
    game.narrative.scene_count = 10
    game.world.clocks = [
        make_clock(name="Old", clock_type="threat", segments=4, filled=4, fired=True, fired_at_scene=3),
        make_clock(name="Recent", clock_type="threat", segments=4, filled=4, fired=True, fired_at_scene=9),
        make_clock(name="Active", clock_type="threat", segments=4, filled=2),
    ]
    purge_old_fired_clocks(game)
    names = [c.name for c in game.world.clocks]
    assert "Old" not in names
    assert "Recent" in names
    assert "Active" in names


def test_roll_progress_returns_valid_result() -> None:
    from straightjacket.engine.mechanics.consequences import roll_progress

    r = roll_progress("Test Vow", 6, "quest/fulfill_your_vow")
    assert r.result in ("STRONG_HIT", "WEAK_HIT", "MISS")
    assert r.move == "quest/fulfill_your_vow"
    assert r.stat_name == "Test Vow"
    assert r.stat_value == 6
    assert r.action_score == 6
    assert r.d1 == 0
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
