import pytest

from straightjacket.engine.models import GameState, Resources, labels_of
from straightjacket.engine.prompt_boundary import build_new_game_prompt
from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.impacts import apply_impact, blocks_recovery, clear_impact, get_impacts
from straightjacket.engine.ruleset.meters import adjust_momentum, max_momentum
from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
from straightjacket.engine.ruleset.moves import get_moves
from straightjacket.engine.ruleset.outcome_result import move_outcome_config
from straightjacket.engine.setting.packages import list_packages
from straightjacket.web.serializers import build_narrative_status
from tests._helpers import make_game_state


def _game() -> GameState:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    g.resources = Resources(meters={"health": 3, "spirit": 3, "supply": 3, "momentum": 5}, next_move_bonus=0)
    return g


class TestApplyImpact:
    @staticmethod
    def test_apply_new_impact() -> None:
        game = _game()
        assert apply_impact(game, "wounded") is True
        assert "wounded" in game.impacts

    @staticmethod
    def test_apply_duplicate_returns_false() -> None:
        game = _game()
        apply_impact(game, "wounded")
        assert apply_impact(game, "wounded") is False
        assert game.impacts.count("wounded") == 1

    @staticmethod
    def test_apply_unknown_impact_raises() -> None:
        game = _game()
        with pytest.raises(KeyError, match="nonexistent_impact"):
            apply_impact(game, "nonexistent_impact")
        assert "nonexistent_impact" not in game.impacts


class TestImpactsFromTheRules:
    @staticmethod
    def test_each_ruleset_names_its_own_impacts() -> None:
        assert "maimed" in get_impacts("classic")
        assert "permanently_harmed" not in get_impacts("classic")
        assert "permanently_harmed" in get_impacts("starforged")
        assert get_impacts("delve") == get_impacts("classic")
        assert get_impacts("sundered_isles") == get_impacts("starforged")
        assert get_impacts("starforged")["wounded"].prevents_recovery == ["health"]
        assert get_impacts("starforged")["traumatized"].permanent

    @staticmethod
    def test_an_impact_another_ruleset_has_is_refused() -> None:
        game = _game()
        game.setting_id = "classic"
        with pytest.raises(KeyError, match="permanently_harmed"):
            apply_impact(game, "permanently_harmed")

    @staticmethod
    def test_every_impact_a_move_marks_is_its_rulesets_own() -> None:
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
    @staticmethod
    def test_clear_active_impact() -> None:
        game = _game()
        apply_impact(game, "wounded")
        assert clear_impact(game, "wounded") is True
        assert "wounded" not in game.impacts

    @staticmethod
    def test_clear_inactive_impact_returns_false() -> None:
        game = _game()
        assert clear_impact(game, "wounded") is False

    @staticmethod
    def test_cannot_clear_permanent_impact() -> None:
        game = _game()
        apply_impact(game, "permanently_harmed")
        assert clear_impact(game, "permanently_harmed") is False
        assert "permanently_harmed" in game.impacts


class TestMaxMomentum:
    @staticmethod
    def test_no_impacts_keeps_base_max() -> None:
        assert max_momentum(_game()) == 10

    @staticmethod
    def test_each_impact_reduces_max_by_one() -> None:
        game = _game()
        apply_impact(game, "wounded")
        assert max_momentum(game) == 9
        apply_impact(game, "shaken")
        assert max_momentum(game) == 8

    @staticmethod
    def test_momentum_gained_stops_at_the_lowered_max() -> None:
        game = _game()
        apply_impact(game, "wounded")
        game.resources.meters["momentum"] = 8
        adjust_momentum(game, 2)
        assert game.resources.meters["momentum"] == 9

    @staticmethod
    def test_momentum_clamped_to_new_max() -> None:
        game = _game()
        game.resources.meters["momentum"] = 10
        apply_impact(game, "wounded")
        assert game.resources.meters["momentum"] == 9

    @staticmethod
    def test_clear_restores_momentum_max() -> None:
        game = _game()
        apply_impact(game, "wounded")
        apply_impact(game, "shaken")
        clear_impact(game, "wounded")
        assert max_momentum(game) == 9


class TestBlocksRecovery:
    @staticmethod
    def test_wounded_blocks_health_recovery() -> None:
        game = _game()
        apply_impact(game, "wounded")
        assert blocks_recovery(game, "health") == "wounded"

    @staticmethod
    def test_shaken_blocks_spirit_recovery() -> None:
        game = _game()
        apply_impact(game, "shaken")
        assert blocks_recovery(game, "spirit") == "shaken"

    @staticmethod
    def test_unprepared_blocks_supply_recovery() -> None:
        game = _game()
        apply_impact(game, "unprepared")
        assert blocks_recovery(game, "supply") == "unprepared"

    @staticmethod
    def test_no_impact_no_block() -> None:
        game = _game()
        assert not blocks_recovery(game, "health")

    @staticmethod
    def test_doomed_does_not_block_recovery() -> None:
        game = _game()
        apply_impact(game, "doomed")
        assert not blocks_recovery(game, "health")


class TestImpactsSnapshotRestore:
    @staticmethod
    def test_impacts_restored() -> None:
        game = _game()
        apply_impact(game, "wounded")
        snap = game.snapshot()

        apply_impact(game, "shaken")
        assert len(game.impacts) == 2

        game.restore(snap)
        assert game.impacts == ["wounded"]
        assert max_momentum(game) == 9

    @staticmethod
    def test_impacts_round_trip() -> None:
        game = _game()
        apply_impact(game, "doomed")
        apply_impact(game, "tormented")

        d = game.to_dict()
        game2 = GameState.from_dict(d)
        assert sorted(game2.impacts) == ["doomed", "tormented"]


class TestRecoveryHandlerClearsImpact:
    @staticmethod
    @pytest.mark.parametrize(
        ("marked", "cleared", "spirit"),
        [("shaken", True, 3), ("wounded", False, 4)],
    )
    def test_the_impact_a_recovery_clears_is_the_one_its_rules_say_blocks_its_meter(
        marked: str, *, cleared: bool, spirit: int
    ) -> None:
        game = _game()
        game.resources.meters["spirit"] = 2
        apply_impact(game, marked)
        resolve_move_outcome(game, "recover/hearten", "STRONG_HIT", target_npc_id=None, aided_by=None, match=False)
        assert (marked not in game.impacts) is cleared
        assert game.resources.meters["spirit"] == spirit

    @staticmethod
    @pytest.mark.parametrize("wounded", [True, False])
    def test_heal_clears_wounded_and_says_so_only_when_it_was_marked(*, wounded: bool) -> None:
        game = _game()
        if wounded:
            apply_impact(game, "wounded")
        result = resolve_move_outcome(
            game, "recover/heal", "STRONG_HIT", target_npc_id=None, aided_by=None, match=False
        )
        assert not game.impacts
        assert any("wounded" in c for c in labels_of(result.consequences)) is wounded


class TestImpactsStatus:
    @staticmethod
    def test_impacts_shown_in_status() -> None:
        game = _game()
        game.setting_id = "starforged"
        game.world.time_of_day = "evening"
        apply_impact(game, "wounded")
        apply_impact(game, "doomed")
        text = build_narrative_status(game)
        assert "wounded" in text
        assert "doomed" in text

    @staticmethod
    def test_no_impacts_no_line() -> None:
        game = _game()
        game.world.time_of_day = "evening"
        text = build_narrative_status(game)
        assert "Impacts:" not in text


class TestCharacterStatePromptTag:
    @staticmethod
    def test_no_impacts_no_tag() -> None:
        assert "character_state" not in build_new_game_prompt(_game())

    @staticmethod
    def test_impacts_in_character_state() -> None:
        game = _game()
        game.world.time_of_day = "evening"
        apply_impact(game, "wounded")
        apply_impact(game, "doomed")
        header = build_new_game_prompt(game)
        assert '<character_state impacts="wounded, doomed">' in header
        assert (
            '<impact name="wounded">Wounded may be marked when you are at 0 health and fail to Endure Harm.' in header
        )
        assert "Doomed is marked when you Face Death" in header
        assert "](" not in header
