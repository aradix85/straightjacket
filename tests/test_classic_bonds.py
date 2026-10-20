import pytest

from straightjacket.engine.models import GameState, labels_of
from tests._creation import TurnProvider, brain_answer, force_result, library_game


def _forge_a_bond(monkeypatch: pytest.MonkeyPatch, result: str) -> tuple[GameState, list[str]]:
    from straightjacket.engine.game import process_turn

    game = library_game()
    game.resources.meters["spirit"] = 3
    force_result(monkeypatch, result)
    brain = brain_answer(
        move="relationship/forge_a_bond",
        stat="heart",
        target_npc="npc_1",
        player_intent="I stand with Mira through the night",
        location_change=None,
    )
    process_turn(TurnProvider(brain), game, "I stand with Mira through the night", None)
    return game, labels_of(game.narrative.session_log[-1].consequences)


@pytest.mark.parametrize(("result", "own"), [("STRONG_HIT", "spirit +1"), ("WEAK_HIT", "bond_request")])
def test_a_hit_on_classic_forge_a_bond_seals_the_bond_at_full_closeness(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, result: str, own: str
) -> None:
    from straightjacket.engine.gamemaster.questions import answers
    from straightjacket.engine.ruleset.bond import connection_track

    game, labels = _forge_a_bond(monkeypatch, result)
    track = connection_track(game, "npc_1")
    assert track is not None
    assert (track.status, track.ticks, track.name) == ("bonded", track.max_ticks, "Mira")
    assert answers().closeness(game, "npc_1") == 10
    assert game.campaign.legacy["bonds"].ticks == 1
    assert labels == ["Mira: bond sealed", "legacy reward (bonds)", own]


def test_a_miss_on_classic_forge_a_bond_leaves_no_bond(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.gamemaster.questions import answers

    game, labels = _forge_a_bond(monkeypatch, "MISS")
    assert answers().closeness(game, "npc_1") == 0
    assert game.campaign.legacy["bonds"].ticks == 0
    assert "Mira: bond sealed" not in labels


def test_a_classic_bond_aids_by_classics_rule(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.ruleset.bonuses import roll_bonuses

    game, _labels = _forge_a_bond(monkeypatch, "STRONG_HIT")
    option = next(o for o in roll_bonuses(game) if o.id == "connection:npc_1")
    assert (option.add, option.momentum_on_hit) == (1, 0)
    assert option.condition.startswith("You share a bond with Mira")
