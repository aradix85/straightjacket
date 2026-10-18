import pytest

from straightjacket.engine.datasworn.moves import (
    Move,
    _load_moves_from_setting,
    _parse_move,
    clear_cache,
    get_moves,
)
from straightjacket.engine.datasworn.settings import load_package


from collections.abc import Generator


def _own_moves(setting_id: str) -> dict[str, Move]:
    return _load_moves_from_setting(load_package(setting_id).data)


@pytest.fixture(autouse=True)
def _clear_moves_cache() -> Generator[None, None, None]:
    clear_cache()
    yield
    clear_cache()


class TestStarforgedMoves:
    def test_move_count(self) -> None:
        moves = _own_moves("starforged")
        assert len(moves) == 56

    def test_roll_type_distribution(self) -> None:
        moves = _own_moves("starforged")
        by_type: dict[str, int] = {}
        for m in moves.values():
            by_type[m.roll_type] = by_type.get(m.roll_type, 0) + 1
        assert by_type["action_roll"] == 31
        assert by_type["no_roll"] == 18
        assert by_type["progress_roll"] == 5
        assert by_type["special_track"] == 2

    def test_face_danger_structure(self) -> None:
        moves = _own_moves("starforged")
        fd = moves["adventure/face_danger"]
        assert fd.name == "Face Danger"
        assert fd.roll_type == "action_roll"
        assert fd.category == "adventure"
        assert fd.key == "face_danger"
        assert fd.valid_stats == ["edge", "heart", "iron", "shadow", "wits"]
        assert "strong_hit" in fd.outcomes
        assert "weak_hit" in fd.outcomes
        assert "miss" in fd.outcomes

    def test_scene_challenge_face_danger_separate(self) -> None:
        moves = _own_moves("starforged")
        assert "adventure/face_danger" in moves
        assert "scene_challenge/face_danger" in moves
        adv = moves["adventure/face_danger"]
        sc = moves["scene_challenge/face_danger"]
        assert adv.name == "Face Danger"
        assert sc.name == "Face Danger (Scene Challenge)"
        assert adv.id != sc.id

    def test_endure_harm_highest_method(self) -> None:
        moves = _own_moves("starforged")
        eh = moves["suffer/endure_harm"]
        assert eh.roll_type == "action_roll"
        assert eh.valid_stats == ["iron"]
        assert [
            ro.condition_meter for c in eh.conditions for ro in c.roll_options if ro.using == "condition_meter"
        ] == ["health"]

    def test_endure_stress_highest_method(self) -> None:
        moves = _own_moves("starforged")
        es = moves["suffer/endure_stress"]
        assert es.valid_stats == ["heart"]
        assert [
            ro.condition_meter for c in es.conditions for ro in c.roll_options if ro.using == "condition_meter"
        ] == ["spirit"]

    def test_fulfill_your_vow_progress_roll(self) -> None:
        moves = _own_moves("starforged")
        fv = moves["quest/fulfill_your_vow"]
        assert fv.roll_type == "progress_roll"
        assert fv.track_category == "Vow"

    def test_forge_a_bond_progress_roll(self) -> None:
        moves = _own_moves("starforged")
        fb = moves["connection/forge_a_bond"]
        assert fb.roll_type == "progress_roll"
        assert fb.track_category == "Connection"

    def test_take_decisive_action(self) -> None:
        moves = _own_moves("starforged")
        tda = moves["combat/take_decisive_action"]
        assert tda.roll_type == "progress_roll"
        assert tda.track_category == "Combat"

    def test_no_roll_move(self) -> None:
        moves = _own_moves("starforged")
        fv = moves["quest/forsake_your_vow"]
        assert fv.roll_type == "no_roll"
        assert fv.outcomes == {}
        assert fv.conditions == []

    def test_special_track_move(self) -> None:
        moves = _own_moves("starforged")
        od = moves["threshold/overcome_destruction"]
        assert od.roll_type == "special_track"

    def test_continue_a_legacy_all_method(self) -> None:
        moves = _own_moves("starforged")
        cal = moves["legacy/continue_a_legacy"]
        assert cal.roll_type == "special_track"
        usings = {ro.using for c in cal.conditions for ro in c.roll_options}
        assert "quests_legacy" in usings
        assert "bonds_legacy" in usings
        assert "discoveries_legacy" in usings

    def test_develop_your_relationship_custom(self) -> None:
        moves = _own_moves("starforged")
        dyr = moves["connection/develop_your_relationship"]
        assert dyr.roll_type == "action_roll"
        custom_options = [ro for c in dyr.conditions for ro in c.roll_options if ro.using == "custom"]
        assert len(custom_options) >= 5
        values = {ro.value for ro in custom_options}
        assert values == {1, 2, 3, 4, 5}

    def test_companion_takes_a_hit_asset_control(self) -> None:
        moves = _own_moves("starforged")
        cth = moves["suffer/companion_takes_a_hit"]
        asset_options = [ro for c in cth.conditions for ro in c.roll_options if ro.using == "asset_control"]
        assert len(asset_options) >= 1

    def test_withstand_damage_asset_control(self) -> None:
        moves = _own_moves("starforged")
        wd = moves["suffer/withstand_damage"]
        asset_options = [ro for c in wd.conditions for ro in c.roll_options if ro.using == "asset_control"]
        assert len(asset_options) >= 1

    def test_check_your_gear_condition_meter(self) -> None:
        moves = _own_moves("starforged")
        cyg = moves["adventure/check_your_gear"]
        assert [
            ro.condition_meter for c in cyg.conditions for ro in c.roll_options if ro.using == "condition_meter"
        ] == ["supply"]

    def test_all_categories_present(self) -> None:
        moves = _own_moves("starforged")
        categories = {m.category for m in moves.values()}
        expected = {
            "session",
            "adventure",
            "quest",
            "connection",
            "exploration",
            "combat",
            "suffer",
            "recover",
            "threshold",
            "legacy",
            "fate",
            "scene_challenge",
        }
        assert categories == expected

    def test_all_moves_have_id_and_name(self) -> None:
        moves = _own_moves("starforged")
        for key, move in moves.items():
            assert move.id, f"{key} missing id"
            assert move.name, f"{key} missing name"
            assert key.endswith(f"/{move.key}"), f"{key} doesn't end with /{move.key}"

    def test_action_rolls_have_outcomes(self) -> None:
        moves = _own_moves("starforged")
        for key, move in moves.items():
            if move.roll_type == "action_roll":
                assert "strong_hit" in move.outcomes, f"{key} missing strong_hit"
                assert "weak_hit" in move.outcomes, f"{key} missing weak_hit"
                assert "miss" in move.outcomes, f"{key} missing miss"

    def test_progress_rolls_have_outcomes(self) -> None:
        moves = _own_moves("starforged")
        for key, move in moves.items():
            if move.roll_type == "progress_roll":
                assert "strong_hit" in move.outcomes, f"{key} missing strong_hit"

    def test_action_rolls_have_conditions(self) -> None:
        moves = _own_moves("starforged")
        for key, move in moves.items():
            if move.roll_type == "action_roll":
                assert len(move.conditions) > 0, f"{key} has no trigger conditions"


class TestClassicMoves:
    def test_move_count(self) -> None:
        moves = _own_moves("classic")
        assert len(moves) == 35

    def test_roll_type_distribution(self) -> None:
        moves = _own_moves("classic")
        by_type: dict[str, int] = {}
        for m in moves.values():
            by_type[m.roll_type] = by_type.get(m.roll_type, 0) + 1
        assert by_type["action_roll"] == 22
        assert by_type["no_roll"] == 9
        assert by_type["progress_roll"] == 3
        assert by_type["special_track"] == 1

    def test_classic_specific_moves(self) -> None:
        moves = _own_moves("classic")
        assert "relationship/draw_the_circle" in moves
        assert "adventure/undertake_a_journey" in moves
        assert "adventure/make_camp" in moves
        assert "relationship/write_your_epilogue" in moves

    def test_write_your_epilogue_special_track(self) -> None:
        moves = _own_moves("classic")
        we = moves["relationship/write_your_epilogue"]
        assert we.roll_type == "special_track"

    def test_classic_face_danger(self) -> None:
        moves = _own_moves("classic")
        fd = moves["adventure/face_danger"]
        assert fd.valid_stats == ["edge", "heart", "iron", "shadow", "wits"]

    def test_make_camp_condition_meter(self) -> None:
        moves = _own_moves("classic")
        mc = moves["adventure/make_camp"]
        assert [
            ro.condition_meter for c in mc.conditions for ro in c.roll_options if ro.using == "condition_meter"
        ] == ["supply"]


class TestDelveMoves:
    def test_expansion_move_count(self) -> None:
        moves = _own_moves("delve")
        assert len(moves) == 13

    def test_merged_move_count(self) -> None:
        moves = get_moves("delve")
        assert len(moves) == 35 + 13

    def test_delve_specific_moves_present(self) -> None:
        moves = get_moves("delve")
        assert "delve/discover_a_site" in moves
        assert "delve/delve_the_depths" in moves
        assert "delve/locate_your_objective" in moves
        assert "delve/escape_the_depths" in moves

    def test_classic_moves_preserved(self) -> None:
        moves = get_moves("delve")
        assert "adventure/face_danger" in moves
        assert "combat/strike" in moves
        assert "quest/swear_an_iron_vow" in moves

    def test_delve_the_depths_stats(self) -> None:
        moves = get_moves("delve")
        dtd = moves["delve/delve_the_depths"]
        assert set(dtd.valid_stats) == {"edge", "shadow", "wits"}

    def test_locate_your_objective_progress(self) -> None:
        moves = get_moves("delve")
        lyo = moves["delve/locate_your_objective"]
        assert lyo.roll_type == "progress_roll"
        assert lyo.track_category == "Delve"


class TestSunderedIslesMoves:
    def test_expansion_move_count(self) -> None:
        moves = _own_moves("sundered_isles")
        assert len(moves) == 8

    def test_merged_move_count(self) -> None:
        moves = get_moves("sundered_isles")
        assert len(moves) == 56

    def test_si_overrides_starforged(self) -> None:
        moves = get_moves("sundered_isles")
        ute = moves["exploration/undertake_an_expedition"]
        assert "sundered_isles" in ute.id
        assert "sail" in ute.text.lower()

    def test_non_overridden_moves_preserved(self) -> None:
        moves = get_moves("sundered_isles")
        fd = moves["adventure/face_danger"]
        assert "starforged" in fd.id

    def test_si_withstand_damage(self) -> None:
        moves = get_moves("sundered_isles")
        wd = moves["suffer/withstand_damage"]
        assert "sundered_isles" in wd.id


class TestGetMoves:
    def test_starforged_cached(self) -> None:
        m1 = get_moves("starforged")
        m2 = get_moves("starforged")
        assert m1 is m2

    def test_classic_cached(self) -> None:
        m1 = get_moves("classic")
        m2 = get_moves("classic")
        assert m1 is m2

    def test_delve_auto_parent(self) -> None:
        moves = get_moves("delve")
        assert "adventure/face_danger" in moves
        assert "delve/delve_the_depths" in moves

    def test_sundered_isles_auto_parent(self) -> None:
        moves = get_moves("sundered_isles")
        assert "adventure/face_danger" in moves
        assert "sundered_isles" in moves["exploration/undertake_an_expedition"].id

    def test_clear_cache(self) -> None:
        m1 = get_moves("starforged")
        clear_cache()
        m2 = get_moves("starforged")
        assert m1 is not m2


class TestParsing:
    def test_parse_move_minimal(self) -> None:
        raw = {
            "_id": "test/moves/test_cat/test_move",
            "type": "move",
            "name": "Test Move",
            "roll_type": "no_roll",
            "text": "Do the thing.",
            "trigger": {"conditions": None, "text": "When you do the thing..."},
            "outcomes": None,
        }
        move = _parse_move(raw, "test_cat")
        assert move.key == "test_move"
        assert move.name == "Test Move"
        assert move.roll_type == "no_roll"
        assert move.category == "test_cat"
        assert move.conditions == []
        assert move.outcomes == {}
        assert move.valid_stats == []

    def test_parse_move_with_outcomes(self) -> None:
        raw = {
            "_id": "test/moves/cat/m",
            "type": "move",
            "name": "M",
            "roll_type": "action_roll",
            "text": "...",
            "trigger": {
                "conditions": [
                    {
                        "method": "player_choice",
                        "roll_options": [{"using": "stat", "stat": "iron"}],
                    }
                ],
                "text": "...",
            },
            "outcomes": {
                "strong_hit": {"text": "You win."},
                "weak_hit": {"text": "Partial."},
                "miss": {"text": "Fail."},
            },
        }
        move = _parse_move(raw, "cat")
        assert move.valid_stats == ["iron"]
        assert move.outcomes["strong_hit"].text == "You win."

    def test_valid_stats_deduplication(self) -> None:
        raw = {
            "_id": "test/moves/cat/m",
            "type": "move",
            "name": "M",
            "roll_type": "action_roll",
            "text": "...",
            "trigger": {
                "conditions": [
                    {
                        "method": "player_choice",
                        "roll_options": [{"using": "stat", "stat": "iron"}],
                    },
                    {
                        "method": "player_choice",
                        "roll_options": [{"using": "stat", "stat": "iron"}],
                    },
                ],
                "text": "...",
            },
            "outcomes": {"strong_hit": {"text": "ok"}, "weak_hit": {"text": "ok"}, "miss": {"text": "ok"}},
        }
        move = _parse_move(raw, "cat")
        assert move.valid_stats == ["iron"]
