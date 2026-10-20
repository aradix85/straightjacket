from typing import Any

from tests._helpers import make_clock, make_game_state, make_npc


def _npc(name: str, description: str, disposition: str) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "agenda": "",
        "instinct": "",
        "secrets": [],
        "disposition": disposition,
    }


def _setup(*npcs: dict[str, Any]) -> dict[str, Any]:
    return {"npcs": list(npcs), "memory_updates": [], "location": "Dock", "scene_context": ""}


def test_an_opening_registers_neither_the_player_nor_a_known_npc_again(load_engine: None) -> None:
    from straightjacket.engine.game.setup_common import apply_opening_setup

    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="npc_1", name="Kira", status="deceased")]
    apply_opening_setup(
        game,
        _setup(_npc("Kira", "Scout", "friendly"), _npc("Hero", "Player", "neutral"), _npc("Borin", "Smith", "neutral")),
        label="OpeningSetup",
    )
    assert [(n.id, n.name) for n in game.npcs] == [("npc_1", "Kira"), ("npc_2", "Borin")]


def test_an_opening_does_not_split_a_known_npc_by_a_shorter_name(load_engine: None) -> None:
    from straightjacket.engine.game.setup_common import apply_opening_setup

    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="npc_1", name="Maren Silk", description="A smuggler.")]
    apply_opening_setup(game, _setup(_npc("Maren", "A smuggler", "neutral")), label="OpeningSetup")
    assert [n.name for n in game.npcs] == ["Maren Silk"]


def test_seed_opening_memories_matches_and_skips(load_engine: None) -> None:
    from straightjacket.engine.game.setup_common import seed_opening_memories

    game = make_game_state(player_name="Hero")
    game.narrative.scene_count = 1
    game.npcs = [make_npc(id="npc_1", name="Captain Ashwood")]
    seed_opening_memories(
        game,
        [
            {"npc_name": "Ashwood", "event": "Nodded at player", "emotional_weight": "neutral"},
            {"npc_name": "Nobody", "event": "Should be skipped", "emotional_weight": "neutral"},
        ],
    )
    assert len(game.npcs[0].memory) == 1


def test_opening_setup_sets_location_and_context_and_keeps_the_engines_clock_and_time(load_engine: None) -> None:
    from straightjacket.engine.game.setup_common import apply_opening_setup

    game = make_game_state(player_name="Hero")
    game.world.clocks = [make_clock(name="Engine clock")]
    game.world.time_of_day = "morning"
    apply_opening_setup(
        game, {"npcs": [], "memory_updates": [], "location": "Market", "scene_context": "Busy."}, label="OpeningSetup"
    )
    assert game.world.current_location == "Market"
    assert game.world.current_scene_context == "Busy."
    assert [c.name for c in game.world.clocks] == ["Engine clock"]
    assert game.world.time_of_day == "morning"


def test_opening_setup_schema_leaves_clocks_and_time_to_the_engine(load_engine: None) -> None:
    from straightjacket.engine.ai.schemas import get_opening_setup_schema

    properties = get_opening_setup_schema()["properties"]
    assert "clocks" not in properties
    assert "time_of_day" not in properties
