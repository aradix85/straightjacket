"""Tests for step 11c: NPC name oracle rolling."""

from unittest.mock import patch

from straightjacket.engine.models import GameState


def test_roll_oracle_name_no_setting() -> None:
    from straightjacket.engine.npc.naming import roll_oracle_name

    game = GameState()  # No setting_id
    assert roll_oracle_name(game) == ""


def test_roll_oracle_name_classic_single_path(load_engine: None) -> None:
    from straightjacket.engine.datasworn.settings import clear_cache
    from straightjacket.engine.npc.naming import roll_oracle_name

    clear_cache()
    game = GameState(setting_id="classic")
    name = roll_oracle_name(game)
    assert name  # Non-empty
    assert len(name) >= 2


def test_roll_oracle_name_starforged_multi_path(load_engine: None) -> None:
    from straightjacket.engine.datasworn.settings import clear_cache
    from straightjacket.engine.npc.naming import roll_oracle_name

    clear_cache()
    game = GameState(setting_id="starforged")
    name = roll_oracle_name(game)
    assert name
    # Either callsign (1 word) or given + family (2 words)
    word_count = len(name.split())
    assert word_count in (1, 2)


def test_roll_oracle_name_delve_inherits_from_classic(load_engine: None) -> None:
    from straightjacket.engine.datasworn.settings import clear_cache
    from straightjacket.engine.npc.naming import roll_oracle_name

    clear_cache()
    game = GameState(setting_id="delve")
    name = roll_oracle_name(game)
    assert name  # Delve's own paths are empty; should fall back to Classic's


def test_process_new_npcs_uses_oracle_name(stub_all: None, load_engine: None) -> None:
    from straightjacket.engine.datasworn.settings import clear_cache
    from straightjacket.engine.npc.processing import process_new_npcs

    clear_cache()
    game = GameState(player_name="Hero", setting_id="classic")
    with patch("straightjacket.engine.npc.naming.roll_oracle_name", return_value="Sigrid Ironhand"):
        process_new_npcs(game, [{"name": "AI Generated Name", "description": "a warrior", "disposition": "neutral"}])
    assert len(game.npcs) == 1
    assert game.npcs[0].name == "Sigrid Ironhand"
    # AI name preserved as alias
    assert "AI Generated Name" in game.npcs[0].aliases


def test_process_new_npcs_fallback_to_ai_name(stub_all: None, load_engine: None) -> None:
    from straightjacket.engine.npc.processing import process_new_npcs

    game = GameState(player_name="Hero")  # No setting_id → no oracle
    process_new_npcs(game, [{"name": "AI Name", "description": "d", "disposition": "neutral"}])
    assert len(game.npcs) == 1
    assert game.npcs[0].name == "AI Name"
