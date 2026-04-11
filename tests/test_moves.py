"""Tests for Datasworn move loader (step 7a).

Covers: move parsing, all four settings, roll type distribution,
trigger extraction, expansion merge, cache, lookup, and edge cases.
"""

import pytest

from straightjacket.engine.datasworn.moves import (
    _parse_move,
    clear_cache,
    get_moves,
    load_moves,
)


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_moves_cache():
    """Clear moves cache before each test."""
    clear_cache()
    yield
    clear_cache()


# ── Starforged ───────────────────────────────────────────────


class TestStarforgedMoves:
    def test_move_count(self):
        moves = load_moves("starforged")
        assert len(moves) == 56

    def test_roll_type_distribution(self):
        moves = load_moves("starforged")
        by_type: dict[str, int] = {}
        for m in moves.values():
            by_type[m.roll_type] = by_type.get(m.roll_type, 0) + 1
        assert by_type["action_roll"] == 31
        assert by_type["no_roll"] == 18
        assert by_type["progress_roll"] == 5
        assert by_type["special_track"] == 2

    def test_face_danger_structure(self):
        moves = load_moves("starforged")
        fd = moves["adventure/face_danger"]
        assert fd.name == "Face Danger"
        assert fd.roll_type == "action_roll"
        assert fd.category == "adventure"
        assert fd.key == "face_danger"
        assert fd.valid_stats == ["edge", "heart", "iron", "shadow", "wits"]
        assert "strong_hit" in fd.outcomes
        assert "weak_hit" in fd.outcomes
        assert "miss" in fd.outcomes
        assert fd.trigger_method == "player_choice"

    def test_scene_challenge_face_danger_separate(self):
        """Scene challenge variant is separate from adventure variant."""
        moves = load_moves("starforged")
        assert "adventure/face_danger" in moves
        assert "scene_challenge/face_danger" in moves
        adv = moves["adventure/face_danger"]
        sc = moves["scene_challenge/face_danger"]
        assert adv.name == "Face Danger"
        assert sc.name == "Face Danger (Scene Challenge)"
        assert adv.id != sc.id

    def test_endure_harm_highest_method(self):
        moves = load_moves("starforged")
        eh = moves["suffer/endure_harm"]
        assert eh.roll_type == "action_roll"
        assert eh.trigger_method == "highest"
        assert eh.valid_stats == ["iron"]
        assert eh.valid_condition_meters == ["health"]

    def test_endure_stress_highest_method(self):
        moves = load_moves("starforged")
        es = moves["suffer/endure_stress"]
        assert es.trigger_method == "highest"
        assert es.valid_stats == ["heart"]
        assert es.valid_condition_meters == ["spirit"]

    def test_heal_lowest_method(self):
        moves = load_moves("starforged")
        h = moves["recover/heal"]
        methods = {c.method for c in h.conditions}
        assert "lowest" in methods

    def test_fulfill_your_vow_progress_roll(self):
        moves = load_moves("starforged")
        fv = moves["quest/fulfill_your_vow"]
        assert fv.roll_type == "progress_roll"
        assert fv.track_category == "Vow"
        assert fv.trigger_method == "progress_roll"

    def test_forge_a_bond_progress_roll(self):
        moves = load_moves("starforged")
        fb = moves["connection/forge_a_bond"]
        assert fb.roll_type == "progress_roll"
        assert fb.track_category == "Connection"

    def test_take_decisive_action(self):
        moves = load_moves("starforged")
        tda = moves["combat/take_decisive_action"]
        assert tda.roll_type == "progress_roll"
        assert tda.track_category == "Combat"
        assert len(tda.oracle_ids) > 0

    def test_no_roll_move(self):
        moves = load_moves("starforged")
        fv = moves["quest/forsake_your_vow"]
        assert fv.roll_type == "no_roll"
        assert fv.outcomes == {}
        assert fv.conditions == []

    def test_special_track_move(self):
        moves = load_moves("starforged")
        od = moves["threshold/overcome_destruction"]
        assert od.roll_type == "special_track"

    def test_continue_a_legacy_all_method(self):
        moves = load_moves("starforged")
        cal = moves["legacy/continue_a_legacy"]
        assert cal.roll_type == "special_track"
        assert cal.trigger_method == "all"
        usings = {ro.using for c in cal.conditions for ro in c.roll_options}
        assert "quests_legacy" in usings
        assert "bonds_legacy" in usings
        assert "discoveries_legacy" in usings

    def test_develop_your_relationship_custom(self):
        moves = load_moves("starforged")
        dyr = moves["connection/develop_your_relationship"]
        assert dyr.roll_type == "action_roll"
        custom_options = [ro for c in dyr.conditions for ro in c.roll_options if ro.using == "custom"]
        assert len(custom_options) >= 5
        values = {ro.value for ro in custom_options}
        assert values == {1, 2, 3, 4, 5}

    def test_companion_takes_a_hit_asset_control(self):
        moves = load_moves("starforged")
        cth = moves["suffer/companion_takes_a_hit"]
        asset_options = [ro for c in cth.conditions for ro in c.roll_options if ro.using == "asset_control"]
        assert len(asset_options) >= 1
        assert asset_options[0].control == "health"

    def test_withstand_damage_asset_control(self):
        moves = load_moves("starforged")
        wd = moves["suffer/withstand_damage"]
        asset_options = [ro for c in wd.conditions for ro in c.roll_options if ro.using == "asset_control"]
        assert len(asset_options) >= 1
        assert asset_options[0].control == "integrity"

    def test_check_your_gear_condition_meter(self):
        moves = load_moves("starforged")
        cyg = moves["adventure/check_your_gear"]
        assert cyg.valid_condition_meters == ["supply"]

    def test_oracle_ids_present(self):
        moves = load_moves("starforged")
        eh = moves["suffer/endure_harm"]
        assert len(eh.oracle_ids) > 0
        ptp = moves["fate/pay_the_price"]
        assert len(ptp.oracle_ids) > 0

    def test_ask_the_oracle_oracles(self):
        moves = load_moves("starforged")
        ato = moves["fate/ask_the_oracle"]
        assert len(ato.oracle_ids) == 5

    def test_all_categories_present(self):
        moves = load_moves("starforged")
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

    def test_all_moves_have_id_and_name(self):
        moves = load_moves("starforged")
        for key, move in moves.items():
            assert move.id, f"{key} missing id"
            assert move.name, f"{key} missing name"
            assert key.endswith(f"/{move.key}"), f"{key} doesn't end with /{move.key}"

    def test_action_rolls_have_outcomes(self):
        moves = load_moves("starforged")
        for key, move in moves.items():
            if move.roll_type == "action_roll":
                assert "strong_hit" in move.outcomes, f"{key} missing strong_hit"
                assert "weak_hit" in move.outcomes, f"{key} missing weak_hit"
                assert "miss" in move.outcomes, f"{key} missing miss"

    def test_progress_rolls_have_outcomes(self):
        moves = load_moves("starforged")
        for key, move in moves.items():
            if move.roll_type == "progress_roll":
                assert "strong_hit" in move.outcomes, f"{key} missing strong_hit"

    def test_action_rolls_have_conditions(self):
        moves = load_moves("starforged")
        for key, move in moves.items():
            if move.roll_type == "action_roll":
                assert len(move.conditions) > 0, f"{key} has no trigger conditions"


# ── Classic ──────────────────────────────────────────────────


class TestClassicMoves:
    def test_move_count(self):
        moves = load_moves("classic")
        assert len(moves) == 35

    def test_roll_type_distribution(self):
        moves = load_moves("classic")
        by_type: dict[str, int] = {}
        for m in moves.values():
            by_type[m.roll_type] = by_type.get(m.roll_type, 0) + 1
        assert by_type["action_roll"] == 22
        assert by_type["no_roll"] == 9
        assert by_type["progress_roll"] == 3
        assert by_type["special_track"] == 1

    def test_classic_specific_moves(self):
        moves = load_moves("classic")
        assert "relationship/draw_the_circle" in moves
        assert "adventure/undertake_a_journey" in moves
        assert "adventure/make_camp" in moves
        assert "relationship/write_your_epilogue" in moves

    def test_write_your_epilogue_special_track(self):
        moves = load_moves("classic")
        we = moves["relationship/write_your_epilogue"]
        assert we.roll_type == "special_track"

    def test_classic_face_danger(self):
        moves = load_moves("classic")
        fd = moves["adventure/face_danger"]
        assert fd.valid_stats == ["edge", "heart", "iron", "shadow", "wits"]

    def test_make_camp_condition_meter(self):
        moves = load_moves("classic")
        mc = moves["adventure/make_camp"]
        assert mc.valid_condition_meters == ["supply"]


# ── Delve (expansion on Classic) ─────────────────────────────


class TestDelveMoves:
    def test_expansion_move_count(self):
        """Delve alone has 13 moves."""
        moves = load_moves("delve")
        assert len(moves) == 13

    def test_merged_move_count(self):
        """Delve merged with Classic: 35 Classic + 13 Delve."""
        moves = load_moves("delve", parent_id="classic")
        assert len(moves) == 35 + 13

    def test_delve_specific_moves_present(self):
        moves = load_moves("delve", parent_id="classic")
        assert "delve/discover_a_site" in moves
        assert "delve/delve_the_depths" in moves
        assert "delve/locate_your_objective" in moves
        assert "delve/escape_the_depths" in moves

    def test_classic_moves_preserved(self):
        moves = load_moves("delve", parent_id="classic")
        assert "adventure/face_danger" in moves
        assert "combat/strike" in moves
        assert "quest/swear_an_iron_vow" in moves

    def test_delve_the_depths_stats(self):
        moves = load_moves("delve", parent_id="classic")
        dtd = moves["delve/delve_the_depths"]
        assert set(dtd.valid_stats) == {"edge", "shadow", "wits"}

    def test_locate_your_objective_progress(self):
        moves = load_moves("delve", parent_id="classic")
        lyo = moves["delve/locate_your_objective"]
        assert lyo.roll_type == "progress_roll"
        assert lyo.track_category == "Delve"

    def test_replaces_field(self):
        moves = load_moves("delve")
        rad_alt = moves.get("delve/reveal_a_danger_alt")
        if rad_alt:
            assert len(rad_alt.replaces) > 0

    def test_delve_oracles(self):
        moves = load_moves("delve", parent_id="classic")
        dtd = moves["delve/delve_the_depths"]
        assert len(dtd.oracle_ids) > 0


# ── Sundered Isles (expansion on Starforged) ─────────────────


class TestSunderedIslesMoves:
    def test_expansion_move_count(self):
        """SI alone has 8 moves."""
        moves = load_moves("sundered_isles")
        assert len(moves) == 8

    def test_merged_move_count(self):
        """SI merged with Starforged: 56 base, 8 SI override same keys."""
        moves = load_moves("sundered_isles", parent_id="starforged")
        assert len(moves) == 56

    def test_si_overrides_starforged(self):
        """SI moves replace their Starforged counterparts."""
        moves = load_moves("sundered_isles", parent_id="starforged")
        ute = moves["exploration/undertake_an_expedition"]
        assert "sundered_isles" in ute.id
        assert "sail" in ute.text.lower()

    def test_non_overridden_moves_preserved(self):
        moves = load_moves("sundered_isles", parent_id="starforged")
        fd = moves["adventure/face_danger"]
        assert "starforged" in fd.id

    def test_allow_momentum_burn(self):
        moves = load_moves("sundered_isles")
        ute = moves["exploration/undertake_an_expedition"]
        assert ute.allow_momentum_burn is True
        mad = moves["exploration/make_a_discovery"]
        assert mad.allow_momentum_burn is False

    def test_replaces_field(self):
        moves = load_moves("sundered_isles")
        ute = moves["exploration/undertake_an_expedition"]
        assert len(ute.replaces) > 0
        assert any("starforged" in r for r in ute.replaces)

    def test_si_inline_oracles(self):
        """SI has inline oracle tables instead of string references."""
        moves = load_moves("sundered_isles")
        mad = moves["exploration/make_a_discovery"]
        assert len(mad.oracle_ids) > 0

    def test_si_withstand_damage(self):
        moves = load_moves("sundered_isles", parent_id="starforged")
        wd = moves["suffer/withstand_damage"]
        assert "sundered_isles" in wd.id


# ── get_moves (cached, auto-parent) ─────────────────────────


class TestGetMoves:
    def test_starforged_cached(self):
        m1 = get_moves("starforged")
        m2 = get_moves("starforged")
        assert m1 is m2

    def test_classic_cached(self):
        m1 = get_moves("classic")
        m2 = get_moves("classic")
        assert m1 is m2

    def test_delve_auto_parent(self):
        """get_moves('delve') auto-resolves parent to classic."""
        moves = get_moves("delve")
        assert "adventure/face_danger" in moves
        assert "delve/delve_the_depths" in moves

    def test_sundered_isles_auto_parent(self):
        """get_moves('sundered_isles') auto-resolves parent to starforged."""
        moves = get_moves("sundered_isles")
        assert "adventure/face_danger" in moves
        assert "sundered_isles" in moves["exploration/undertake_an_expedition"].id

    def test_clear_cache(self):
        m1 = get_moves("starforged")
        clear_cache()
        m2 = get_moves("starforged")
        assert m1 is not m2


# ── Parse edge cases ─────────────────────────────────────────


class TestParsing:
    def test_parse_move_minimal(self):
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

    def test_parse_move_with_outcomes(self):
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
        assert move.trigger_method == "player_choice"

    def test_parse_replaces_string(self):
        """Delve uses a plain string for replaces."""
        raw = {
            "_id": "test/moves/cat/m",
            "type": "move",
            "name": "M",
            "roll_type": "no_roll",
            "text": "...",
            "trigger": {"conditions": None, "text": "..."},
            "outcomes": None,
            "replaces": "other/moves/cat/m",
        }
        move = _parse_move(raw, "cat")
        assert move.replaces == ["other/moves/cat/m"]

    def test_parse_replaces_list(self):
        """SI uses a list for replaces."""
        raw = {
            "_id": "test/moves/cat/m",
            "type": "move",
            "name": "M",
            "roll_type": "no_roll",
            "text": "...",
            "trigger": {"conditions": None, "text": "..."},
            "outcomes": None,
            "replaces": ["move:other/cat/m"],
        }
        move = _parse_move(raw, "cat")
        assert move.replaces == ["move:other/cat/m"]

    def test_valid_stats_deduplication(self):
        """Multiple conditions with same stat should not duplicate."""
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
