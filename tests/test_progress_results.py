import dataclasses

import pytest

from straightjacket.engine.datasworn.moves import get_moves
from straightjacket.engine.game.action_resolution import resolve_action_phase
from straightjacket.engine.game.turn_types import RollOutcome
from straightjacket.engine.mechanics.consequences import downgrade_in_position, generate_consequence_sentences
from straightjacket.engine.mechanics.legacy import get_legacy_track
from straightjacket.engine.mechanics.outcome_result import OutcomeResult
from straightjacket.engine.mechanics.tracks import recommit_track
from straightjacket.engine.models import GameState, ProgressTrack, RollResult, labels_of
from tests._helpers import fix_dice, make_brain_result, make_game_state, make_progress_track


def _roll(move: str, result: str, match: bool = False) -> RollResult:
    return RollResult(
        d1=0,
        c1=5,
        c2=5 if match else 6,
        stat_name="t",
        stat_value=6,
        action_score=6,
        result=result,
        move=move,
        match=match,
    )


def _play(setting_id: str, move: str, track: ProgressTrack, result: str) -> tuple[GameState, list[str]]:
    game = make_game_state(player_name="Hero", setting_id=setting_id)
    game.progress_tracks.append(track)
    if track.track_type == "combat":
        game.world.combat_position = "in_control"
    brain = make_brain_result(move=move, stat="none", target_track=track.id)
    outcome = RollOutcome(roll=_roll(move, result), ds_move=get_moves(setting_id)[move], track=track)
    resolution = resolve_action_phase(game, brain, outcome)
    return game, resolution.consequences


PROGRESS_MOVES = [
    ("classic", "quest/fulfill_your_vow", "vow", "completed"),
    ("classic", "adventure/reach_your_destination", "journey", "completed"),
    ("classic", "combat/end_the_fight", "combat", "completed"),
    ("starforged", "quest/fulfill_your_vow", "vow", "completed"),
    ("starforged", "connection/forge_a_bond", "connection", "bonded"),
    ("starforged", "exploration/finish_an_expedition", "expedition", "completed"),
    ("starforged", "combat/take_decisive_action", "combat", "completed"),
]


@pytest.mark.parametrize(("setting_id", "move", "track_type", "status"), PROGRESS_MOVES)
def test_a_weak_hit_on_a_progress_move_completes_its_track_or_bonds_a_connection(
    load_engine: None, setting_id: str, move: str, track_type: str, status: str
) -> None:
    track = make_progress_track(id=f"{track_type}_x", track_type=track_type, ticks=24)
    game, _ = _play(setting_id, move, track, "WEAK_HIT")
    assert track.status == status
    if track_type == "combat":
        assert game.world.combat_position == ""


@pytest.mark.parametrize(
    ("setting_id", "move", "track_type", "ticks_after"),
    [
        ("classic", "quest/fulfill_your_vow", "vow", 4),
        ("classic", "adventure/reach_your_destination", "journey", 4),
        ("starforged", "quest/fulfill_your_vow", "vow", 12),
        ("starforged", "connection/forge_a_bond", "connection", 12),
        ("starforged", "exploration/finish_an_expedition", "expedition", 12),
    ],
)
def test_a_miss_recommits_with_less_progress_and_a_higher_rank(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, setting_id: str, move: str, track_type: str, ticks_after: int
) -> None:
    track = make_progress_track(id=f"{track_type}_x", name="The Long Road", track_type=track_type, ticks=24)
    fix_dice(monkeypatch, 3, 8)
    game, consequences = _play(setting_id, move, track, "MISS")
    assert (track.status, track.ticks, track.rank) == ("active", ticks_after, "formidable")
    assert "recommit The Long Road" in labels_of(consequences)
    sentences = generate_consequence_sentences(consequences, [], game, make_brain_result(move=move))
    assert any("Hero" in s and "The Long Road" in s for s in sentences)


@pytest.mark.parametrize(
    ("setting_id", "move"), [("classic", "combat/end_the_fight"), ("starforged", "combat/take_decisive_action")]
)
def test_a_miss_loses_the_fight(load_engine: None, setting_id: str, move: str) -> None:
    track = make_progress_track(id="combat_x", track_type="combat", ticks=24)
    _play(setting_id, move, track, "MISS")
    assert track.status == "failed"


def test_an_epic_track_stays_epic_when_recommitted(load_engine: None) -> None:
    track = make_progress_track(rank="epic", ticks=9)
    recommit_track(track, "keep_one_box", OutcomeResult())
    assert (track.rank, track.ticks) == ("epic", 4)


def test_keeping_one_box_keeps_less_when_less_is_filled(load_engine: None) -> None:
    track = make_progress_track(ticks=3)
    recommit_track(track, "keep_one_box", OutcomeResult())
    assert track.ticks == 3


def test_clearing_by_the_lowest_die_stops_at_zero(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    track = make_progress_track(ticks=6)
    fix_dice(monkeypatch, 9, 7)
    recommit_track(track, "clear_lowest_die", OutcomeResult())
    assert track.ticks == 0


def test_finish_an_expedition_weak_hit_rewards_one_rank_lower(load_engine: None) -> None:
    track = make_progress_track(id="expedition_x", track_type="expedition", rank="formidable", ticks=24)
    game, _ = _play("starforged", "exploration/finish_an_expedition", track, "WEAK_HIT")
    assert get_legacy_track(game, "discoveries").ticks == 2


def test_forge_a_bond_weak_hit_bonds_now_and_tells_the_request(load_engine: None) -> None:
    track = make_progress_track(id="connection_npc_1", track_type="connection", ticks=24)
    game, consequences = _play("starforged", "connection/forge_a_bond", track, "WEAK_HIT")
    assert track.status == "bonded"
    assert get_legacy_track(game, "bonds").ticks == 2
    sentences = generate_consequence_sentences(
        consequences, [], game, make_brain_result(move="connection/forge_a_bond")
    )
    assert any("ask something more of Hero" in s or "Hero has yet to do" in s for s in sentences)


def test_a_bonded_connection_keeps_its_bond_and_is_not_made_again(load_engine: None) -> None:
    from straightjacket.engine.mechanics.tracks import start_track
    from straightjacket.engine.npc.bond import get_npc_bond

    track = make_progress_track(id="connection_npc_1", name="Mira", track_type="connection", ticks=24)
    game, _ = _play("starforged", "connection/forge_a_bond", track, "STRONG_HIT")
    assert get_npc_bond(game, "npc_1") == track.filled_boxes == 6
    again = make_brain_result(
        move="connection/make_a_connection", target_npc="npc_1", track_name="Mira", track_rank="dangerous"
    )
    start_track(game, again, "STRONG_HIT")
    assert [t.id for t in game.progress_tracks] == ["connection_npc_1"]


@pytest.mark.parametrize(
    ("position", "result", "match", "counted"),
    [
        ("bad_spot", "WEAK_HIT", False, "MISS"),
        ("bad_spot", "STRONG_HIT", False, "WEAK_HIT"),
        ("bad_spot", "STRONG_HIT", True, "STRONG_HIT"),
        ("bad_spot", "MISS", False, "MISS"),
        ("in_control", "WEAK_HIT", False, "WEAK_HIT"),
    ],
)
def test_take_decisive_action_in_a_bad_spot_counts_lower(
    load_engine: None, position: str, result: str, match: bool, counted: str
) -> None:
    game = make_game_state(setting_id="starforged")
    game.world.combat_position = position
    roll = _roll("combat/take_decisive_action", result, match)
    assert downgrade_in_position(game, roll) == dataclasses.replace(roll, result=counted)


def test_other_progress_moves_ignore_the_position(load_engine: None) -> None:
    game = make_game_state(setting_id="classic")
    game.world.combat_position = "bad_spot"
    roll = _roll("combat/end_the_fight", "WEAK_HIT")
    assert downgrade_in_position(game, roll) is roll
