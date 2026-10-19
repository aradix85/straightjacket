from straightjacket.engine.models import labels_of
import pytest

from straightjacket.engine.datasworn.settings import load_package
from straightjacket.engine.engine_loader import eng
from straightjacket.engine.game.finalization import update_crisis
from straightjacket.engine.datasworn.oracle_rolls import plain_text
from straightjacket.engine.mechanics.move_effects import apply_effects, parse_effects
from straightjacket.engine.mechanics.move_handlers import _TABLE_TRIGGERS
from straightjacket.engine.mechanics.move_outcome import make_follow_up_moves, resolve_move_outcome
from straightjacket.engine.mechanics.outcome_result import OutcomeResult
from straightjacket.engine.mechanics.suffer import start_dying_clock, suffer, tick_dying_clock
from straightjacket.engine.mechanics.tracks import complete_track
from straightjacket.engine.models import GameState, Resources
from tests._helpers import fix_dice, make_game_state, make_progress_track

MISS = (1, 10, 10)
WEAK_HIT = (6, 1, 10)
STRONG_HIT = (6, 1, 1)


def _game(setting_id: str, health: int = 5, spirit: int = 5, supply: int = 5) -> GameState:
    game = make_game_state(player_name="Hero", setting_id=setting_id)
    game.resources = Resources(health=health, spirit=spirit, supply=supply, momentum=2, max_momentum=10)
    return game


def _dying(game: GameState) -> list[str]:
    return [c.name for c in game.world.clocks if c.clock_type == eng().suffer.dying_clock.clock_type]


def test_harm_above_zero_in_starforged_is_taken_without_endure_harm(load_engine: None) -> None:
    game = _game("starforged", health=3)
    result = OutcomeResult()
    suffer(game, "health", 1, result)
    assert game.resources.health == 2
    assert (labels_of(result.consequences), result.follow_up_moves) == (["health -1"], [])


def test_harm_past_zero_costs_momentum_and_is_endured(load_engine: None) -> None:
    game = _game("starforged", health=1)
    result = OutcomeResult()
    suffer(game, "health", 2, result)
    assert (game.resources.health, game.resources.momentum) == (0, 1)
    assert labels_of(result.consequences) == ["health -1", "momentum -1"]
    assert result.follow_up_moves == ["suffer/endure_harm"]


@pytest.mark.parametrize(("meter", "move"), [("health", "suffer/endure_harm"), ("spirit", "suffer/endure_stress")])
def test_classic_endures_every_harm_and_stress(load_engine: None, meter: str, move: str) -> None:
    game = _game("classic")
    result = OutcomeResult()
    suffer(game, meter, 1, result)
    assert result.follow_up_moves == [move]


def test_pay_the_price_harm_goes_through_endure_harm(load_engine: None) -> None:
    game = _game("classic")
    result = apply_effects(game, parse_effects(["health -1"]))
    assert result.follow_up_moves == ["suffer/endure_harm"]


def test_exhausted_supply_marks_unprepared_and_further_loss_costs_momentum(load_engine: None) -> None:
    game = _game("starforged", supply=1)
    result = OutcomeResult()
    suffer(game, "supply", 1, result)
    suffer(game, "supply", 1, result)
    assert game.impacts == ["unprepared"]
    assert labels_of(result.consequences) == ["supply -1", "mark unprepared", "momentum -1"]
    assert (game.resources.momentum, result.follow_up_moves) == (1, [])


def test_a_miss_at_zero_marks_the_first_free_impact(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    game = _game("starforged", health=0)
    result = OutcomeResult(follow_up_moves=["suffer/endure_harm"])
    fix_dice(monkeypatch, *MISS)
    make_follow_up_moves(game, result)
    assert game.impacts == ["wounded"]
    assert labels_of(result.consequences) == ["follow-up move Endure Harm: MISS", "momentum -2", "mark wounded"]


def test_with_both_impacts_marked_mortal_harm_faces_death(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    game = _game("starforged", health=0)
    game.impacts = ["wounded", "permanently_harmed"]
    result = OutcomeResult(follow_up_moves=["suffer/endure_harm"])
    fix_dice(monkeypatch, *MISS, 5, *MISS)
    make_follow_up_moves(game, result)
    assert game.game_over
    assert labels_of(result.consequences)[-2:] == ["follow-up move Face Death: MISS", "you are dead"]


def test_face_death_on_a_weak_hit_returns_bound_to_an_extreme_vow(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = _game("starforged", health=0)
    result = OutcomeResult(follow_up_moves=["threshold/face_death"])
    fix_dice(monkeypatch, *WEAK_HIT, *STRONG_HIT)
    make_follow_up_moves(game, result)
    [vow] = game.progress_tracks
    assert (vow.name, vow.rank, vow.bound_impact, vow.status) == ("The deathbound quest", "extreme", "doomed", "active")
    assert game.impacts == ["doomed"]
    assert not game.game_over
    assert "follow-up move Swear an Iron Vow: STRONG_HIT" in labels_of(result.consequences)
    assert any(
        c.startswith('return from the brink bound to the extreme vow "The deathbound quest"')
        for c in labels_of(result.consequences)
    )

    complete_track(game, vow.id, "completed")
    assert game.impacts == []


def test_a_failed_bound_vow_keeps_its_burden(load_engine: None) -> None:
    game = _game("starforged")
    game.impacts = ["doomed"]
    game.progress_tracks.append(make_progress_track(id="vow_quest", bound_impact="doomed"))
    complete_track(game, "vow_quest", "failed")
    assert game.impacts == ["doomed"]


@pytest.mark.parametrize(("swear", "dead", "impacts"), [(MISS, True, []), (WEAK_HIT, False, ["cursed"])])
def test_classic_face_death_dies_when_the_vow_misses(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, swear: tuple[int, ...], dead: bool, impacts: list[str]
) -> None:
    game = _game("classic", health=0)
    result = OutcomeResult(follow_up_moves=["suffer/face_death"])
    fix_dice(monkeypatch, *WEAK_HIT, *swear)
    make_follow_up_moves(game, result)
    assert (game.game_over, game.impacts, len(game.progress_tracks)) == (dead, impacts, 0 if dead else 1)


def test_dying_gives_two_turns_to_raise_health(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    game = _game("starforged", health=0)
    game.impacts = ["wounded", "permanently_harmed"]
    fix_dice(monkeypatch, 15)
    resolve_move_outcome(game, "suffer/endure_harm", "MISS", target_npc_id=None, match=False)
    assert _dying(game) == ["Dying"]

    first, second = OutcomeResult(), OutcomeResult()
    tick_dying_clock(game, first)
    assert (_dying(game), first.follow_up_moves) == (["Dying"], [])
    tick_dying_clock(game, second)
    assert _dying(game) == []
    assert (labels_of(second.consequences), second.follow_up_moves) == (
        ["Dying: out of time"],
        ["threshold/face_death"],
    )


def test_dying_ends_when_health_rises_above_zero(load_engine: None) -> None:
    game = _game("starforged", health=0)
    start_dying_clock(game)
    game.resources.health = 2
    result = OutcomeResult()
    tick_dying_clock(game, result)
    assert (_dying(game), labels_of(result.consequences), result.follow_up_moves) == ([], [], [])


@pytest.mark.parametrize(("in_a_fight", "follow_ups"), [(False, []), (True, ["threshold/face_death"])])
def test_unconscious_faces_death_only_in_a_fight(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, in_a_fight: bool, follow_ups: list[str]
) -> None:
    game = _game("starforged", health=0)
    game.impacts = ["wounded", "permanently_harmed"]
    if in_a_fight:
        game.progress_tracks.append(make_progress_track(id="combat_raiders", track_type="combat"))
    fix_dice(monkeypatch, 25)
    result = resolve_move_outcome(game, "suffer/endure_harm", "MISS", target_npc_id=None, match=False)
    assert labels_of(result.consequences)[-1].startswith("Endure Harm: You are unconscious")
    assert result.follow_up_moves == follow_ups


def test_giving_up_forsakes_the_newest_vow(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    game = _game("starforged", spirit=0)
    game.impacts = ["shaken", "traumatized"]
    game.progress_tracks += [
        make_progress_track(id="vow_old", name="Old"),
        make_progress_track(id="vow_new", name="New"),
    ]
    fix_dice(monkeypatch, 15)
    result = resolve_move_outcome(game, "suffer/endure_stress", "MISS", target_npc_id=None, match=False)
    assert [t.status for t in game.progress_tracks] == ["active", "failed"]
    assert labels_of(result.consequences) == [
        "momentum -2",
        "Endure Stress: You give up. Forsake Your Vow.",
        'forsake the vow "New"',
        "momentum -2",
    ]
    assert result.follow_up_moves == ["suffer/endure_stress"]


def test_every_table_row_that_names_a_threshold_or_forsake_has_a_trigger(load_engine: None) -> None:
    rules = eng().suffer.table_rows
    assert all(rule.trigger in _TABLE_TRIGGERS for rule in rules)
    named = ("Face Death", "Face Desolation", "Forsake Your Vow")
    for setting_id in ("classic", "starforged", "sundered_isles"):
        for path in ("moves/endure_harm", "moves/endure_stress"):
            for row in load_package(setting_id).oracle_table(path).rows:
                text = plain_text(row.text)
                if any(name in text for name in named):
                    assert any(text.startswith(rule.prefix) for rule in rules), text


def test_meters_at_zero_bring_crisis_but_not_death(load_engine: None) -> None:
    game = _game("classic", health=0, spirit=0)
    update_crisis(game)
    assert (game.crisis_mode, game.game_over) == (True, False)


def test_classic_sojourn_clears_a_marked_condition_first(load_engine: None) -> None:
    game = _game("classic", health=3, spirit=2)
    game.impacts = ["shaken"]
    result = resolve_move_outcome(game, "relationship/sojourn", "WEAK_HIT", target_npc_id=None, match=False)
    assert (game.impacts, game.resources.spirit, game.resources.health) == ([], 3, 4)
    assert labels_of(result.consequences)[:2] == ["clear shaken", "spirit +1"]


def test_classic_heal_gives_two_health(load_engine: None) -> None:
    game = _game("classic", health=1)
    resolve_move_outcome(game, "adventure/heal", "STRONG_HIT", target_npc_id=None, match=False)
    assert game.resources.health == 3
