from __future__ import annotations

import pytest

from tests._helpers import make_brain_result, make_game_state, make_progress_track


def _game_with(*assets: str) -> object:
    game = make_game_state(setting_id="starforged")
    game.assets = list(assets)
    return game


def test_an_enabled_ability_with_an_add_becomes_an_option(load_engine: None) -> None:
    from straightjacket.engine.mechanics.bonuses import roll_bonuses

    options = {o.id: o for o in roll_bonuses(_game_with("companion/combat_bot"))}
    assert options["companion/combat_bot#0"].add == 1


def test_a_disabled_ability_is_offered_only_after_an_upgrade(load_engine: None) -> None:
    from straightjacket.engine.mechanics.assets import enable_next_ability
    from straightjacket.engine.mechanics.bonuses import roll_bonuses

    game = _game_with("companion/banshee")
    assert "companion/banshee#1" not in {o.id for o in roll_bonuses(game)}
    assert enable_next_ability(game, "companion/banshee")
    option = next(o for o in roll_bonuses(game) if o.id == "companion/banshee#1")
    assert (option.add, option.momentum_on_hit) == (1, 1)


def test_a_connection_offers_its_aid(load_engine: None) -> None:
    from straightjacket.engine.mechanics.bonuses import roll_bonuses

    game = _game_with()
    game.progress_tracks.append(
        make_progress_track(id="connection_npc_1", name="Mira", track_type="connection", rank="dangerous", ticks=0)
    )
    option = next(o for o in roll_bonuses(game) if o.id == "connection:npc_1")
    assert (option.add, option.momentum_on_hit) == (1, 1)


def test_an_unknown_choice_is_ignored(load_engine: None) -> None:
    from straightjacket.engine.mechanics.bonuses import chosen_bonus

    assert chosen_bonus(_game_with("companion/combat_bot"), "companion/combat_bot#7") is None


@pytest.mark.parametrize(("dice", "momentum_after"), [([3, 9, 9], 2), ([6, 1, 1], 3)])
def test_a_chosen_bonus_adds_to_the_roll_and_momentum_on_a_hit(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, dice: list[int], momentum_after: int
) -> None:
    from straightjacket.engine.game.turn import _execute_roll
    from straightjacket.engine.mechanics import consequences

    game = _game_with()
    game.progress_tracks.append(
        make_progress_track(id="connection_npc_1", name="Mira", track_type="connection", rank="dangerous", ticks=0)
    )
    game.resources.momentum = 2
    sequence = list(dice)
    monkeypatch.setattr(consequences.random, "randint", lambda low, high: sequence.pop(0))
    brain = make_brain_result(move="adventure/face_danger", stat="wits")
    brain.bonus_id = "connection:npc_1"
    outcome = _execute_roll(game, brain)
    assert outcome.roll.action_score == min(dice[0] + game.get_stat("wits") + 1, 10)
    assert game.resources.momentum == momentum_after


def test_saves_without_ability_states_still_load(load_engine: None) -> None:
    from straightjacket.engine.models import GameState

    data = make_game_state(setting_id="starforged").to_dict()
    data.pop("asset_abilities")
    assert GameState.from_dict(data).asset_abilities == {}


def test_momentum_tied_to_another_move_is_not_granted_with_the_add(load_engine: None) -> None:
    from straightjacket.engine.mechanics.bonuses import roll_bonuses

    option = next(o for o in roll_bonuses(_game_with("companion/combat_bot")) if o.id == "companion/combat_bot#0")
    assert (option.add, option.momentum_on_hit) == (1, 0)
