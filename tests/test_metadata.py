from typing import Any

from straightjacket.engine.models import GameState
from tests._helpers import make_game_state, make_memory, make_npc


def _game() -> GameState:
    game = make_game_state(player_name="Hero")
    game.narrative.scene_count = 5
    game.world.current_location = "Tavern"
    game.world.time_of_day = "evening"
    game.npcs = [
        make_npc(
            id="npc_1",
            name="Kira",
            disposition="friendly",
            status="active",
            last_location="Tavern",
            memory=[make_memory(scene=4, event="Talked to player", importance=3)],
        ),
        make_npc(id="npc_2", name="Borin", disposition="neutral", status="active", last_location="Tavern"),
    ]
    return game


def _apply(game: GameState, present: set[str], **reported: list[dict[str, Any]]) -> None:
    from straightjacket.engine.ai.metadata import apply_narrator_metadata

    metadata: dict[str, Any] = {
        "new_npcs": [],
        "npc_renames": [],
        "npc_details": [],
        "deceased_npcs": [],
        "lore_npcs": [],
        **reported,
    }
    apply_narrator_metadata(game, metadata, scene_present_ids=present, world_addition="")


def test_a_reported_death_marks_an_npc_present_in_the_scene(load_engine: None) -> None:
    game = _game()
    _apply(game, {"npc_1"}, deceased_npcs=[{"npc_id": "npc_1"}])
    assert game.npcs[0].status == "deceased"


def test_a_reported_death_of_an_npc_not_in_the_scene_is_refused(load_engine: None) -> None:
    game = _game()
    _apply(game, {"npc_2"}, deceased_npcs=[{"npc_id": "npc_1"}])
    assert game.npcs[0].status == "active"


def test_a_reported_death_of_an_npc_with_a_memory_of_this_scene_is_taken(load_engine: None) -> None:
    game = _game()
    game.npcs[0].memory.append(make_memory(scene=5, event="Just arrived", importance=5))
    _apply(game, {"npc_2"}, deceased_npcs=[{"npc_id": "npc_1"}])
    assert game.npcs[0].status == "deceased"


def test_a_reported_death_of_an_unknown_npc_changes_nothing(load_engine: None) -> None:
    game = _game()
    _apply(game, {"npc_1", "npc_2"}, deceased_npcs=[{"npc_id": "nobody"}])
    assert [n.status for n in game.npcs] == ["active", "active"]


def test_an_openings_reported_death_needs_no_presence(load_engine: None) -> None:
    from straightjacket.engine.ai.metadata import process_deceased_npcs

    game = _game()
    process_deceased_npcs(game, [{"npc_id": "npc_1"}, {"npc_id": "nobody"}])
    assert [n.status for n in game.npcs] == ["deceased", "active"]


def test_a_figure_only_spoken_of_becomes_a_lore_npc(load_engine: None) -> None:
    game = _game()
    _apply(game, {"npc_1", "npc_2"}, lore_npcs=[{"name": "Ancient King", "description": "Legendary ruler"}])
    [lore] = [n for n in game.npcs if n.status == "lore"]
    assert (lore.name, lore.description) == ("Ancient King", "Legendary ruler")


def test_a_lore_figure_that_is_known_or_nameless_adds_no_npc(load_engine: None) -> None:
    game = _game()
    _apply(
        game,
        {"npc_1", "npc_2"},
        lore_npcs=[{"name": "Kira", "description": "Already exists"}, {"name": " ", "description": "No name"}],
    )
    assert [n.name for n in game.npcs] == ["Kira", "Borin"]


def test_a_rename_when_no_npc_is_known_fails_the_extraction_only(load_engine: None) -> None:
    import json

    from straightjacket.engine.ai.narrator import call_narrator_metadata
    from tests._helpers import make_brain_result
    from tests._mocks import MockProvider

    game = make_game_state(player_name="Hero")
    reply = {
        "new_npcs": [{"name": "Orla", "description": "a ferrywoman", "disposition": "neutral"}],
        "npc_renames": [None],
        "npc_details": [],
        "deceased_npcs": [],
        "lore_npcs": [],
    }
    metadata = call_narrator_metadata(MockProvider(json.dumps(reply)), "Orla waits.", game, make_brain_result(), [])
    assert metadata["npc_renames"] == metadata["new_npcs"] == []
