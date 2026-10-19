from unittest.mock import patch

import pytest

from tests._helpers import make_game_state


def test_roll_oracle_name_needs_the_setting(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.npc.naming import roll_oracle_name

    game = make_game_state()
    game.setting_id = ""
    with pytest.raises(FileNotFoundError, match="Setting package not found"):
        roll_oracle_name(game)


def test_roll_oracle_name_classic_single_path(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.npc.naming import roll_oracle_name
    from straightjacket.engine.setting.packages import clear_cache

    clear_cache()
    game = make_game_state(setting_id="classic")
    name = roll_oracle_name(game)
    assert name
    assert len(name) >= 2


def test_roll_oracle_name_starforged_multi_path(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.npc.naming import roll_oracle_name
    from straightjacket.engine.setting.packages import clear_cache

    clear_cache()
    game = make_game_state(setting_id="starforged")
    name = roll_oracle_name(game)
    assert name

    word_count = len(name.split())
    assert word_count in (1, 2)


def test_roll_oracle_name_delve_inherits_from_classic(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.npc.naming import roll_oracle_name
    from straightjacket.engine.setting.packages import clear_cache

    clear_cache()
    game = make_game_state(setting_id="delve")
    name = roll_oracle_name(game)
    assert name


def test_process_new_npcs_uses_oracle_name(stub_all: None, load_engine: None) -> None:
    from straightjacket.engine.gamemaster.npc.processing import process_new_npcs
    from straightjacket.engine.setting.packages import clear_cache

    clear_cache()
    game = make_game_state(player_name="Hero", setting_id="classic")
    with patch("straightjacket.engine.gamemaster.npc.processing.roll_oracle_name", return_value="Sigrid Ironhand"):
        process_new_npcs(game, [{"name": "AI Generated Name", "description": "a warrior", "disposition": "neutral"}])
    assert len(game.npcs) == 1
    assert game.npcs[0].name == "Sigrid Ironhand"

    assert "AI Generated Name" in game.npcs[0].aliases
