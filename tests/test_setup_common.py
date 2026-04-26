from tests._helpers import make_clock, make_game_state, make_npc


def test_register_extracted_npcs_skips_player(stub_all: None) -> None:
    from straightjacket.engine.game.setup_common import register_extracted_npcs

    game = make_game_state(player_name="Hero")
    game.world.current_location = "Tavern"
    max_id = register_extracted_npcs(
        game,
        [
            {"name": "Mira", "description": "Scout", "disposition": "friendly"},
            {"name": "Hero", "description": "Player", "disposition": "neutral"},
        ],
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
            {"name": "Kira", "description": "Scout", "disposition": "friendly"},
            {"name": "Borin", "description": "Smith", "disposition": "neutral"},
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


def test_apply_world_setup_replace_vs_extend(stub_all: None) -> None:
    from straightjacket.engine.game.setup_common import apply_world_setup

    game = make_game_state(player_name="Hero")
    game.world.clocks = [make_clock(name="Old")]
    apply_world_setup(
        game,
        {
            "clocks": [
                {
                    "name": "New",
                    "clock_type": "threat",
                    "segments": 4,
                    "filled": 1,
                    "trigger_description": "Storm breaks",
                }
            ],
            "location": "Market",
            "scene_context": "Busy.",
            "time_of_day": "midday",
        },
        clocks_mode="replace",
    )
    assert len(game.world.clocks) == 1
    assert game.world.clocks[0].name == "New"

    game.world.clocks = [make_clock(name="Old")]
    apply_world_setup(
        game,
        {
            "clocks": [
                {
                    "name": "New2",
                    "clock_type": "threat",
                    "segments": 4,
                    "filled": 0,
                    "trigger_description": "Door opens",
                }
            ],
        },
        clocks_mode="extend",
    )
    assert len(game.world.clocks) == 2
