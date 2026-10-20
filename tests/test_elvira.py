import pytest

from straightjacket.engine.models import (
    GameState,
)
from tests._helpers import make_clock, make_game_state, make_memory, make_npc, make_progress_track


@pytest.fixture
def game(load_engine: None) -> GameState:
    g = make_game_state(
        player_name="Elvira",
        setting_id="starforged",
        setting_genre="starforged",
    )
    g.resources.meters["health"] = 4
    g.resources.meters["spirit"] = 3
    g.resources.meters["supply"] = 5
    g.resources.meters["momentum"] = 3
    g.world.current_location = "The Docks"
    g.world.time_of_day = "evening"
    g.world.chaos_factor = 6
    g.world.combat_position = ""
    g.narrative.scene_count = 5
    g.npcs = [
        make_npc(
            id="npc_1",
            name="Kira",
            status="active",
            disposition="friendly",
            agenda="Trade",
            instinct="Cautious",
            memory=[make_memory(scene=1, event="Met at docks", emotional_weight="neutral", importance=3)],
        ),
        make_npc(id="npc_2", name="Ghost", status="deceased", disposition="neutral"),
    ]
    g.world.clocks = [make_clock(name="Doom", clock_type="threat", segments=6, filled=3)]
    g.progress_tracks = [
        make_progress_track(id="vow_find_truth", name="Find the Truth", track_type="vow", rank="dangerous", ticks=16),
        make_progress_track(id="connection_npc_1", name="Kira", track_type="connection", rank="dangerous", ticks=8),
    ]
    return g


def test_the_final_state_holds_the_character_the_bond_of_each_npc_and_the_clocks(game: GameState) -> None:
    from tests.elvira.elvira_bot.display import final_state_dict

    result = final_state_dict(game)
    assert (result["character"], result["meters"]["health"], result["scene"]) == ("Elvira", 4, 5)
    kira = next(n for n in result["npcs"] if n["name"] == "Kira")
    assert kira["bond"] == 2
    assert [c["name"] for c in result["active_clocks"]] == ["Doom"]


def test_a_turn_record_keeps_the_state_and_the_npcs_in_play(game: GameState) -> None:
    from tests.elvira.elvira_bot.recorder import record_turn

    game.world.combat_position = "in_control"
    record = record_turn(game, 1, "I look around.", "The docks are quiet.", None)
    state = record.state_after
    assert (state.meters["health"], state.chaos, state.scene) == (4, 6, 5)
    assert (state.active_progress_tracks, state.combat_position) == (2, "in_control")
    [kira] = record.npcs
    assert (kira.name, kira.disposition, kira.memory_count, kira.agenda) == ("Kira", "friendly", 1, "Trade")


class TestInvariants:
    def test_clean_game_no_violations(self, game: GameState) -> None:
        from tests.elvira.elvira_bot.invariants import assert_game_state

        violations = assert_game_state(game, turn=1)
        assert violations == []

    def test_catches_bad_health(self, game: GameState) -> None:
        from tests.elvira.elvira_bot.invariants import assert_game_state

        game.resources.meters["health"] = -1
        violations = assert_game_state(game, turn=1)
        assert any("health" in v for v in violations)

    def test_catches_bad_disposition(self, game: GameState) -> None:
        from tests.elvira.elvira_bot.invariants import assert_game_state

        game.npcs[0].disposition = "invalid"
        violations = assert_game_state(game, turn=1)
        assert any("disposition" in v for v in violations)
