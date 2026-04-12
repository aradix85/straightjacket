#!/usr/bin/env python3
"""Tests for Elvira bot modules: snapshots, invariants, display.

Catches attribute errors and structural issues when engine dataclasses change.
"""

import pytest

from straightjacket.engine.models import (
    ClockData,
    GameState,
    MemoryEntry,
    NpcData,
    ProgressTrack,
)


@pytest.fixture()
def game(load_engine: None) -> GameState:
    """Minimal game state with NPCs, clocks, tracks — exercises all snapshot fields."""
    g = GameState(
        player_name="Elvira",
        setting_id="starforged",
        setting_genre="starforged",
    )
    g.resources.health = 4
    g.resources.spirit = 3
    g.resources.supply = 5
    g.resources.momentum = 3
    g.world.current_location = "The Docks"
    g.world.time_of_day = "evening"
    g.world.chaos_factor = 6
    g.world.combat_position = ""
    g.narrative.scene_count = 5
    g.npcs = [
        NpcData(
            id="npc_1",
            name="Kira",
            status="active",
            disposition="friendly",
            agenda="Trade",
            instinct="Cautious",
            memory=[MemoryEntry(scene=1, event="Met at docks", emotional_weight="neutral", importance=3)],
        ),
        NpcData(id="npc_2", name="Ghost", status="deceased", disposition="neutral"),
    ]
    g.world.clocks = [ClockData(name="Doom", clock_type="threat", segments=6, filled=3)]
    g.progress_tracks = [
        ProgressTrack(id="vow_find_truth", name="Find the Truth", track_type="vow", rank="dangerous", ticks=16),
        ProgressTrack(id="connection_npc_1", name="Kira", track_type="connection", rank="dangerous", ticks=8),
    ]
    return g


class TestFinalStateDict:
    def test_returns_dict(self, game: GameState) -> None:
        from tests.elvira.elvira_bot.display import final_state_dict

        result = final_state_dict(game)
        assert isinstance(result, dict)
        assert result["character"] == "Elvira"
        assert result["health"] == 4
        assert result["scene"] == 5

    def test_npcs_have_bond(self, game: GameState) -> None:
        from tests.elvira.elvira_bot.display import final_state_dict

        result = final_state_dict(game)
        npcs = result["npcs"]
        kira = next(n for n in npcs if n["name"] == "Kira")
        assert "bond" in kira
        assert kira["bond"] == 2  # ticks=8, filled_boxes=2

    def test_clocks_present(self, game: GameState) -> None:
        from tests.elvira.elvira_bot.display import final_state_dict

        result = final_state_dict(game)
        assert len(result["active_clocks"]) == 1
        assert result["active_clocks"][0]["name"] == "Doom"


class TestSnapshotState:
    def test_returns_snapshot(self, game: GameState) -> None:
        from tests.elvira.elvira_bot.recorder import _snapshot_state

        snap = _snapshot_state(game)
        assert snap.health == 4
        assert snap.chaos == 6
        assert snap.scene == 5
        assert snap.active_progress_tracks == 2

    def test_combat_position(self, game: GameState) -> None:
        from tests.elvira.elvira_bot.recorder import _snapshot_state

        game.world.combat_position = "in_control"
        snap = _snapshot_state(game)
        assert snap.combat_position == "in_control"


class TestSnapshotNpcs:
    def test_filters_active_and_background(self, game: GameState) -> None:
        from tests.elvira.elvira_bot.recorder import _snapshot_npcs

        snaps = _snapshot_npcs(game)
        names = [s.name for s in snaps]
        assert "Kira" in names
        assert "Ghost" not in names  # deceased filtered out

    def test_npc_fields(self, game: GameState) -> None:
        from tests.elvira.elvira_bot.recorder import _snapshot_npcs

        snaps = _snapshot_npcs(game)
        kira = next(s for s in snaps if s.name == "Kira")
        assert kira.disposition == "friendly"
        assert kira.memory_count == 1
        assert kira.agenda == "Trade"


class TestInvariants:
    def test_clean_game_no_violations(self, game: GameState) -> None:
        from tests.elvira.elvira_bot.invariants import assert_game_state

        violations = assert_game_state(game, turn=1)
        assert violations == []

    def test_catches_bad_health(self, game: GameState) -> None:
        from tests.elvira.elvira_bot.invariants import assert_game_state

        game.resources.health = -1
        violations = assert_game_state(game, turn=1)
        assert any("health" in v for v in violations)

    def test_catches_bad_disposition(self, game: GameState) -> None:
        from tests.elvira.elvira_bot.invariants import assert_game_state

        game.npcs[0].disposition = "invalid"
        violations = assert_game_state(game, turn=1)
        assert any("disposition" in v for v in violations)
