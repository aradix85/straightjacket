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


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture()
def game(stub_engine):
    """Fresh game state with known resource values (stubbed engine config)."""
    g = GameState()
    g.resources = Resources(health=5, spirit=5, supply=5, momentum=2, max_momentum=10)
    g.setting_id = "starforged"
    return g


@pytest.fixture()
def game_real(load_engine):
    """Fresh game state with real engine.yaml (for config-driven resolution tests)."""
    g = GameState()
    g.resources = Resources(health=5, spirit=5, supply=5, momentum=2, max_momentum=10)
    g.setting_id = "starforged"
    return g


# ── Effect parsing ───────────────────────────────────────────


class TestParseEffect:
    def test_momentum_positive(self):
        e = parse_effect("momentum +2")
        assert e.type == "momentum"
        assert e.value == 2

    def test_momentum_negative(self):
        e = parse_effect("momentum -1")
        assert e.type == "momentum"
        assert e.value == -1

    def test_health_positive(self):
        e = parse_effect("health +3")
        assert e.type == "health"
        assert e.value == 3

    def test_spirit_negative(self):
        e = parse_effect("spirit -2")
        assert e.type == "spirit"
        assert e.value == -2

    def test_supply_negative(self):
        e = parse_effect("supply -1")
        assert e.type == "supply"
        assert e.value == -1

    def test_mark_progress(self):
        e = parse_effect("mark_progress 2")
        assert e.type == "mark_progress"
        assert e.value == 2

    def test_pay_the_price(self):
        e = parse_effect("pay_the_price")
        assert e.type == "pay_the_price"

    def test_position_in_control(self):
        e = parse_effect("position in_control")
        assert e.type == "position"
        assert e.target == "in_control"

    def test_position_bad_spot(self):
        e = parse_effect("position bad_spot")
        assert e.type == "position"
        assert e.target == "bad_spot"

    def test_next_move_bonus(self):
        e = parse_effect("next_move_bonus +1")
        assert e.type == "next_move_bonus"
        assert e.value == 1

    def test_suffer_move(self):
        e = parse_effect("suffer_move -2")
        assert e.type == "suffer_move"
        assert e.value == -2

    def test_legacy_reward(self):
        e = parse_effect("legacy_reward quests")
        assert e.type == "legacy_reward"
        assert e.target == "quests"

    def test_fill_clock(self):
        e = parse_effect("fill_clock 1")
        assert e.type == "fill_clock"
        assert e.value == 1

    def test_narrative(self):
        e = parse_effect("narrative")
        assert e.type == "narrative"

    def test_unknown(self):
        e = parse_effect("xyzzy")
        assert e.type == "unknown"

    def test_parse_effects_list(self):
        effects = parse_effects(["momentum +1", "position in_control"])
        assert len(effects) == 2
        assert effects[0].type == "momentum"
        assert effects[1].type == "position"

    def test_integrity(self):
        e = parse_effect("integrity +1")
        assert e.type == "integrity"
        assert e.value == 1


# ── Effect application ───────────────────────────────────────


class TestApplyEffects:
    def test_momentum_gain(self, game):
        effects = parse_effects(["momentum +2"])
        result = apply_effects(game, effects)
        assert game.resources.momentum == 4
        assert "momentum +2" in result.consequences

    def test_momentum_loss(self, game):
        effects = parse_effects(["momentum -1"])
        result = apply_effects(game, effects)
        assert game.resources.momentum == 1
        assert "momentum -1" in result.consequences

    def test_momentum_clamped_to_max(self, game):
        game.resources.momentum = 9
        effects = parse_effects(["momentum +2"])
        apply_effects(game, effects)
        assert game.resources.momentum == 10

    def test_momentum_clamped_to_floor(self, game):
        game.resources.momentum = -5
        effects = parse_effects(["momentum -2"])
        apply_effects(game, effects)
        assert game.resources.momentum == -6  # floor is -6

    def test_health_gain(self, game):
        game.resources.health = 3
        effects = parse_effects(["health +2"])
        result = apply_effects(game, effects)
        assert game.resources.health == 5
        assert "health +2" in result.consequences

    def test_health_loss(self, game):
        effects = parse_effects(["health -2"])
        result = apply_effects(game, effects)
        assert game.resources.health == 3
        assert "health -2" in result.consequences

    def test_health_clamped_to_max(self, game):
        game.resources.health = 5
        effects = parse_effects(["health +1"])
        result = apply_effects(game, effects)
        assert game.resources.health == 5
        # No consequence logged when no actual change
        assert not any("health" in c for c in result.consequences)

    def test_spirit_gain(self, game):
        game.resources.spirit = 3
        effects = parse_effects(["spirit +2"])
        apply_effects(game, effects)
        assert game.resources.spirit == 5

    def test_supply_loss(self, game):
        effects = parse_effects(["supply -1"])
        apply_effects(game, effects)
        assert game.resources.supply == 4

    def test_mark_progress(self, game):
        effects = parse_effects(["mark_progress 2"])
        result = apply_effects(game, effects)
        assert result.progress_marks == 2

    def test_pay_the_price(self, game):
        effects = parse_effects(["pay_the_price"])
        result = apply_effects(game, effects)
        assert result.pay_the_price is True

    def test_position_in_control(self, game):
        effects = parse_effects(["position in_control"])
        result = apply_effects(game, effects)
        assert result.combat_position == "in_control"

    def test_position_bad_spot(self, game):
        effects = parse_effects(["position bad_spot"])
        result = apply_effects(game, effects)
        assert result.combat_position == "bad_spot"

    def test_next_move_bonus(self, game):
        effects = parse_effects(["next_move_bonus +1"])
        result = apply_effects(game, effects)
        assert result.next_move_bonus == 1

    def test_fill_clock(self, game):
        effects = parse_effects(["fill_clock 2"])
        result = apply_effects(game, effects)
        assert result.clock_fills == 2

    def test_narrative(self, game):
        effects = parse_effects(["narrative"])
        result = apply_effects(game, effects)
        assert result.narrative_only is True

    def test_multiple_effects(self, game):
        effects = parse_effects(["momentum +2", "position in_control"])
        result = apply_effects(game, effects)
        assert game.resources.momentum == 4
        assert result.combat_position == "in_control"

    def test_suffer_move_generic(self, game):
        """Generic suffer picks highest track."""
        game.resources.health = 5
        game.resources.spirit = 3
        game.resources.supply = 2
        effects = parse_effects(["suffer_move -1"])
        result = apply_effects(game, effects)
        # Should pick health (highest)
        assert game.resources.health == 4
        assert "health -1" in result.consequences


# ── Suffer handler ───────────────────────────────────────────


class TestSufferHandler:
    def test_strong_hit_recovery(self, game):
        game.resources.health = 3
        params = {"track": "health", "recovery": 1, "blocking_impact": "wounded"}
        result = apply_suffer_handler(game, "STRONG_HIT", params)
        assert game.resources.health == 4
        assert "health +1" in result.consequences

    def test_strong_hit_track_at_max(self, game):
        """When track is at max, take momentum instead."""
        game.resources.health = 5
        params = {"track": "health", "recovery": 1, "blocking_impact": "wounded"}
        result = apply_suffer_handler(game, "STRONG_HIT", params)
        assert game.resources.momentum == 3
        assert "momentum +1" in result.consequences

    def test_weak_hit_exchange(self, game):
        game.resources.health = 3
        game.resources.momentum = 4
        params = {"track": "health", "recovery": 1, "blocking_impact": "wounded"}
        apply_suffer_handler(game, "WEAK_HIT", params)
        assert game.resources.health == 4
        assert game.resources.momentum == 3

    def test_miss_extra_damage(self, game):
        game.resources.health = 3
        params = {
            "track": "health",
            "miss_extra_track": -1,
            "miss_extra_momentum": -2,
            "impact_pair": ["wounded", "permanently_harmed"],
        }
        apply_suffer_handler(game, "MISS", params)
        assert game.resources.health == 2

    def test_miss_at_zero_reports_impact(self, game):
        game.resources.health = 0
        game.resources.momentum = 5
        params = {
            "track": "health",
            "miss_extra_track": -1,
            "miss_extra_momentum": -2,
            "impact_pair": ["wounded", "permanently_harmed"],
        }
        result = apply_suffer_handler(game, "MISS", params)
        # Can't lose health at 0, takes momentum instead
        assert game.resources.momentum == 3
        assert any("must mark" in c for c in result.consequences)


# ── Threshold handler ────────────────────────────────────────


class TestThresholdHandler:
    def test_strong_hit_survive(self, game):
        params = {"impact": "doomed", "game_over_text": "you are dead"}
        result = apply_threshold_handler(game, "STRONG_HIT", params)
        assert result.narrative_only is True
        assert not game.game_over

    def test_weak_hit_impact(self, game):
        params = {"impact": "doomed", "game_over_text": "you are dead"}
        result = apply_threshold_handler(game, "WEAK_HIT", params)
        assert "mark doomed" in result.consequences

    def test_miss_game_over(self, game):
        params = {"impact": "doomed", "game_over_text": "you are dead"}
        result = apply_threshold_handler(game, "MISS", params)
        assert game.game_over is True
        assert "you are dead" in result.consequences


# ── Recovery handler ─────────────────────────────────────────


class TestRecoveryHandler:
    def test_strong_hit_full_recovery(self, game):
        game.resources.health = 2
        params = {
            "track": "health",
            "full_amount": 3,
            "impact_amount": 2,
            "blocking_impact": "wounded",
        }
        apply_recovery_handler(game, "STRONG_HIT", params)
        assert game.resources.health == 5

    def test_weak_hit_with_cost(self, game):
        game.resources.health = 2
        game.resources.momentum = 5
        params = {
            "track": "health",
            "full_amount": 3,
            "impact_amount": 2,
            "blocking_impact": "wounded",
            "weak_hit_cost_type": "momentum",
            "weak_hit_cost": -2,
        }
        apply_recovery_handler(game, "WEAK_HIT", params)
        assert game.resources.health == 5
        assert game.resources.momentum == 3

    def test_miss_pay_the_price(self, game):
        params = {"track": "health", "full_amount": 3, "impact_amount": 2, "blocking_impact": "wounded"}
        result = apply_recovery_handler(game, "MISS", params)
        assert result.pay_the_price is True


# ── Config-driven resolution ─────────────────────────────────


class TestResolveOutcome:
    def test_face_danger_strong_hit(self, game_real):
        result = resolve_move_outcome(game_real, "adventure/face_danger", "STRONG_HIT")
        assert game_real.resources.momentum == 3
        assert "momentum +1" in result.consequences

    def test_face_danger_miss(self, game_real):
        result = resolve_move_outcome(game_real, "adventure/face_danger", "MISS")
        assert result.pay_the_price is True

    def test_strike_strong_hit_position(self, game_real):
        result = resolve_move_outcome(game_real, "combat/strike", "STRONG_HIT")
        assert result.combat_position == "in_control"
        assert result.progress_marks == 2

    def test_strike_weak_hit_bad_spot(self, game_real):
        result = resolve_move_outcome(game_real, "combat/strike", "WEAK_HIT")
        assert result.combat_position == "bad_spot"
        assert result.progress_marks == 2

    def test_enter_fray_strong_hit(self, game_real):
        result = resolve_move_outcome(game_real, "combat/enter_the_fray", "STRONG_HIT")
        assert game_real.resources.momentum == 4
        assert result.combat_position == "in_control"

    def test_endure_harm_handler(self, game_real):
        game_real.resources.health = 3
        resolve_move_outcome(game_real, "suffer/endure_harm", "STRONG_HIT")
        assert game_real.resources.health == 4

    def test_endure_stress_handler(self, game_real):
        game_real.resources.spirit = 3
        resolve_move_outcome(game_real, "suffer/endure_stress", "STRONG_HIT")
        assert game_real.resources.spirit == 4

    def test_face_death_miss(self, game_real):
        resolve_move_outcome(game_real, "threshold/face_death", "MISS")
        assert game_real.game_over is True

    def test_heal_strong_hit(self, game_real):
        game_real.resources.health = 2
        resolve_move_outcome(game_real, "recover/heal", "STRONG_HIT")
        assert game_real.resources.health == 5

    def test_scene_challenge_face_danger_weak_hit(self, game_real):
        result = resolve_move_outcome(game_real, "scene_challenge/face_danger", "WEAK_HIT")
        assert result.progress_marks == 1
        assert result.clock_fills == 1

    def test_unknown_move_raises(self, game_real):
        with pytest.raises(ValueError, match="No outcome config"):
            resolve_move_outcome(game_real, "nonexistent/move", "STRONG_HIT")

    def test_gather_information_strong_hit(self, game_real):
        result = resolve_move_outcome(game_real, "adventure/gather_information", "STRONG_HIT")
        assert game_real.resources.momentum == 4
        assert "momentum +2" in result.consequences

    def test_swear_vow_strong_hit(self, game_real):
        resolve_move_outcome(game_real, "quest/swear_an_iron_vow", "STRONG_HIT")
        assert game_real.resources.momentum == 4

    def test_resupply_miss(self, game_real):
        result = resolve_move_outcome(game_real, "recover/resupply", "MISS")
        assert result.pay_the_price is True


# ── Combat position in WorldState ────────────────────────────


class TestCombatPosition:
    def test_combat_position_default_empty(self):
        g = GameState()
        assert g.world.combat_position == ""

    def test_combat_position_serializes(self):
        g = GameState()
        g.world.combat_position = "in_control"
        d = g.world.to_dict()
        assert d["combat_position"] == "in_control"

    def test_combat_position_deserializes(self):
        from straightjacket.engine.models_base import WorldState

        w = WorldState.from_dict({"combat_position": "bad_spot", "chaos_factor": 5})
        assert w.combat_position == "bad_spot"

    def test_combat_position_snapshot_restore(self):
        g = GameState()
        g.world.combat_position = "in_control"
        snap = g.snapshot()
        g.world.combat_position = "bad_spot"
        # Restore bypasses db sync in test context, so we test the dict level
        assert snap.world["combat_position"] == "in_control"


# ── Progress roll through turn pipeline ──────────────────────


class TestProgressRollPipeline:
    def test_progress_roll_uses_track_boxes(self, game_real):
        """roll_progress uses filled_boxes from the track."""
        from straightjacket.engine.mechanics.consequences import roll_progress
        from straightjacket.engine.models import ProgressTrack

        track = ProgressTrack(id="v1", name="Find the artifact", track_type="vow", rank="dangerous", ticks=24)
        assert track.filled_boxes == 6  # 24 ticks / 4 = 6 boxes

        roll = roll_progress(track.name, track.filled_boxes, "quest/fulfill_your_vow")
        assert roll.stat_value == 6
        assert roll.action_score == 6
        assert roll.d1 == 0
        assert roll.d2 == 0

    def test_find_progress_track(self, game_real):
        """_find_progress_track returns the right track by category."""
        from straightjacket.engine.game.turn import _find_progress_track
        from straightjacket.engine.models import ProgressTrack

        game_real.progress_tracks = [
            ProgressTrack(id="v1", name="Old vow", track_type="vow", ticks=8),
            ProgressTrack(id="c1", name="Fight", track_type="combat", ticks=12),
            ProgressTrack(id="v2", name="New vow", track_type="vow", ticks=20),
        ]

        # Multiple vow tracks without target_track → error
        with pytest.raises(ValueError, match="Multiple active vow tracks"):
            _find_progress_track(game_real, "Vow")

        # With target_track → finds by name substring
        vow = _find_progress_track(game_real, "Vow", target_track="New")
        assert vow is not None
        assert vow.name == "New vow"

        vow_old = _find_progress_track(game_real, "Vow", target_track="Old")
        assert vow_old is not None
        assert vow_old.name == "Old vow"

        # Single combat track → auto-selects
        combat = _find_progress_track(game_real, "Combat")
        assert combat is not None
        assert combat.name == "Fight"

        # No expedition tracks → None
        expedition = _find_progress_track(game_real, "Expedition")
        assert expedition is None

        # Completed tracks filtered out
        game_real.progress_tracks[0].status = "completed"
        vow_active = _find_progress_track(game_real, "Vow")
        assert vow_active is not None
        assert vow_active.name == "New vow"  # only active one left
