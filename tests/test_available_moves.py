import pytest

from straightjacket.engine.models import GameState, Resources
from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.config_types import ActiveTrackCondition
from straightjacket.engine.ruleset.moves import get_moves
from straightjacket.engine.tools import available_moves
from tests._helpers import make_game_state, make_progress_track


def _game(setting: str = "starforged") -> GameState:
    g = make_game_state(player_name="Hero", setting_id=setting)
    g.resources = Resources(health=5, spirit=5, supply=5, momentum=2, max_momentum=10)
    return g


def _in_fight(game: GameState, position: str) -> GameState:
    game.progress_tracks.append(make_progress_track(id="c1", name="Fight", track_type="combat", ticks=12))
    game.world.combat_position = position
    return game


def _moves(game: GameState) -> set[str]:
    return set(available_moves(game))


class TestAvailableMoves:
    def test_no_combat_has_adventure_moves(self, load_engine: None) -> None:
        moves = _moves(_game())
        assert {"adventure/face_danger", "adventure/secure_an_advantage", "adventure/gather_information"} <= moves

    def test_no_combat_has_enter_the_fray(self, load_engine: None) -> None:
        assert {"combat/enter_the_fray", "combat/battle"} <= _moves(_game())

    def test_no_combat_excludes_combat_moves(self, load_engine: None) -> None:
        moves = _moves(_game())
        assert not {"combat/strike", "combat/clash", "combat/gain_ground", "combat/react_under_fire"} & moves
        assert "combat/take_decisive_action" not in moves

    def test_in_control_has_strike_and_gain_ground(self, load_engine: None) -> None:
        moves = _moves(_in_fight(_game(), "in_control"))
        assert {"combat/strike", "combat/gain_ground", "combat/take_decisive_action"} <= moves
        assert not {"combat/clash", "combat/react_under_fire"} & moves

    def test_bad_spot_has_clash_and_react(self, load_engine: None) -> None:
        moves = _moves(_in_fight(_game(), "bad_spot"))
        assert {"combat/clash", "combat/react_under_fire", "combat/take_decisive_action"} <= moves
        assert not {"combat/strike", "combat/gain_ground"} & moves

    def test_a_fight_excludes_entering_another(self, load_engine: None) -> None:
        moves = _moves(_in_fight(_game(), "in_control"))
        assert not {"combat/enter_the_fray", "combat/battle"} & moves

    def test_a_combat_position_without_a_fight_track_offers_no_fight_move(self, load_engine: None) -> None:
        game = _game()
        game.world.combat_position = "in_control"
        moves = _moves(game)
        assert not {"combat/strike", "combat/gain_ground", "combat/take_decisive_action"} & moves
        assert "combat/enter_the_fray" in moves

    def test_no_vow_excludes_fulfill(self, load_engine: None) -> None:
        moves = _moves(_game())
        assert "quest/fulfill_your_vow" not in moves
        assert "quest/swear_an_iron_vow" in moves

    def test_with_vow_includes_fulfill(self, load_engine: None) -> None:
        game = _game()
        game.progress_tracks.append(make_progress_track(id="v1", name="Test Vow", track_type="vow", ticks=20))
        assert "quest/fulfill_your_vow" in _moves(game)

    def test_suffer_moves_excluded(self, load_engine: None) -> None:
        moves = _moves(_game())
        assert "suffer/endure_harm" not in moves
        assert "threshold/face_death" not in moves

    def test_recovery_moves_available(self, load_engine: None) -> None:
        assert {"recover/heal", "recover/resupply"} <= _moves(_game())

    def test_engine_specific_moves_present(self, load_engine: None) -> None:
        assert {"dialog", "ask_the_oracle", "world_shaping"} <= _moves(_game())

    def test_offers_the_settings_own_moves_and_the_engines(self, load_engine: None) -> None:
        offered = available_moves(_game())
        assert offered["adventure/face_danger"] is get_moves("starforged")["adventure/face_danger"]
        assert offered["dialog"] is rules().engine_moves["dialog"]

    def test_classic_setting(self, load_engine: None) -> None:
        moves = _moves(_game(setting="classic"))
        assert {"adventure/face_danger", "adventure/undertake_a_journey", "relationship/compel"} <= moves

    def test_reaching_a_destination_needs_a_journey(self, load_engine: None) -> None:
        game = _game(setting="classic")
        assert "adventure/reach_your_destination" not in _moves(game)
        game.progress_tracks.append(make_progress_track(id="j1", name="To the ridge", track_type="journey"))
        assert "adventure/reach_your_destination" in _moves(game)

    def test_delve_site_moves_wait_for_a_site(self, load_engine: None) -> None:
        moves = _moves(_game(setting="delve"))
        assert not {"delve/delve_the_depths", "delve/locate_your_objective"} & moves


@pytest.mark.parametrize("setting", ["classic", "delve", "starforged", "sundered_isles"])
def test_every_offered_progress_move_has_its_track(load_engine: None, setting: str) -> None:
    track_types = rules().get_raw("track_types_by_category")
    marking = rules().get_raw("progress_mark_categories")
    creating = rules().get_raw("track_creating_moves")
    ds_moves = get_moves(setting)
    for key, move in ds_moves.items():
        if move.roll_type == "progress_roll":
            category = move.track_category
        elif key in marking and key not in creating:
            category = marking[key]
        else:
            continue
        rule = rules().move_availability[key]
        required = {c.active_track for c in rule.available if isinstance(c, ActiveTrackCondition)}
        assert rule.never or track_types[category] in required, f"{setting}: {key} is offered without its track"
