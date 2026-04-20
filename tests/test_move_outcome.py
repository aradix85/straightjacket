"""Tests for move outcome resolver (step 7b).

Covers: effect parsing, effect application, handler-based moves,
config-driven outcome resolution, combat position, and edge cases.
"""

import pytest

from straightjacket.engine.mechanics.move_outcome import (
    apply_effects,
    apply_recovery_handler,
    apply_suffer_handler,
    apply_threshold_handler,
    parse_effect,
    parse_effects,
    resolve_move_outcome,
)
from straightjacket.engine.models import GameState, Resources
from tests._helpers import make_game_state, make_progress_track


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture()
def game(stub_engine: None) -> GameState:
    """Fresh game state with known resource values (stubbed engine config)."""
    g = make_game_state()
    g.resources = Resources(health=5, spirit=5, supply=5, momentum=2, max_momentum=10)
    g.setting_id = "starforged"
    return g


@pytest.fixture()
def game_real(load_engine: None) -> GameState:
    """Fresh game state with real engine.yaml (for config-driven resolution tests)."""
    g = make_game_state()
    g.resources = Resources(health=5, spirit=5, supply=5, momentum=2, max_momentum=10)
    g.setting_id = "starforged"
    return g


# ── Effect parsing ───────────────────────────────────────────


class TestParseEffect:
    @pytest.mark.parametrize(
        "effect_str, expected_type, expected_value, expected_target",
        [
            ("momentum +2", "momentum", 2, ""),
            ("momentum -1", "momentum", -1, ""),
            ("health +3", "health", 3, ""),
            ("spirit -2", "spirit", -2, ""),
            ("supply -1", "supply", -1, ""),
            ("integrity +1", "integrity", 1, ""),
            ("mark_progress 2", "mark_progress", 2, ""),
            ("next_move_bonus +1", "next_move_bonus", 1, ""),
            ("suffer_move -2", "suffer_move", -2, ""),
            ("fill_clock 1", "fill_clock", 1, ""),
            ("position in_control", "position", 0, "in_control"),
            ("position bad_spot", "position", 0, "bad_spot"),
            ("legacy_reward quests", "legacy_reward", 0, "quests"),
            ("pay_the_price", "pay_the_price", 0, ""),
            ("narrative", "narrative", 0, ""),
            ("xyzzy", "unknown", 0, ""),
        ],
    )
    def test_parse_effect(self, effect_str: str, expected_type: str, expected_value: int, expected_target: str) -> None:
        e = parse_effect(effect_str)
        assert e.type == expected_type
        assert e.value == expected_value
        if expected_target:
            assert e.target == expected_target

    def test_parse_effects_list(self) -> None:
        effects = parse_effects(["momentum +1", "position in_control"])
        assert len(effects) == 2
        assert effects[0].type == "momentum"
        assert effects[1].type == "position"


# ── Effect application ───────────────────────────────────────


class TestApplyEffects:
    @pytest.mark.parametrize(
        "effect, track, start, expected, cons_fragment",
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
        setattr(game.resources, track, start)
        result = apply_effects(game, parse_effects([effect]))
        assert getattr(game.resources, track) == expected
        if cons_fragment:
            assert cons_fragment in result.consequences

    def test_momentum_clamped_to_max(self, game: GameState) -> None:
        game.resources.momentum = 9
        apply_effects(game, parse_effects(["momentum +2"]))
        assert game.resources.momentum == 10

    def test_momentum_clamped_to_floor(self, game: GameState) -> None:
        game.resources.momentum = -5
        apply_effects(game, parse_effects(["momentum -2"]))
        assert game.resources.momentum == -6

    def test_health_clamped_to_max_no_consequence(self, game: GameState) -> None:
        result = apply_effects(game, parse_effects(["health +1"]))
        assert game.resources.health == 5
        assert not any("health" in c for c in result.consequences)

    @pytest.mark.parametrize(
        "effect, attr, expected",
        [
            ("mark_progress 2", "progress_marks", 2),
            ("pay_the_price", "pay_the_price", True),
            ("position in_control", "combat_position", "in_control"),
            ("position bad_spot", "combat_position", "bad_spot"),
            ("next_move_bonus +1", "next_move_bonus", 1),
            ("fill_clock 2", "clock_fills", 2),
            ("narrative", "narrative_only", True),
        ],
    )
    def test_result_fields(self, game: GameState, effect: str, attr: str, expected: object) -> None:
        result = apply_effects(game, parse_effects([effect]))
        assert getattr(result, attr) == expected

    def test_multiple_effects(self, game: GameState) -> None:
        result = apply_effects(game, parse_effects(["momentum +2", "position in_control"]))
        assert game.resources.momentum == 4
        assert result.combat_position == "in_control"

    def test_pay_the_price_appends_oracle_line(self, game: GameState) -> None:
        """pay_the_price rolls the oracle table and adds the chosen line to consequences."""
        from straightjacket.engine.engine_loader import eng

        pay_lines = eng().get_raw("pay_the_price")
        result = apply_effects(game, parse_effects(["pay_the_price"]))
        assert result.pay_the_price is True
        assert len(result.consequences) == 1
        # The appended consequence must be one of the oracle lines (with
        # {player} substituted where applicable).
        rendered = {line.format(player=game.player_name) for line in pay_lines}
        assert result.consequences[0] in rendered

    def test_pay_the_price_substitutes_player_name(self, game: GameState) -> None:
        """Lines containing {player} are rendered with the current player name."""
        import random as _random

        # Force selection of the line that contains {player}: index 6 in the yaml
        # ("Someone saw what {player} did. They won't forget.")
        _random.seed(12345)
        from straightjacket.engine.engine_loader import eng

        pay_lines = eng().get_raw("pay_the_price")
        player_line_idx = next(i for i, line in enumerate(pay_lines) if "{player}" in line)

        # Seed-search for a seed that picks the player line.
        for seed in range(200):
            _random.seed(seed)
            if _random.randrange(len(pay_lines)) == player_line_idx:
                _random.seed(seed)
                break
        else:
            raise AssertionError("no seed in 0..199 selects the {player} line")

        result = apply_effects(game, parse_effects(["pay_the_price"]))
        assert game.player_name in result.consequences[0]
        assert "{player}" not in result.consequences[0]

    def test_suffer_move_picks_highest_track(self, game: GameState) -> None:
        game.resources.health = 5
        game.resources.spirit = 3
        game.resources.supply = 2
        result = apply_effects(game, parse_effects(["suffer_move -1"]))
        assert game.resources.health == 4
        assert "health -1" in result.consequences


_SUFFER_DEFAULTS = {
    "track": "health",
    "recovery": 1,
    "miss_extra_track": -1,
    "miss_extra_momentum": -2,
    "impact_pair": [],
    "blocking_impact": "",
}


def _suffer_params(**overrides: object) -> dict:
    """Build a complete suffer-handler params dict for tests."""
    merged = dict(_SUFFER_DEFAULTS)
    merged.update(overrides)  # type: ignore[arg-type]
    return merged


_RECOVERY_DEFAULTS = {
    "track": "health",
    "full_amount": 3,
    "impact_amount": 2,
    "blocking_impact": "",
    "weak_hit_cost_type": "momentum",
    "weak_hit_cost": -2,
}


def _recovery_params(**overrides: object) -> dict:
    """Build a complete recovery-handler params dict for tests."""
    merged = dict(_RECOVERY_DEFAULTS)
    merged.update(overrides)  # type: ignore[arg-type]
    return merged


# ── Suffer handler ───────────────────────────────────────────


class TestSufferHandler:
    def test_strong_hit_recovery(self, game: GameState) -> None:
        game.resources.health = 3
        result = apply_suffer_handler(
            game, "STRONG_HIT", _suffer_params(track="health", recovery=1, blocking_impact="wounded")
        )
        assert game.resources.health == 4
        assert "health +1" in result.consequences

    def test_strong_hit_track_at_max_takes_momentum(self, game: GameState) -> None:
        result = apply_suffer_handler(
            game, "STRONG_HIT", _suffer_params(track="health", recovery=1, blocking_impact="wounded")
        )
        assert game.resources.momentum == 3
        assert "momentum +1" in result.consequences

    def test_weak_hit_exchange(self, game: GameState) -> None:
        game.resources.health = 3
        game.resources.momentum = 4
        apply_suffer_handler(game, "WEAK_HIT", _suffer_params(track="health", recovery=1, blocking_impact="wounded"))
        assert game.resources.health == 4
        assert game.resources.momentum == 3

    def test_miss_extra_damage(self, game: GameState) -> None:
        game.resources.health = 3
        apply_suffer_handler(
            game,
            "MISS",
            _suffer_params(
                track="health",
                miss_extra_track=-1,
                miss_extra_momentum=-2,
                impact_pair=["wounded", "permanently_harmed"],
            ),
        )
        assert game.resources.health == 2

    def test_miss_at_zero_reports_impact(self, game: GameState) -> None:
        game.resources.health = 0
        game.resources.momentum = 5
        result = apply_suffer_handler(
            game,
            "MISS",
            _suffer_params(
                track="health",
                miss_extra_track=-1,
                miss_extra_momentum=-2,
                impact_pair=["wounded", "permanently_harmed"],
            ),
        )
        assert game.resources.momentum == 3
        assert any("mark wounded" in c for c in result.consequences)
        assert "wounded" in game.impacts


# ── Threshold handler ────────────────────────────────────────


class TestThresholdHandler:
    @pytest.mark.parametrize(
        "result_type, game_over, has_impact, narrative_only",
        [
            ("STRONG_HIT", False, False, True),
            ("WEAK_HIT", False, True, False),
            ("MISS", True, False, False),
        ],
    )
    def test_threshold_outcomes(
        self, game: GameState, result_type: str, game_over: bool, has_impact: bool, narrative_only: bool
    ) -> None:
        params = {"impact": "doomed", "game_over_text": "you are dead"}
        result = apply_threshold_handler(game, result_type, params)
        assert game.game_over == game_over
        assert result.narrative_only == narrative_only
        if has_impact:
            assert "mark doomed" in result.consequences
        if game_over:
            assert "you are dead" in result.consequences


# ── Recovery handler ─────────────────────────────────────────


class TestRecoveryHandler:
    def test_strong_hit_full_recovery(self, game: GameState) -> None:
        game.resources.health = 2
        apply_recovery_handler(
            game,
            "STRONG_HIT",
            _recovery_params(track="health", full_amount=3, impact_amount=2, blocking_impact="wounded"),
        )
        assert game.resources.health == 5

    def test_weak_hit_with_cost(self, game: GameState) -> None:
        game.resources.health = 2
        game.resources.momentum = 5
        apply_recovery_handler(
            game,
            "WEAK_HIT",
            _recovery_params(
                track="health",
                full_amount=3,
                impact_amount=2,
                blocking_impact="wounded",
                weak_hit_cost_type="momentum",
                weak_hit_cost=-2,
            ),
        )
        assert game.resources.health == 5
        assert game.resources.momentum == 3

    def test_miss_pay_the_price(self, game: GameState) -> None:
        result = apply_recovery_handler(
            game,
            "MISS",
            _recovery_params(track="health", full_amount=3, impact_amount=2, blocking_impact="wounded"),
        )
        assert result.pay_the_price is True


# ── Config-driven resolution ─────────────────────────────────


class TestResolveOutcome:
    @pytest.mark.parametrize(
        "move, result_type, check_fn",
        [
            (
                "adventure/face_danger",
                "STRONG_HIT",
                lambda g, r: g.resources.momentum == 3 and "momentum +1" in r.consequences,
            ),
            ("adventure/face_danger", "MISS", lambda g, r: r.pay_the_price is True),
            ("adventure/gather_information", "STRONG_HIT", lambda g, r: g.resources.momentum == 4),
            ("quest/swear_an_iron_vow", "STRONG_HIT", lambda g, r: g.resources.momentum == 4),
            ("recover/resupply", "MISS", lambda g, r: r.pay_the_price is True),
        ],
    )
    def test_simple_outcomes(self, game_real: GameState, move: str, result_type: str, check_fn: object) -> None:
        result = resolve_move_outcome(game_real, move, result_type)
        assert check_fn(game_real, result)  # type: ignore[operator]

    def test_strike_strong_hit_position(self, game_real: GameState) -> None:
        result = resolve_move_outcome(game_real, "combat/strike", "STRONG_HIT")
        assert result.combat_position == "in_control"
        assert result.progress_marks == 2

    def test_strike_weak_hit_bad_spot(self, game_real: GameState) -> None:
        result = resolve_move_outcome(game_real, "combat/strike", "WEAK_HIT")
        assert result.combat_position == "bad_spot"
        assert result.progress_marks == 2

    def test_enter_fray_strong_hit(self, game_real: GameState) -> None:
        result = resolve_move_outcome(game_real, "combat/enter_the_fray", "STRONG_HIT")
        assert game_real.resources.momentum == 4
        assert result.combat_position == "in_control"

    def test_endure_harm_handler(self, game_real: GameState) -> None:
        game_real.resources.health = 3
        resolve_move_outcome(game_real, "suffer/endure_harm", "STRONG_HIT")
        assert game_real.resources.health == 4

    def test_endure_stress_handler(self, game_real: GameState) -> None:
        game_real.resources.spirit = 3
        resolve_move_outcome(game_real, "suffer/endure_stress", "STRONG_HIT")
        assert game_real.resources.spirit == 4

    def test_face_death_miss(self, game_real: GameState) -> None:
        resolve_move_outcome(game_real, "threshold/face_death", "MISS")
        assert game_real.game_over is True

    def test_heal_strong_hit(self, game_real: GameState) -> None:
        game_real.resources.health = 2
        resolve_move_outcome(game_real, "recover/heal", "STRONG_HIT")
        assert game_real.resources.health == 5

    def test_scene_challenge_face_danger_weak_hit(self, game_real: GameState) -> None:
        result = resolve_move_outcome(game_real, "scene_challenge/face_danger", "WEAK_HIT")
        assert result.progress_marks == 1
        assert result.clock_fills == 1

    def test_unknown_move_raises(self, game_real: GameState) -> None:
        with pytest.raises(ValueError, match="No outcome config"):
            resolve_move_outcome(game_real, "nonexistent/move", "STRONG_HIT")


# ── Combat position in WorldState ────────────────────────────


class TestCombatPosition:
    def test_default_empty(self) -> None:
        assert make_game_state().world.combat_position == ""

    def test_serializes(self) -> None:
        g = make_game_state()
        g.world.combat_position = "in_control"
        assert g.world.to_dict()["combat_position"] == "in_control"

    def test_deserializes(self) -> None:
        from straightjacket.engine.models_base import WorldState

        assert WorldState.from_dict({"combat_position": "bad_spot", "chaos_factor": 5}).combat_position == "bad_spot"

    def test_snapshot_restore(self) -> None:
        g = make_game_state()
        g.world.combat_position = "in_control"
        snap = g.snapshot()
        g.world.combat_position = "bad_spot"
        assert snap.world["combat_position"] == "in_control"


# ── Progress roll through turn pipeline ──────────────────────


class TestProgressRollPipeline:
    def test_progress_roll_uses_track_boxes(self, game_real: GameState) -> None:
        from straightjacket.engine.mechanics.consequences import roll_progress

        track = make_progress_track(id="v1", name="Find the artifact", track_type="vow", rank="dangerous", ticks=24)
        assert track.filled_boxes == 6
        roll = roll_progress(track.name, track.filled_boxes, "quest/fulfill_your_vow")
        assert roll.stat_value == 6 and roll.action_score == 6 and roll.d1 == 0 and roll.d2 == 0

    def test_find_progress_track(self, game_real: GameState) -> None:
        from straightjacket.engine.game.tracks import find_progress_track as _find_progress_track

        game_real.progress_tracks = [
            make_progress_track(id="v1", name="Old vow", track_type="vow", ticks=8),
            make_progress_track(id="c1", name="Fight", track_type="combat", ticks=12),
            make_progress_track(id="v2", name="New vow", track_type="vow", ticks=20),
        ]
        with pytest.raises(ValueError, match="Multiple active vow tracks"):
            _find_progress_track(game_real, "Vow")

        assert _find_progress_track(game_real, "Vow", target_track="New").name == "New vow"  # type: ignore[union-attr]
        assert _find_progress_track(game_real, "Vow", target_track="Old").name == "Old vow"  # type: ignore[union-attr]
        assert _find_progress_track(game_real, "Combat").name == "Fight"  # type: ignore[union-attr]
        assert _find_progress_track(game_real, "Expedition") is None

        game_real.progress_tracks[0].status = "completed"
        assert _find_progress_track(game_real, "Vow").name == "New vow"  # type: ignore[union-attr]
