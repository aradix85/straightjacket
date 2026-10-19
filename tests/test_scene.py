import pytest

from straightjacket.engine.gamemaster.scene import SceneSetup, _roll_adjustments, adjustment_descriptions, check_scene
from tests._helpers import fix_dice, make_game_state, make_random_event


def test_expected_when_roll_above_cf(monkeypatch: pytest.MonkeyPatch) -> None:
    game = make_game_state()
    game.world.chaos_factor = 5
    fix_dice(monkeypatch, 6)
    setup = check_scene(game)
    assert setup.scene_type == "expected"


def test_expected_when_roll_is_10(monkeypatch: pytest.MonkeyPatch) -> None:
    game = make_game_state()
    game.world.chaos_factor = 9
    fix_dice(monkeypatch, 10)
    setup = check_scene(game)
    assert setup.scene_type == "expected"


def test_altered_when_roll_le_cf_odd(monkeypatch: pytest.MonkeyPatch) -> None:
    game = make_game_state()
    game.world.chaos_factor = 5
    fix_dice(monkeypatch, 3)
    setup = check_scene(game)
    assert setup.scene_type == "altered"
    assert len(setup.adjustments) >= 1


def test_interrupt_when_roll_le_cf_even(monkeypatch: pytest.MonkeyPatch) -> None:
    game = make_game_state()
    game.world.chaos_factor = 5
    fix_dice(monkeypatch, 4)
    setup = check_scene(game)
    assert setup.scene_type == "interrupt"
    assert setup.interrupt_event is not None
    assert setup.interrupt_event.source == "interrupt_scene"
    assert setup.interrupt_event.focus != ""


def test_cf1_only_roll1_triggers(monkeypatch: pytest.MonkeyPatch) -> None:
    game = make_game_state()
    game.world.chaos_factor = 1
    fix_dice(monkeypatch, 1)
    assert check_scene(game).scene_type == "altered"
    fix_dice(monkeypatch, 2)
    assert check_scene(game).scene_type == "expected"


def test_cf9_most_rolls_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    game = make_game_state()
    game.world.chaos_factor = 9
    fix_dice(monkeypatch, 10)
    assert check_scene(game).scene_type == "expected"
    fix_dice(monkeypatch, 9)
    assert check_scene(game).scene_type == "altered"
    fix_dice(monkeypatch, 8)
    assert check_scene(game).scene_type == "interrupt"


def test_single_adjustment(monkeypatch: pytest.MonkeyPatch) -> None:
    for roll in range(1, 7):
        fix_dice(monkeypatch, roll)
        adjs = _roll_adjustments()
        assert len(adjs) == 1
        assert adjs[0] != "make_2_adjustments"


def test_double_adjustment(monkeypatch: pytest.MonkeyPatch) -> None:
    fix_dice(monkeypatch, 7)
    adjs = _roll_adjustments()
    assert len(adjs) == 2
    for a in adjs:
        assert a != "make_2_adjustments"


def test_adjustment_types(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = {
        "remove_character",
        "add_character",
        "reduce_activity",
        "increase_activity",
        "remove_object",
        "add_object",
    }
    seen = set()
    for roll in range(1, 7):
        fix_dice(monkeypatch, roll)
        adjs = _roll_adjustments()
        seen.add(adjs[0])
    assert seen == expected


def test_adjustment_descriptions_maps_all() -> None:
    types = ["remove_character", "add_character", "reduce_activity", "increase_activity", "remove_object", "add_object"]
    descs = adjustment_descriptions(types)
    assert len(descs) == 6
    for d in descs:
        assert len(d) > 10


def test_scene_setup_roundtrip() -> None:
    setup = SceneSetup(scene_type="altered", adjustments=["add_character", "remove_object"])
    d = setup.to_dict()
    restored = SceneSetup.from_dict(d)
    assert restored.scene_type == "altered"
    assert restored.adjustments == ["add_character", "remove_object"]


def test_scene_setup_interrupt_roundtrip() -> None:
    event = make_random_event(focus="npc_action", meaning_action="Betray", meaning_subject="Trust")
    setup = SceneSetup(scene_type="interrupt", interrupt_event=event)
    d = setup.to_dict()
    restored = SceneSetup.from_dict(d)
    assert restored.scene_type == "interrupt"
    assert restored.interrupt_event is not None
    assert restored.interrupt_event.focus == "npc_action"
