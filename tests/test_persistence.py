import copy
import json
from typing import Any

import pytest

from straightjacket.engine.models import GameState, Resources, consequence
from straightjacket.engine.persistence import (
    ChatMessage,
    IncompatibleSaveError,
    SavedGame,
    delete_save,
    list_saves_with_info,
    load_game,
    save_game,
)
from straightjacket.engine.ruleset.meters import starting_resources
from straightjacket.engine.user_management import get_save_dir
from tests._helpers import (
    make_blueprint,
    make_clock,
    make_game_state,
    make_memory,
    make_npc,
    make_predecessor,
    make_progress_track,
    make_scene_log_entry,
    make_threat,
    use_users_dir,
)


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


def _save(game: GameState) -> dict[str, object]:
    return SavedGame(saved_at="2026-01-01", game_state=game, chat_messages=[]).to_dict()


def _with(data: dict[str, object], path: tuple[str | int, ...], value: object) -> object:
    changed = json.loads(json.dumps(data))
    part = changed
    for step in path[:-1]:
        part = part[step]
    part[path[-1]] = value
    return changed


def _write(name: str, content: object) -> None:
    path = get_save_dir("tester") / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content), encoding="utf-8")


@pytest.fixture
def save_dir(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    use_users_dir(monkeypatch, tmp_path)
    return tmp_path


@pytest.mark.usefixtures("save_dir")
def test_a_load_returns_exactly_what_was_saved() -> None:
    game = _game()
    game.npcs[0].arc = "Beginning to trust the player"
    game.npcs[0].aliases = [game.npcs[0].name]
    game.world.combat_position = "bad_spot"
    game.narrative.story_blueprint = make_blueprint(triggered_director_phases=["climax"])
    msgs = [ChatMessage(role="assistant", content="Hello world.", epilogue=False)]
    save_game(game, "tester", msgs, "test_save")

    loaded, loaded_msgs = load_game("tester", "test_save")
    assert loaded is not None
    assert loaded.to_dict() == game.to_dict()
    assert loaded_msgs == msgs


@pytest.mark.usefixtures("save_dir")
def test_load_nonexistent_returns_none() -> None:
    game, msgs = load_game("tester", "nonexistent")
    assert game is None
    assert not msgs


@pytest.mark.usefixtures("save_dir")
def test_list_saves_empty() -> None:
    result = list_saves_with_info("empty_user")
    assert not result


@pytest.mark.usefixtures("save_dir")
def test_list_saves_with_saves() -> None:
    save_game(_game(), "lister", [], "save_a")
    save_game(_game(), "lister", [], "save_b")
    result = list_saves_with_info("lister")
    assert len(result) == 2
    names = {s.name for s in result}
    assert "save_a" in names
    assert "save_b" in names


@pytest.mark.usefixtures("save_dir")
def test_delete_save() -> None:
    save_game(_game(), "deleter", [], "to_delete")
    delete_save("deleter", "to_delete")
    assert not list_saves_with_info("deleter")


@pytest.mark.usefixtures("save_dir")
def test_deleting_a_save_that_does_not_exist_changes_nothing() -> None:
    delete_save("nobody", "nope")
    assert not (get_save_dir("nobody") / "nope.json").exists()


@pytest.mark.usefixtures("save_dir")
def test_a_save_holds_the_time_the_state_and_the_chat() -> None:
    msgs = [ChatMessage(role="assistant", content="Narration.", epilogue=True)]
    save_game(_game(), "tester", msgs, "keys")
    data = json.loads((get_save_dir("tester") / "keys.json").read_text(encoding="utf-8"))
    assert set(data) == {"saved_at", "game_state", "chat_messages"}
    assert data["chat_messages"] == [{"role": "assistant", "content": "Narration.", "epilogue": True}]


@pytest.mark.usefixtures("save_dir")
def test_list_saves_skips_corrupt_files() -> None:
    save_game(_game(), "mixed", [], "good_save")
    save_root = get_save_dir("mixed")

    (save_root / "broken_json.json").write_text("{not valid json", encoding="utf-8")

    (save_root / "missing_fields.json").write_text(json.dumps({"saved_at": "2026-01-01"}), encoding="utf-8")

    (save_root / "not_an_object.json").write_text(json.dumps(["saved_at"]), encoding="utf-8")

    wrong_type = _with(_save(_game()), ("game_state", "narrative", "scene_count"), "three")
    (save_root / "wrong_type.json").write_text(json.dumps(wrong_type), encoding="utf-8")

    result = list_saves_with_info("mixed")
    names = {s.name for s in result}
    assert names == {"good_save"}


def test_a_save_missing_a_field_does_not_load() -> None:
    data = starting_resources("starforged").to_dict()
    data.pop("next_move_bonus")
    with pytest.raises(ValueError, match=r"Resources: missing keys \['next_move_bonus'\]"):
        Resources.from_dict(data)


def test_a_save_with_an_unknown_field_does_not_load() -> None:
    data = _with(_game().to_dict(), ("retired_field",), 0)
    with pytest.raises(ValueError, match=r"GameState: unknown keys \['retired_field'\]"):
        GameState.from_dict(data)


def test_a_save_with_null_in_a_required_field_does_not_load() -> None:
    data = _with(_game().to_dict(), ("world", "current_location"), None)
    with pytest.raises(ValueError, match=r"GameState\.world\.current_location: expected <class 'str'>, got None"):
        GameState.from_dict(data)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("world", "clocks"), ["Doom"], r"GameState\.world\.clocks\[0\]: expected dict, got str"),
        (("resources",), 5, r"GameState\.resources: expected dict, got int"),
        (("world", "clocks"), "Doom", r"GameState\.world\.clocks: expected list, got str"),
        (("truths",), ["cataclysm"], r"GameState\.truths: expected dict, got list"),
    ],
)
def test_a_save_with_a_value_where_an_object_belongs_does_not_load(
    path: tuple[str, ...], value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        GameState.from_dict(_with(_game().to_dict(), path, value))


def test_a_save_that_is_no_object_does_not_load() -> None:
    with pytest.raises(ValueError, match="GameState: expected dict, got list"):
        GameState.from_dict([])


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("narrative", "scene_count"), "3", r"GameState\.narrative\.scene_count: expected <class 'int'>, got '3'"),
        (("narrative", "scene_count"), True, r"GameState\.narrative\.scene_count: expected <class 'int'>, got True"),
        (("crisis_mode",), 0, r"GameState\.crisis_mode: expected <class 'bool'>, got 0"),
        (("player_name",), 7, r"GameState\.player_name: expected <class 'str'>, got 7"),
        (("resources", "meters", "health"), "4", r"GameState\.resources\.meters\.health: expected <class 'int'>"),
        (("npcs", 0, "aliases"), [3], r"GameState\.npcs\[0\]\.aliases\[0\]: expected <class 'str'>, got 3"),
        (("npcs", 0, "memory", 0, "about_npc"), 3, r"GameState\.npcs\[0\]\.memory\[0\]\.about_npc: expected"),
    ],
)
def test_a_save_with_a_value_of_another_type_than_its_field_does_not_load(
    path: tuple[str | int, ...], value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        GameState.from_dict(_with(_game().to_dict(), path, value))


@pytest.mark.usefixtures("save_dir")
def test_a_save_file_with_a_wrong_value_is_reported_as_incompatible() -> None:
    _write("wrong", _with(_save(_game()), ("game_state", "narrative", "scene_count"), "three"))
    with pytest.raises(IncompatibleSaveError, match=r"tester/wrong\.game_state\.narrative\.scene_count: expected"):
        load_game("tester", "wrong")


@pytest.mark.usefixtures("save_dir")
@pytest.mark.parametrize(
    ("content", "message"),
    [
        ({"saved_at": "2026-01-01"}, r"tester/partial: missing keys \['chat_messages', 'game_state'\]"),
        (["saved_at"], "tester/partial: expected dict, got list"),
    ],
)
def test_a_save_file_that_is_no_save_is_reported_as_incompatible(content: object, message: str) -> None:
    _write("partial", content)
    with pytest.raises(IncompatibleSaveError, match=message):
        load_game("tester", "partial")


@pytest.mark.usefixtures("save_dir")
def test_a_chat_message_without_its_epilogue_mark_does_not_load() -> None:
    _write("old", _with(_save(_game()), ("chat_messages",), [{"role": "assistant", "content": "Hello world."}]))
    with pytest.raises(IncompatibleSaveError, match=r"tester/old\.chat_messages\[0\]: missing keys \['epilogue'\]"):
        load_game("tester", "old")


def test_a_snapshot_in_a_save_is_read_as_strictly_as_the_game() -> None:
    game = _game()
    game.last_turn_snapshot = game.snapshot()
    data = _with(game.to_dict(), ("last_turn_snapshot", "resources", "retired_meter"), 3)
    with pytest.raises(ValueError, match=r"GameState\.last_turn_snapshot\.resources: unknown keys \['retired_meter'\]"):
        GameState.from_dict(data)
    data = _with(game.to_dict(), ("last_turn_snapshot", "npcs", 0, "memory", 0, "importance"), "high")
    with pytest.raises(ValueError, match=r"last_turn_snapshot\.npcs\[0\]\.memory\[0\]\.importance: expected"):
        GameState.from_dict(data)


def test_a_snapshot_survives_a_save() -> None:
    game = _game()
    game.narrative.story_blueprint = make_blueprint(triggered_director_phases=["climax"])
    game.last_turn_snapshot = game.snapshot()
    loaded = GameState.from_dict(json.loads(json.dumps(game.to_dict())))
    assert loaded.last_turn_snapshot == game.last_turn_snapshot
    game.resources.meters["health"] = 1
    game.npcs.clear()
    game.restore(loaded.last_turn_snapshot)
    assert (game.resources.meters["health"], [n.name for n in game.npcs]) == (4, ["Ally"])


def test_a_consequence_is_saved_as_its_kind_its_texts_and_its_numbers() -> None:
    saved = consequence("track_loss", track="health", n=1).to_dict()
    assert saved == {"kind": "track_loss", "texts": {"track": "health"}, "numbers": {"n": 1}}


def _game_with_every_part() -> GameState:
    game = _game()
    game.narrative.story_blueprint = make_blueprint()
    game.narrative.session_log = [make_scene_log_entry(consequences=[consequence("track_loss", track="health", n=1)])]
    game.progress_tracks = [make_progress_track()]
    game.threats = [make_threat()]
    game.campaign.predecessors = [make_predecessor()]
    return game


def _change_every_part(game: GameState) -> None:
    game.resources.meters["health"] = 0
    game.world.clocks[0].filled = 6
    game.world.location_history.append("Elsewhere")
    game.npcs[0].memory.clear()
    game.narrative.scene_intensity_history.append("action")
    game.narrative.director_guidance.npc_guidance["npc_1"] = "be wary"
    game.narrative.session_log[0].consequences[0].numbers["n"] = 2
    assert game.narrative.story_blueprint is not None
    game.narrative.story_blueprint.revealed.append("r1")
    game.progress_tracks[0].ticks += 4
    game.threats[0].menace_ticks += 1
    game.impacts.append("wounded")
    game.campaign.predecessors[0].legacy_filled_boxes["quests"] = 9
    game.campaign.legacy["quests"].ticks = 12


def test_a_snapshot_does_not_follow_the_game() -> None:
    game = _game_with_every_part()
    snap = game.snapshot()
    kept = copy.deepcopy(snap)
    _change_every_part(game)
    assert snap == kept
    game.restore(snap)
    assert game.snapshot() == kept


def test_a_restore_leaves_its_snapshot_as_it_was() -> None:
    game = _game_with_every_part()
    snap = game.snapshot()
    kept = copy.deepcopy(snap)
    game.restore(snap)
    _change_every_part(game)
    assert snap == kept


def test_a_snapshot_that_disagrees_on_the_blueprint_does_not_restore() -> None:
    game = _game()
    game.narrative.story_blueprint = make_blueprint()
    snap = game.snapshot()
    game.narrative.story_blueprint = None
    with pytest.raises(ValueError, match="story blueprint"):
        game.restore(snap)
