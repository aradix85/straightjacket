import json
from typing import Any

import pytest

from straightjacket.engine.models import GameState
from straightjacket.engine.ruleset.meters import starting_resources
from tests._helpers import make_blueprint, make_clock, make_game_state, make_memory, make_npc


def _game() -> GameState:
    game = make_game_state(player_name="TestHero", stats={"edge": 2, "heart": 2, "iron": 1, "shadow": 1, "wits": 1})
    game.resources.meters["health"] = 4
    game.resources.meters["momentum"] = 3
    game.world.current_location = "TestTavern"
    game.narrative.scene_count = 3
    game.npcs = [
        make_npc(
            id="npc_1",
            name="Ally",
            disposition="friendly",
            memory=[make_memory(scene=1, event="Met player", importance=3)],
        ),
    ]
    game.world.clocks = [make_clock(name="Doom", segments=6, filled=2)]
    return game


@pytest.fixture
def save_dir(tmp_path: Any, monkeypatch: pytest.MonkeyPatch, load_engine: None) -> Any:
    for target in (
        "straightjacket.engine.config_loader.USERS_DIR",
        "straightjacket.engine.user_management.USERS_DIR",
    ):
        monkeypatch.setattr(target, tmp_path)
    return tmp_path


def test_a_load_returns_exactly_what_was_saved(save_dir: Any) -> None:
    from straightjacket.engine.persistence import load_game, save_game

    game = _game()
    game.npcs[0].arc = "Beginning to trust the player"
    game.npcs[0].aliases = [game.npcs[0].name]
    game.world.combat_position = "bad_spot"
    game.narrative.story_blueprint = make_blueprint(triggered_director_phases=["climax"])
    msgs = [{"role": "assistant", "content": "Hello world."}]
    save_game(game, "tester", msgs, "test_save")

    loaded, loaded_msgs = load_game("tester", "test_save")
    assert loaded is not None
    assert loaded.to_dict() == game.to_dict()
    assert loaded_msgs == msgs


def test_load_nonexistent_returns_none(save_dir: Any) -> None:
    from straightjacket.engine.persistence import load_game

    game, msgs = load_game("tester", "nonexistent")
    assert game is None
    assert msgs == []


def test_list_saves_empty(save_dir: Any) -> None:
    from straightjacket.engine.persistence import list_saves_with_info

    result = list_saves_with_info("empty_user")
    assert result == []


def test_list_saves_with_saves(save_dir: Any) -> None:
    from straightjacket.engine.persistence import list_saves_with_info, save_game

    save_game(_game(), "lister", [], "save_a")
    save_game(_game(), "lister", [], "save_b")
    result = list_saves_with_info("lister")
    assert len(result) == 2
    names = {s["name"] for s in result}
    assert "save_a" in names
    assert "save_b" in names


def test_delete_save(save_dir: Any) -> None:
    from straightjacket.engine.persistence import delete_save, list_saves_with_info, save_game

    save_game(_game(), "deleter", [], "to_delete")
    delete_save("deleter", "to_delete")
    assert list_saves_with_info("deleter") == []


def test_deleting_a_save_that_does_not_exist_changes_nothing(save_dir: Any) -> None:
    from straightjacket.engine.persistence import delete_save, get_save_dir

    delete_save("nobody", "nope")
    assert not (get_save_dir("nobody") / "nope.json").exists()


def test_a_save_holds_the_time_the_state_and_the_chat(save_dir: Any) -> None:
    from straightjacket.engine.persistence import get_save_dir, save_game

    msgs = [{"role": "assistant", "content": "Narration.", "epilogue": True}]
    save_game(_game(), "tester", msgs, "keys")
    data = json.loads((get_save_dir("tester") / "keys.json").read_text(encoding="utf-8"))
    assert set(data) == {"saved_at", "game_state", "chat_messages"}
    assert data["chat_messages"] == msgs


def test_list_saves_skips_corrupt_files(save_dir: Any) -> None:
    from straightjacket.engine.persistence import get_save_dir, list_saves_with_info, save_game

    save_game(_game(), "mixed", [], "good_save")
    save_root = get_save_dir("mixed")

    (save_root / "broken_json.json").write_text("{not valid json", encoding="utf-8")

    (save_root / "missing_fields.json").write_text(json.dumps({"saved_at": "2026-01-01"}), encoding="utf-8")

    result = list_saves_with_info("mixed")
    names = {s["name"] for s in result}
    assert names == {"good_save"}


def test_a_save_missing_a_field_does_not_load(load_engine: None) -> None:
    from straightjacket.engine.models import Resources

    data = starting_resources("starforged").to_dict()
    data.pop("next_move_bonus")
    with pytest.raises(ValueError, match=r"Resources: missing fields \['next_move_bonus'\]"):
        Resources.from_dict(data)


def test_a_save_with_an_unknown_field_does_not_load(load_engine: None) -> None:
    data = _game().to_dict()
    data["retired_field"] = 0
    with pytest.raises(ValueError, match=r"GameState: unknown fields \['retired_field'\]"):
        GameState.from_dict(data)


def test_a_save_with_null_in_a_required_field_does_not_load(load_engine: None) -> None:
    data = _game().to_dict()
    data["world"]["current_location"] = None
    with pytest.raises(ValueError, match="null where"):
        GameState.from_dict(data)


def test_a_save_with_a_value_where_an_object_belongs_does_not_load(load_engine: None) -> None:
    data = _game().to_dict()
    data["world"]["clocks"] = ["Doom"]
    with pytest.raises(ValueError, match="not an object"):
        GameState.from_dict(data)
    data = _game().to_dict()
    data["resources"] = 5
    with pytest.raises(ValueError, match="Resources needs an object"):
        GameState.from_dict(data)


def test_a_snapshot_that_disagrees_on_the_blueprint_does_not_restore(load_engine: None) -> None:
    from tests._helpers import make_blueprint

    game = _game()
    game.narrative.story_blueprint = make_blueprint()
    snap = game.snapshot()
    game.narrative.story_blueprint = None
    with pytest.raises(ValueError, match="story blueprint"):
        game.restore(snap)


def test_a_snapshot_with_an_unknown_resource_does_not_restore(load_engine: None) -> None:
    game = _game()
    snap = game.snapshot()
    snap.resources["retired_meter"] = 3
    with pytest.raises(ValueError, match=r"Resources: unknown fields \['retired_meter'\]"):
        game.restore(snap)
