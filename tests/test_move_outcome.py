import pytest

from straightjacket.engine.models import GameState, Resources, labels_of
from straightjacket.engine.ruleset.move_effects import apply_effects, parse_effect, parse_effects
from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
from tests._helpers import make_game_state, record_price_tables


@pytest.fixture
def game(load_engine: None) -> GameState:
    g = make_game_state()
    g.resources = Resources(meters={"health": 5, "spirit": 5, "supply": 5, "momentum": 2}, next_move_bonus=0)
    g.setting_id = "starforged"
    return g


class TestParseEffect:
    @pytest.mark.parametrize(
        ("effect_str", "expected_type", "expected_value", "expected_target"),
        [
            ("momentum +2", "momentum", 2, ""),
            ("momentum -1", "momentum", -1, ""),
            ("health +3", "health", 3, ""),
            ("spirit -2", "spirit", -2, ""),
            ("supply -1", "supply", -1, ""),
            ("mark_progress 2", "mark_progress", 2, ""),
            ("next_move_bonus +1", "next_move_bonus", 1, ""),
            ("suffer_move -2", "suffer_move", -2, ""),
            ("fill_clock 1", "fill_clock", 1, ""),
            ("position in_control", "position", 0, "in_control"),
            ("position bad_spot", "position", 0, "bad_spot"),
            ("legacy_reward quests", "legacy_reward", 0, "quests"),
            ("pay_the_price", "pay_the_price", 0, ""),
        ],
    )
    def test_parse_effect(self, effect_str: str, expected_type: str, expected_value: int, expected_target: str) -> None:
        e = parse_effect(effect_str)
        assert e.type == expected_type
        assert e.value == expected_value
        if expected_target:
            assert e.target == expected_target

    def test_parse_effect_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="xyzzy"):
            parse_effect("xyzzy")

    def test_parse_effects_list(self) -> None:
        effects = parse_effects(["momentum +1", "position in_control"])
        assert len(effects) == 2
        assert effects[0].type == "momentum"
        assert effects[1].type == "position"


class TestApplyEffects:
    @pytest.mark.parametrize(
        ("effect", "track", "start", "expected", "cons_fragment"),
        [
            ("momentum +2", "momentum", 2, 4, "momentum +2"),
            ("momentum -1", "momentum", 2, 1, "momentum -1"),
            ("health +2", "health", 3, 5, "health +2"),
            ("health -2", "health", 5, 3, "health -2"),
            ("spirit +2", "spirit", 3, 5, ""),
            ("supply -1", "supply", 5, 4, ""),
        ],
    )
    def test_resource_change(
        self, game: GameState, effect: str, track: str, start: int, expected: int, cons_fragment: str
    ) -> None:
        game.resources.meters[track] = start
        result = apply_effects(game, parse_effects([effect]))
        assert game.resources.meters[track] == expected
        if cons_fragment:
            assert cons_fragment in labels_of(result.consequences)

    def test_momentum_clamped_to_max(self, game: GameState) -> None:
        game.resources.meters["momentum"] = 9
        apply_effects(game, parse_effects(["momentum +2"]))
        assert game.resources.meters["momentum"] == 10

    def test_momentum_clamped_to_floor(self, game: GameState) -> None:
        game.resources.meters["momentum"] = -5
        apply_effects(game, parse_effects(["momentum -2"]))
        assert game.resources.meters["momentum"] == -6

    def test_health_clamped_to_max_no_consequence(self, game: GameState) -> None:
        result = apply_effects(game, parse_effects(["health +1"]))
        assert game.resources.meters["health"] == 5
        assert not any("health" in c for c in labels_of(result.consequences))

    @pytest.mark.parametrize(
        ("effect", "attr", "expected"),
        [
            ("mark_progress 2", "progress_marks", 2),
            ("position in_control", "combat_position", "in_control"),
            ("position bad_spot", "combat_position", "bad_spot"),
            ("fill_clock 2", "clock_fills", 2),
        ],
    )
    def test_result_fields(self, game: GameState, effect: str, attr: str, expected: object) -> None:
        result = apply_effects(game, parse_effects([effect]))
        assert getattr(result, attr) == expected

    def test_next_move_bonus_waits_for_the_next_roll(self, game: GameState) -> None:
        result = apply_effects(game, parse_effects(["next_move_bonus +1"]))
        assert game.resources.next_move_bonus == 1
        assert "next move +1" in labels_of(result.consequences)

    def test_no_effects_change_nothing(self, game: GameState) -> None:
        before = game.resources.snapshot()
        result = apply_effects(game, [])
        assert game.resources.snapshot() == before
        assert labels_of(result.consequences) == []

    def test_multiple_effects(self, game: GameState) -> None:
        result = apply_effects(game, parse_effects(["momentum +2", "position in_control"]))
        assert game.resources.meters["momentum"] == 4
        assert result.combat_position == "in_control"

    def test_suffer_move_picks_highest_track(self, game: GameState) -> None:
        game.resources.meters["health"] = 5
        game.resources.meters["spirit"] = 3
        game.resources.meters["supply"] = 2
        result = apply_effects(game, parse_effects(["suffer_move -1"]))
        assert game.resources.meters["health"] == 4
        assert "health -1" in labels_of(result.consequences)


class TestEndureHarm:
    def test_a_strong_hit_takes_back_health(self, game: GameState) -> None:
        game.resources.meters["health"] = 3
        result = resolve_move_outcome(game, "suffer/endure_harm", "STRONG_HIT", target_npc_id=None, match=False)
        assert game.resources.meters["health"] == 4
        assert "health +1" in labels_of(result.consequences)

    def test_a_strong_hit_at_full_health_takes_momentum(self, game: GameState) -> None:
        result = resolve_move_outcome(game, "suffer/endure_harm", "STRONG_HIT", target_npc_id=None, match=False)
        assert game.resources.meters["momentum"] == 3
        assert "momentum +1" in labels_of(result.consequences)

    def test_a_weak_hit_exchanges_momentum_for_health(self, game: GameState) -> None:
        game.resources.meters["health"] = 3
        game.resources.meters["momentum"] = 4
        resolve_move_outcome(game, "suffer/endure_harm", "WEAK_HIT", target_npc_id=None, match=False)
        assert (game.resources.meters["health"], game.resources.meters["momentum"]) == (4, 3)

    def test_a_miss_above_zero_costs_more_health(self, game: GameState) -> None:
        game.resources.meters["health"] = 3
        resolve_move_outcome(game, "suffer/endure_harm", "MISS", target_npc_id=None, match=False)
        assert game.resources.meters["health"] == 2


@pytest.mark.parametrize(("result_type", "game_over"), [("STRONG_HIT", False), ("MISS", True)])
def test_face_death_returns_on_a_strong_hit_and_dies_on_a_miss(
    game: GameState, result_type: str, game_over: bool
) -> None:
    result = resolve_move_outcome(game, "threshold/face_death", result_type, target_npc_id=None, match=False)
    assert game.game_over is game_over
    assert labels_of(result.consequences) == (["you are dead"] if game_over else [])
    assert game.impacts == []


class TestHeal:
    def test_a_strong_hit_heals_its_full_amount(self, game: GameState) -> None:
        game.resources.meters["health"] = 2
        resolve_move_outcome(game, "recover/heal", "STRONG_HIT", target_npc_id=None, match=False)
        assert game.resources.meters["health"] == 5

    def test_a_weak_hit_heals_at_a_cost_of_momentum(self, game: GameState) -> None:
        game.resources.meters["health"] = 2
        game.resources.meters["momentum"] = 5
        resolve_move_outcome(game, "recover/heal", "WEAK_HIT", target_npc_id=None, match=False)
        assert (game.resources.meters["health"], game.resources.meters["momentum"]) == (5, 3)


class TestResolveOutcome:
    @pytest.mark.parametrize(
        ("move", "result_type", "check_fn"),
        [
            (
                "adventure/face_danger",
                "STRONG_HIT",
                lambda g, r: g.resources.meters["momentum"] == 3 and "momentum +1" in labels_of(r.consequences),
            ),
            ("adventure/gather_information", "STRONG_HIT", lambda g, r: g.resources.meters["momentum"] == 4),
            ("quest/swear_an_iron_vow", "STRONG_HIT", lambda g, r: g.resources.meters["momentum"] == 4),
        ],
    )
    def test_simple_outcomes(self, game: GameState, move: str, result_type: str, check_fn: object) -> None:
        result = resolve_move_outcome(game, move, result_type, target_npc_id=None, match=False)
        assert check_fn(game, result)

    @pytest.mark.parametrize("move", ["adventure/face_danger", "recover/heal", "recover/resupply"])
    def test_a_miss_pays_the_price(self, game: GameState, monkeypatch: pytest.MonkeyPatch, move: str) -> None:
        rolled = record_price_tables(monkeypatch)
        resolve_move_outcome(game, move, "MISS", target_npc_id=None, match=False)
        assert rolled == ["Pay the Price"]

    def test_strike_strong_hit_position(self, game: GameState) -> None:
        result = resolve_move_outcome(game, "combat/strike", "STRONG_HIT", target_npc_id=None, match=False)
        assert result.combat_position == "in_control"
        assert result.progress_marks == 2

    def test_strike_weak_hit_bad_spot(self, game: GameState) -> None:
        result = resolve_move_outcome(game, "combat/strike", "WEAK_HIT", target_npc_id=None, match=False)
        assert result.combat_position == "bad_spot"
        assert result.progress_marks == 2

    def test_enter_fray_strong_hit(self, game: GameState) -> None:
        result = resolve_move_outcome(game, "combat/enter_the_fray", "STRONG_HIT", target_npc_id=None, match=False)
        assert game.resources.meters["momentum"] == 4
        assert result.combat_position == "in_control"

    def test_endure_stress_handler(self, game: GameState) -> None:
        game.resources.meters["spirit"] = 3
        resolve_move_outcome(game, "suffer/endure_stress", "STRONG_HIT", target_npc_id=None, match=False)
        assert game.resources.meters["spirit"] == 4

    def test_scene_challenge_face_danger_weak_hit(self, game: GameState) -> None:
        result = resolve_move_outcome(game, "scene_challenge/face_danger", "WEAK_HIT", target_npc_id=None, match=False)
        assert result.progress_marks == 1
        assert result.clock_fills == 1

    @pytest.mark.parametrize("move", ["adventure/gather_information", "adventure/compel"])
    def test_weak_hit_names_its_complication(self, game: GameState, move: str) -> None:
        weak = resolve_move_outcome(game, move, "WEAK_HIT", target_npc_id=None, match=False)
        strong = resolve_move_outcome(game, move, "STRONG_HIT", target_npc_id=None, match=False)
        kind = move.split("/")[1]
        assert f"complication {kind}" in labels_of(weak.consequences)
        assert not any(c.startswith("complication") for c in labels_of(strong.consequences))

    def test_unknown_move_raises(self, game: GameState) -> None:
        with pytest.raises(ValueError, match="No outcome config"):
            resolve_move_outcome(game, "nonexistent/move", "STRONG_HIT", target_npc_id=None, match=False)
