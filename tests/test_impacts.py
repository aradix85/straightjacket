import pytest

from straightjacket.engine.models import GameState, Resources, labels_of
from straightjacket.engine.ruleset.config import rules
from tests._helpers import make_game_state


def _game() -> GameState:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    g.resources = Resources(meters={"health": 3, "spirit": 3, "supply": 3, "momentum": 5}, next_move_bonus=0)
    return g


class TestApplyImpact:
    def test_apply_new_impact(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact

        game = _game()
        assert apply_impact(game, "wounded") is True
        assert "wounded" in game.impacts

    def test_apply_duplicate_returns_false(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact

        game = _game()
        apply_impact(game, "wounded")
        assert apply_impact(game, "wounded") is False
        assert game.impacts.count("wounded") == 1

    def test_apply_unknown_impact_raises(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact

        game = _game()
        with pytest.raises(KeyError, match="nonexistent_impact"):
            apply_impact(game, "nonexistent_impact")
        assert "nonexistent_impact" not in game.impacts


class TestImpactsFromTheRules:
    def test_each_ruleset_names_its_own_impacts(self, load_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import get_impacts

        assert "maimed" in get_impacts("classic")
        assert "permanently_harmed" not in get_impacts("classic")
        assert "permanently_harmed" in get_impacts("starforged")
        assert get_impacts("delve") == get_impacts("classic")
        assert get_impacts("sundered_isles") == get_impacts("starforged")
        assert get_impacts("starforged")["wounded"].prevents_recovery == ["health"]
        assert get_impacts("starforged")["traumatized"].permanent

    def test_an_impact_another_ruleset_has_is_refused(self, load_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact

        game = _game()
        game.setting_id = "classic"
        with pytest.raises(KeyError, match="permanently_harmed"):
            apply_impact(game, "permanently_harmed")

    def test_every_impact_a_move_marks_is_its_rulesets_own(self, load_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import get_impacts
        from straightjacket.engine.ruleset.moves import get_moves
        from straightjacket.engine.ruleset.outcome_result import move_outcome_config
        from straightjacket.engine.setting.packages import list_packages

        outcomes = rules().get_raw("move_outcomes")
        for setting_id in list_packages():
            game = make_game_state(setting_id=setting_id)
            named: set[str] = set(rules().suffer.exhausted_impacts.values())
            for key in get_moves(setting_id):
                if key not in outcomes:
                    continue
                params = move_outcome_config(game, key).get("params", {})
                named.update(params.get("impact_pair", []))
                named.update(params[name] for name in ("impact",) if params.get(name))
            assert named <= set(get_impacts(setting_id)), (setting_id, named - set(get_impacts(setting_id)))


class TestClearImpact:
    def test_clear_active_impact(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact, clear_impact

        game = _game()
        apply_impact(game, "wounded")
        assert clear_impact(game, "wounded") is True
        assert "wounded" not in game.impacts

    def test_clear_inactive_impact_returns_false(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import clear_impact

        game = _game()
        assert clear_impact(game, "wounded") is False

    def test_cannot_clear_permanent_impact(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact, clear_impact

        game = _game()
        apply_impact(game, "permanently_harmed")
        assert clear_impact(game, "permanently_harmed") is False
        assert "permanently_harmed" in game.impacts


class TestMaxMomentum:
    def test_no_impacts_keeps_base_max(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.meters import max_momentum

        assert max_momentum(_game()) == 10

    def test_each_impact_reduces_max_by_one(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact
        from straightjacket.engine.ruleset.meters import max_momentum

        game = _game()
        apply_impact(game, "wounded")
        assert max_momentum(game) == 9
        apply_impact(game, "shaken")
        assert max_momentum(game) == 8

    def test_momentum_gained_stops_at_the_lowered_max(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact
        from straightjacket.engine.ruleset.meters import adjust_momentum

        game = _game()
        apply_impact(game, "wounded")
        game.resources.meters["momentum"] = 8
        adjust_momentum(game, 2)
        assert game.resources.meters["momentum"] == 9

    def test_momentum_clamped_to_new_max(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact

        game = _game()
        game.resources.meters["momentum"] = 10
        apply_impact(game, "wounded")
        assert game.resources.meters["momentum"] == 9

    def test_clear_restores_momentum_max(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact, clear_impact
        from straightjacket.engine.ruleset.meters import max_momentum

        game = _game()
        apply_impact(game, "wounded")
        apply_impact(game, "shaken")
        clear_impact(game, "wounded")
        assert max_momentum(game) == 9


class TestBlocksRecovery:
    def test_wounded_blocks_health_recovery(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact, blocks_recovery

        game = _game()
        apply_impact(game, "wounded")
        assert blocks_recovery(game, "health") == "wounded"

    def test_shaken_blocks_spirit_recovery(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact, blocks_recovery

        game = _game()
        apply_impact(game, "shaken")
        assert blocks_recovery(game, "spirit") == "shaken"

    def test_unprepared_blocks_supply_recovery(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact, blocks_recovery

        game = _game()
        apply_impact(game, "unprepared")
        assert blocks_recovery(game, "supply") == "unprepared"

    def test_no_impact_no_block(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import blocks_recovery

        game = _game()
        assert blocks_recovery(game, "health") == ""

    def test_doomed_does_not_block_recovery(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact, blocks_recovery

        game = _game()
        apply_impact(game, "doomed")
        assert blocks_recovery(game, "health") == ""


class TestImpactsSnapshotRestore:
    def test_impacts_restored(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact
        from straightjacket.engine.ruleset.meters import max_momentum

        game = _game()
        apply_impact(game, "wounded")
        snap = game.snapshot()

        apply_impact(game, "shaken")
        assert len(game.impacts) == 2

        game.restore(snap)
        assert game.impacts == ["wounded"]
        assert max_momentum(game) == 9

    def test_impacts_round_trip(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact

        game = _game()
        apply_impact(game, "doomed")
        apply_impact(game, "tormented")

        d = game.to_dict()
        game2 = GameState.from_dict(d)
        assert sorted(game2.impacts) == ["doomed", "tormented"]


class TestSufferHandlerMarksImpact:
    def test_miss_at_zero_health_marks_wounded(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.move_handlers import apply_suffer_handler

        game = _game()
        game.resources.meters["health"] = 0
        params = {
            "track": "health",
            "recovery": 1,
            "miss_extra_track": -1,
            "miss_extra_momentum": -2,
            "strong_hit_exchange_cost": 0,
            "weak_hit_exchange": True,
            "recover_from_zero": True,
            "impact_pair": ["wounded", "permanently_harmed"],
        }
        result = apply_suffer_handler(game, "suffer/endure_harm", "MISS", params)
        assert "wounded" in game.impacts
        assert any("wounded" in c for c in labels_of(result.consequences))

    def test_second_hit_marks_worse_impact(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact
        from straightjacket.engine.ruleset.move_handlers import apply_suffer_handler

        game = _game()
        game.resources.meters["health"] = 0
        apply_impact(game, "wounded")
        params = {
            "track": "health",
            "recovery": 1,
            "miss_extra_track": -1,
            "miss_extra_momentum": -2,
            "strong_hit_exchange_cost": 0,
            "weak_hit_exchange": True,
            "recover_from_zero": True,
            "impact_pair": ["wounded", "permanently_harmed"],
        }
        apply_suffer_handler(game, "suffer/endure_harm", "MISS", params)
        assert "permanently_harmed" in game.impacts


class TestRecoveryHandlerClearsImpact:
    @pytest.mark.parametrize(
        ("marked", "cleared", "spirit"),
        [("shaken", True, 3), ("wounded", False, 4)],
    )
    def test_the_impact_a_recovery_clears_is_the_one_its_rules_say_blocks_its_meter(
        self, load_engine: None, marked: str, cleared: bool, spirit: int
    ) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact
        from straightjacket.engine.ruleset.move_handlers import apply_recovery_handler

        game = _game()
        game.setting_id = "starforged"
        game.resources.meters["spirit"] = 2
        apply_impact(game, marked)
        params = {
            "track": "spirit",
            "full_amount": 2,
            "impact_amount": 1,
            "weak_hit_cost_type": "momentum",
            "weak_hit_cost": -1,
        }
        apply_recovery_handler(game, "recover/hearten", "STRONG_HIT", params)
        assert (marked not in game.impacts) is cleared
        assert game.resources.meters["spirit"] == spirit

    def test_heal_clears_wounded(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact
        from straightjacket.engine.ruleset.move_handlers import apply_recovery_handler

        game = _game()
        apply_impact(game, "wounded")
        params = {
            "track": "health",
            "full_amount": 3,
            "impact_amount": 2,
            "weak_hit_cost_type": "momentum",
            "weak_hit_cost": -2,
        }
        result = apply_recovery_handler(game, "recover/heal", "STRONG_HIT", params)
        assert "wounded" not in game.impacts
        assert any("wounded" in c for c in labels_of(result.consequences))

    def test_no_impact_no_clear(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.move_handlers import apply_recovery_handler

        game = _game()
        params = {
            "track": "health",
            "full_amount": 3,
            "impact_amount": 2,
            "weak_hit_cost_type": "momentum",
            "weak_hit_cost": -2,
        }
        result = apply_recovery_handler(game, "recover/heal", "STRONG_HIT", params)
        assert not any("wounded" in c for c in labels_of(result.consequences))


class TestImpactsStatus:
    def test_impacts_shown_in_status(self, load_engine: None) -> None:
        from straightjacket.engine.ruleset.impacts import apply_impact
        from straightjacket.web.serializers import build_narrative_status

        game = _game()
        game.setting_id = "starforged"
        game.world.time_of_day = "evening"
        apply_impact(game, "wounded")
        apply_impact(game, "doomed")
        text = build_narrative_status(game)
        assert "wounded" in text
        assert "doomed" in text

    def test_no_impacts_no_line(self, load_engine: None) -> None:
        from straightjacket.web.serializers import build_narrative_status

        game = _game()
        game.world.time_of_day = "evening"
        text = build_narrative_status(game)
        assert "Impacts:" not in text


class TestCharacterStatePromptTag:
    def test_no_impacts_no_tag(self, load_engine: None) -> None:
        from straightjacket.engine.prompt_shared import _scene_header

        game = _game()
        header = _scene_header(game)
        assert "character_state" not in header

    def test_impacts_in_character_state(self, load_engine: None) -> None:
        from straightjacket.engine.prompt_shared import _scene_header
        from straightjacket.engine.ruleset.impacts import apply_impact

        game = _game()
        game.setting_id = "starforged"
        game.world.time_of_day = "evening"
        apply_impact(game, "wounded")
        apply_impact(game, "doomed")
        header = _scene_header(game)
        assert '<character_state impacts="wounded, doomed">' in header
        assert (
            '<impact name="wounded">Wounded may be marked when you are at 0 health and fail to Endure Harm.' in header
        )
        assert "Doomed is marked when you Face Death" in header
        assert "](id:" not in header
