from straightjacket.engine.models import GameState, Resources
from tests._helpers import make_game_state


def _game() -> GameState:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    g.resources = Resources(health=3, spirit=3, supply=3, momentum=5, max_momentum=10)
    return g


class TestApplyImpact:
    def test_apply_new_impact(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import apply_impact

        game = _game()
        assert apply_impact(game, "wounded") is True
        assert "wounded" in game.impacts

    def test_apply_duplicate_returns_false(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import apply_impact

        game = _game()
        apply_impact(game, "wounded")
        assert apply_impact(game, "wounded") is False
        assert game.impacts.count("wounded") == 1

    def test_apply_unknown_impact_returns_false(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import apply_impact

        game = _game()
        assert apply_impact(game, "nonexistent_impact") is False
        assert "nonexistent_impact" not in game.impacts


class TestClearImpact:
    def test_clear_active_impact(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import apply_impact, clear_impact

        game = _game()
        apply_impact(game, "wounded")
        assert clear_impact(game, "wounded") is True
        assert "wounded" not in game.impacts

    def test_clear_inactive_impact_returns_false(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import clear_impact

        game = _game()
        assert clear_impact(game, "wounded") is False

    def test_cannot_clear_permanent_impact(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import apply_impact, clear_impact

        game = _game()
        apply_impact(game, "permanently_harmed")
        assert clear_impact(game, "permanently_harmed") is False
        assert "permanently_harmed" in game.impacts


class TestRecalcMaxMomentum:
    def test_no_impacts_keeps_base_max(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import recalc_max_momentum

        game = _game()
        recalc_max_momentum(game)
        assert game.resources.max_momentum == 10

    def test_each_impact_reduces_max_by_one(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import apply_impact

        game = _game()
        apply_impact(game, "wounded")
        assert game.resources.max_momentum == 9
        apply_impact(game, "shaken")
        assert game.resources.max_momentum == 8

    def test_momentum_clamped_to_new_max(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import apply_impact

        game = _game()
        game.resources.momentum = 10
        apply_impact(game, "wounded")
        assert game.resources.momentum == 9

    def test_clear_restores_momentum_max(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import apply_impact, clear_impact

        game = _game()
        apply_impact(game, "wounded")
        apply_impact(game, "shaken")
        clear_impact(game, "wounded")
        assert game.resources.max_momentum == 9


class TestBlocksRecovery:
    def test_wounded_blocks_health_recovery(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import apply_impact, blocks_recovery

        game = _game()
        apply_impact(game, "wounded")
        assert blocks_recovery(game, "health") == "wounded"

    def test_shaken_blocks_spirit_recovery(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import apply_impact, blocks_recovery

        game = _game()
        apply_impact(game, "shaken")
        assert blocks_recovery(game, "spirit") == "shaken"

    def test_unprepared_blocks_supply_recovery(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import apply_impact, blocks_recovery

        game = _game()
        apply_impact(game, "unprepared")
        assert blocks_recovery(game, "supply") == "unprepared"

    def test_no_impact_no_block(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import blocks_recovery

        game = _game()
        assert blocks_recovery(game, "health") == ""

    def test_doomed_does_not_block_recovery(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import apply_impact, blocks_recovery

        game = _game()
        apply_impact(game, "doomed")
        assert blocks_recovery(game, "health") == ""


class TestImpactsSnapshotRestore:
    def test_impacts_restored(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import apply_impact

        game = _game()
        apply_impact(game, "wounded")
        snap = game.snapshot()

        apply_impact(game, "shaken")
        assert len(game.impacts) == 2

        game.restore(snap)
        assert game.impacts == ["wounded"]
        assert game.resources.max_momentum == 9

    def test_impacts_round_trip(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import apply_impact

        game = _game()
        apply_impact(game, "doomed")
        apply_impact(game, "tormented")

        d = game.to_dict()
        game2 = GameState.from_dict(d)
        assert sorted(game2.impacts) == ["doomed", "tormented"]


class TestSufferHandlerMarksImpact:
    def test_miss_at_zero_health_marks_wounded(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.move_handlers import apply_suffer_handler

        game = _game()
        game.resources.health = 0
        params = {
            "track": "health",
            "recovery": 1,
            "miss_extra_track": -1,
            "miss_extra_momentum": -2,
            "impact_pair": ["wounded", "permanently_harmed"],
            "blocking_impact": "wounded",
        }
        result = apply_suffer_handler(game, "MISS", params)
        assert "wounded" in game.impacts
        assert any("wounded" in c for c in result.consequences)

    def test_second_hit_marks_worse_impact(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import apply_impact
        from straightjacket.engine.mechanics.move_handlers import apply_suffer_handler

        game = _game()
        game.resources.health = 0
        apply_impact(game, "wounded")
        params = {
            "track": "health",
            "recovery": 1,
            "miss_extra_track": -1,
            "miss_extra_momentum": -2,
            "impact_pair": ["wounded", "permanently_harmed"],
            "blocking_impact": "wounded",
        }
        apply_suffer_handler(game, "MISS", params)
        assert "permanently_harmed" in game.impacts


class TestRecoveryHandlerClearsImpact:
    def test_heal_clears_wounded(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import apply_impact
        from straightjacket.engine.mechanics.move_handlers import apply_recovery_handler

        game = _game()
        apply_impact(game, "wounded")
        params = {
            "track": "health",
            "full_amount": 3,
            "impact_amount": 2,
            "blocking_impact": "wounded",
            "weak_hit_cost_type": "momentum",
            "weak_hit_cost": -2,
        }
        result = apply_recovery_handler(game, "STRONG_HIT", params)
        assert "wounded" not in game.impacts
        assert any("wounded" in c for c in result.consequences)

    def test_no_impact_no_clear(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.move_handlers import apply_recovery_handler

        game = _game()
        params = {
            "track": "health",
            "full_amount": 3,
            "impact_amount": 2,
            "blocking_impact": "wounded",
            "weak_hit_cost_type": "momentum",
            "weak_hit_cost": -2,
        }
        result = apply_recovery_handler(game, "STRONG_HIT", params)
        assert not any("wounded" in c for c in result.consequences)


class TestThresholdHandlerMarksImpact:
    def test_face_death_weak_hit_marks_doomed(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.move_handlers import apply_threshold_handler

        game = _game()
        result = apply_threshold_handler(game, "WEAK_HIT", {"impact": "doomed"})
        assert "doomed" in game.impacts
        assert any("doomed" in c for c in result.consequences)


class TestImpactsStatus:
    def test_impacts_shown_in_status(self, load_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import apply_impact
        from straightjacket.web.serializers import build_narrative_status

        game = _game()
        game.setting_id = "starforged"
        apply_impact(game, "wounded")
        apply_impact(game, "doomed")
        text = build_narrative_status(game)
        assert "wounded" in text
        assert "doomed" in text

    def test_no_impacts_no_line(self, load_engine: None) -> None:
        from straightjacket.web.serializers import build_narrative_status

        game = _game()
        text = build_narrative_status(game)
        assert "Impacts:" not in text


class TestImpactAcknowledgmentValidator:
    def test_impact_label_in_narration_passes(self) -> None:
        from straightjacket.engine.ai.rule_validator import check_impact_acknowledgment

        result = check_impact_acknowledgment(
            "The wound will not heal quickly. You are wounded, deeply.",
            ["wounded"],
        )
        assert result == []

    def test_missing_impact_fails(self) -> None:
        from straightjacket.engine.ai.rule_validator import check_impact_acknowledgment

        result = check_impact_acknowledgment(
            "The fight ends. You walk away, unaffected.",
            ["wounded"],
        )
        assert len(result) == 1
        assert "IMPACT CHANGE" in result[0]

    def test_no_changes_passes(self) -> None:
        from straightjacket.engine.ai.rule_validator import check_impact_acknowledgment

        result = check_impact_acknowledgment("Anything.", [])
        assert result == []

    def test_multiword_label_matches_on_first_word(self) -> None:
        from straightjacket.engine.ai.rule_validator import check_impact_acknowledgment

        result = check_impact_acknowledgment(
            "The damage is permanently etched in your flesh.",
            ["permanently harmed"],
        )
        assert result == []


class TestCharacterStatePromptTag:
    def test_no_impacts_no_tag(self, load_engine: None) -> None:
        from straightjacket.engine.prompt_shared import _scene_header

        game = _game()
        header = _scene_header(game)
        assert "character_state" not in header

    def test_impacts_in_character_state(self, load_engine: None) -> None:
        from straightjacket.engine.mechanics.impacts import apply_impact
        from straightjacket.engine.prompt_shared import _scene_header

        game = _game()
        game.setting_id = "starforged"
        apply_impact(game, "wounded")
        apply_impact(game, "doomed")
        header = _scene_header(game)
        assert "character_state" in header
        assert "wounded" in header
        assert "doomed" in header
