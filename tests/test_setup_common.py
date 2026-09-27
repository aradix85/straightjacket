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


def test_register_extracted_npcs_skips_player(stub_all: None) -> None:
    from straightjacket.engine.game.setup_common import register_extracted_npcs

    game = make_game_state(player_name="Hero")
    game.world.current_location = "Tavern"
    max_id = register_extracted_npcs(
        game,
        [
            _npc("Mira", "Scout", "friendly"),
            _npc("Hero", "Player", "neutral"),
        ],
        skip_names=set(),
    )
    assert len(game.npcs) == 1
    assert game.npcs[0].name == "Mira"
    assert max_id == 1


def test_register_extracted_npcs_skips_returning(stub_all: None) -> None:
    from straightjacket.engine.game.setup_common import register_extracted_npcs

    game = make_game_state(player_name="Hero")
    register_extracted_npcs(
        game,
        [
            _npc("Kira", "Scout", "friendly"),
            _npc("Borin", "Smith", "neutral"),
        ],
        skip_names={"kira"},
    )
    names = {n.name for n in game.npcs}
    assert "Kira" not in names
    assert "Borin" in names


def test_seed_opening_memories_matches_and_skips(stub_all: None) -> None:
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


def test_opening_setup_sets_location_and_context_and_keeps_the_engines_clock_and_time(stub_all: None) -> None:
    from straightjacket.engine.game.setup_common import apply_opening_setup

    game = make_game_state(player_name="Hero")
    game.world.clocks = [make_clock(name="Engine clock")]
    game.world.time_of_day = "morning"
    apply_opening_setup(game, {"npcs": [], "memory_updates": [], "location": "Market", "scene_context": "Busy."})
    assert game.world.current_location == "Market"
    assert game.world.current_scene_context == "Busy."
    assert [c.name for c in game.world.clocks] == ["Engine clock"]
    assert game.world.time_of_day == "morning"


def test_opening_setup_schema_leaves_clocks_and_time_to_the_engine(stub_all: None) -> None:
    from straightjacket.engine.ai.schemas import get_opening_setup_schema

    properties = get_opening_setup_schema()["properties"]
    assert "clocks" not in properties
    assert "time_of_day" not in properties
