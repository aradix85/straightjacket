import pytest

from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.meters import (
    condition_meters,
    gain,
    in_crisis,
    lose,
    max_momentum,
    starting_resources,
)
from tests._helpers import make_game_state


def test_condition_meters_come_from_each_rulesets_datasworn_rules(load_engine: None) -> None:
    for setting_id in ("classic", "starforged"):
        meters = condition_meters(setting_id)
        assert list(meters) == ["health", "spirit", "supply"]
        assert all((m.min, m.max, m.start) == (0, 5, 5) for m in meters.values())
    assert condition_meters("delve") == condition_meters("classic")
    assert condition_meters("sundered_isles") == condition_meters("starforged")


def test_a_new_character_starts_with_the_rulesets_meters_and_momentum(load_engine: None) -> None:
    resources = starting_resources("sundered_isles")
    assert resources.meters == {"health": 5, "spirit": 5, "supply": 5, "momentum": rules().momentum.start}
    assert resources.next_move_bonus == 0


def test_a_condition_meter_stays_within_its_range(load_engine: None) -> None:
    game = make_game_state(setting_id="classic")
    game.resources.meters["supply"] = 1
    assert lose(game, "supply", 3) == 1
    assert game.resources.meters["supply"] == 0
    assert gain(game, "supply", 9) == 5
    assert game.resources.meters["supply"] == 5


def test_a_meter_the_ruleset_lacks_is_refused(load_engine: None) -> None:
    with pytest.raises(KeyError, match="integrity"):
        lose(make_game_state(), "integrity", 1)


@pytest.mark.parametrize(("health", "spirit", "crisis"), [(5, 5, False), (0, 5, True), (5, 0, True), (1, 1, False)])
def test_crisis_follows_the_meters_the_ruleset_names(load_engine: None, health: int, spirit: int, crisis: bool) -> None:
    game = make_game_state()
    game.resources.meters.update(health=health, spirit=spirit, supply=0)
    assert in_crisis(game) is crisis


def test_max_momentum_never_drops_below_zero(load_engine: None) -> None:
    game = make_game_state(impacts=["wounded"] * (rules().momentum.max + 2))
    assert max_momentum(game) == 0
