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
    pkg = load_package(setting_id)
    return _load_moves_from_setting(pkg, pkg)


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
        categories = {key.split("/")[0] for key in moves}
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

    def test_all_moves_have_a_name(self) -> None:
        moves = _own_moves("starforged")
        for key, move in moves.items():
            assert move.name, f"{key} missing name"

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
        assert ute != get_moves("starforged")["exploration/undertake_an_expedition"]

    def test_non_overridden_moves_preserved(self) -> None:
        moves = get_moves("sundered_isles")
        assert moves["adventure/face_danger"] == get_moves("starforged")["adventure/face_danger"]

    def test_si_withstand_damage(self) -> None:
        moves = get_moves("sundered_isles")
        assert moves["suffer/withstand_damage"] == _own_moves("sundered_isles")["suffer/withstand_damage"]

    def test_replaced_moves_roll_their_own_tables(self) -> None:
        isles = get_moves("sundered_isles")
        starforged = get_moves("starforged")
        for key, table in (
            ("exploration/make_a_discovery", "make_a_discovery"),
            ("exploration/confront_chaos", "confront_chaos"),
        ):
            own = [row.text for row in isles[key].tables[table].rows]
            assert own != [row.text for row in starforged[key].tables[table].rows]
        assert (
            isles["exploration/make_a_discovery"].tables["make_a_discovery"].rows[0].text == "Abundant and unusual life"
        )


class TestMoveTables:
    def test_a_move_carries_the_tables_datasworn_names_for_it(self) -> None:
        assert set(get_moves("starforged")["fate/pay_the_price"].tables) == {"pay_the_price", "story_complication"}
        assert set(get_moves("classic")["fate/pay_the_price"].tables) == {"pay_the_price"}
        assert set(get_moves("starforged")["adventure/gather_information"].tables) == {"story_clue"}
        assert get_moves("classic")["adventure/gather_information"].tables == {}

    def test_an_inherited_move_reads_its_tables_from_its_own_package(self) -> None:
        delve = get_moves("delve")
        assert (
            delve["suffer/endure_harm"].tables["endure_harm"]
            is get_moves("classic")["suffer/endure_harm"].tables["endure_harm"]
        )
        assert set(delve["delve/delve_the_depths"].tables) == {"edge", "shadow", "wits"}


class TestRollMethods:
    def test_conditions_keep_their_method_and_text(self) -> None:
        heal = get_moves("classic")["adventure/heal"]
        assert [(c.method, c.text) for c in heal.conditions] == [
            ("player_choice", ""),
            ("lowest", "Mend your own wounds"),
        ]

    def test_a_lowest_way_is_answered_with_its_method(self) -> None:
        assert get_moves("classic")["adventure/heal"].stat_answers == ["wits", "lowest"]
        assert get_moves("starforged")["recover/heal"].stat_answers == ["iron", "lowest", "heart", "wits"]
        assert get_moves("starforged")["adventure/face_danger"].stat_answers == [
            "edge",
            "heart",
            "iron",
            "shadow",
            "wits",
        ]


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
        assert (
            moves["exploration/undertake_an_expedition"]
            != get_moves("starforged")["exploration/undertake_an_expedition"]
        )

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
        move = _parse_move(raw, load_package("starforged"))
        assert move.name == "Test Move"
        assert move.roll_type == "no_roll"
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
        move = _parse_move(raw, load_package("starforged"))
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
        move = _parse_move(raw, load_package("starforged"))
        assert move.valid_stats == ["iron"]
