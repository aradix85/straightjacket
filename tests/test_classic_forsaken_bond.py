from typing import Any

import pytest

from straightjacket.engine.models import GameState, ProgressTrack, labels_of
from tests._creation import TurnProvider, brain_answer, create_game, fixed_roll, force_result, library_game

VOW = "Find the lost page"
TESTED = f'Mira: the bond is tested, since the vow "{VOW}" made to them was forsaken'


def _bonded_library(monkeypatch: pytest.MonkeyPatch) -> GameState:
    from straightjacket.engine.ruleset.bond import seal_bond

    game = library_game()
    seal_bond(game, game.npcs[0])
    force_result(monkeypatch, "STRONG_HIT")
    return game


def _swear(game: GameState, bonus_id: str | None) -> ProgressTrack:
    from straightjacket.engine.game import process_turn

    brain = brain_answer(
        move="quest/swear_an_iron_vow",
        stat="heart",
        bonus_id=bonus_id,
        track_name=VOW,
        track_rank="dangerous",
        player_intent="I swear to Mira to find the lost page",
        location_change=None,
    )
    process_turn(TurnProvider(brain), game, "I swear to Mira to find the lost page", None)
    return next(t for t in game.progress_tracks if t.name == VOW)


def _forsake(game: GameState, vow: ProgressTrack) -> None:
    from straightjacket.engine.game import process_turn
    from tests._helpers import make_threat

    threat = make_threat(id="threat_thief", name="The ink thief", linked_vow_id=vow.id)
    threat.menace_ticks = threat.max_menace_ticks
    game.threats.append(threat)
    brain = brain_answer(move="dialog", target_npc=None, player_intent="I wait", location_change=None)
    process_turn(TurnProvider(brain), game, "I wait", None)
    assert vow.status == "failed"


def _meet_mira(
    game: GameState, monkeypatch: pytest.MonkeyPatch, result: str, **brain_changes: Any
) -> tuple[list[str], str]:
    from straightjacket.engine.game import process_turn
    from straightjacket.engine.ruleset import move_outcome

    monkeypatch.setattr(move_outcome, "roll_action", fixed_roll(result))
    brain = brain_answer(
        **{
            "move": "dialog",
            "stat": "heart",
            "target_npc": "npc_1",
            "player_intent": "I talk with Mira",
            "location_change": None,
            **brain_changes,
        }
    )
    provider = TurnProvider(brain)
    process_turn(provider, game, "I talk with Mira", None)
    return labels_of(game.narrative.session_log[-1].consequences), provider.prompts[-1]


def test_a_vow_sworn_with_a_bonds_aid_tests_the_bond_once_when_they_next_meet(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = _bonded_library(monkeypatch)
    vow = _swear(game, "connection:npc_1")
    assert vow.vowed_to == "npc_1"
    _forsake(game, vow)
    labels, prompt = _meet_mira(game, monkeypatch, "WEAK_HIT")
    assert labels == [TESTED, "follow-up move Test Your Bond: WEAK_HIT", "loyalty_test"]
    assert "loyalty_test" not in prompt
    assert vow.vowed_to is None
    assert TESTED not in _meet_mira(game, monkeypatch, "WEAK_HIT")[0]


def test_a_missed_test_after_a_forsaken_vow_clears_the_bond(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.gamemaster.questions import answers

    game = _bonded_library(monkeypatch)
    _forsake(game, _swear(game, "connection:npc_1"))
    labels, _prompt = _meet_mira(game, monkeypatch, "MISS")
    assert labels[:3] == [TESTED, "follow-up move Test Your Bond: MISS", "Mira: bond cleared"]
    assert answers().closeness(game, "npc_1") == 0


def test_a_vow_sworn_without_a_bonds_aid_asks_no_test(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    game = _bonded_library(monkeypatch)
    vow = _swear(game, None)
    assert vow.vowed_to is None
    _forsake(game, vow)
    assert TESTED not in _meet_mira(game, monkeypatch, "WEAK_HIT")[0]


def test_the_players_own_test_of_the_bond_is_the_test_the_vow_asks(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = _bonded_library(monkeypatch)
    vow = _swear(game, "connection:npc_1")
    _forsake(game, vow)
    labels, _prompt = _meet_mira(game, monkeypatch, "WEAK_HIT", move="relationship/test_your_bond")
    assert TESTED not in labels
    assert vow.vowed_to is None


def test_an_action_aimed_at_them_tests_the_bond_too(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    game = _bonded_library(monkeypatch)
    _forsake(game, _swear(game, "connection:npc_1"))
    labels, _prompt = _meet_mira(game, monkeypatch, "STRONG_HIT", move="adventure/face_danger", stat="wits")
    tested = labels.index(TESTED)
    assert labels[tested + 1] == "follow-up move Test Your Bond: STRONG_HIT"


def test_a_test_of_the_bond_the_brain_names_but_plays_as_dialog_still_tests_it(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = _bonded_library(monkeypatch)
    _forsake(game, _swear(game, "connection:npc_1"))
    labels, _prompt = _meet_mira(game, monkeypatch, "WEAK_HIT", move="relationship/test_your_bond", dialog_only=True)
    assert TESTED in labels


def test_a_bond_gone_before_they_meet_asks_no_test(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome

    game = _bonded_library(monkeypatch)
    vow = _swear(game, "connection:npc_1")
    _forsake(game, vow)
    resolve_move_outcome(game, "relationship/test_your_bond", "MISS", target_npc_id="npc_1", aided_by=None, match=False)
    assert TESTED not in _meet_mira(game, monkeypatch, "WEAK_HIT")[0]
    assert vow.vowed_to is None


def test_the_vow_follows_the_person_when_two_npcs_turn_out_to_be_one(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.gamemaster.npc.lifecycle import absorb_npc
    from straightjacket.engine.ruleset.bond import connection_track
    from tests._helpers import make_npc

    game = _bonded_library(monkeypatch)
    vow = _swear(game, "connection:npc_1")
    mira, archivist = game.npcs[0], make_npc(id="npc_2", name="The archivist", status="active")
    game.npcs.append(archivist)
    absorb_npc(game, archivist, mira)
    assert vow.vowed_to == "npc_2"
    assert connection_track(game, "npc_2") is not None


def test_starforged_asks_no_bond_test_for_a_forsaken_vow(load_engine: None) -> None:
    from straightjacket.engine.ruleset.bond import seal_bond
    from straightjacket.engine.ruleset.move_outcome import make_due_bond_test
    from straightjacket.engine.ruleset.outcome_result import new_outcome

    game = create_game(
        "starforged",
        location="Hearthwood",
        npcs=[("Kira", "A hunter.", "friendly")],
        stats=(2, 2, 1, 1, 3),
        player_name="Aria",
        background_vow="avenge sister",
    )
    seal_bond(game, game.npcs[0])
    vow = game.progress_tracks[0]
    vow.vowed_to = game.npcs[0].id
    _forsake(game, vow)
    outcome = new_outcome()
    make_due_bond_test(game, game.npcs[0].id, "dialog", outcome)
    assert (outcome.consequences, vow.vowed_to) == ([], None)
