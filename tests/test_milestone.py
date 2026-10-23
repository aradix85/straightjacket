from typing import Any

import pytest

from straightjacket.engine.ai.provider_base import AIUnavailableError
from straightjacket.engine.engine_loader import eng
from straightjacket.engine.game import process_turn
from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.gamemaster.stance_gate import resolve_npc_stance
from straightjacket.engine.models import GameState, ProgressTrack
from straightjacket.engine.prompt_loader import get_prompt
from straightjacket.engine.ruleset import rolls
from straightjacket.engine.ruleset.answers import action_kind, action_phrase
from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.move_availability import available_moves
from tests._creation import TurnProvider, brain_answer, create_game, force_result, library_game

MILESTONE = "quest/reach_a_milestone"


def _starship_game() -> GameState:
    game = create_game(
        "starforged",
        location="Bleak Station",
        npcs=[("Vex", "A tired dockhand with a cybernetic arm", "neutral")],
        stats=(2, 2, 1, 1, 3),
        player_name="Ash",
        background_vow="Find my sister",
    )
    game.resources.meters["momentum"] = 6
    return game


def _game(setting_id: str) -> GameState:
    return library_game() if setting_id == "classic" else _starship_game()


def _milestone(**overrides: Any) -> dict[str, Any]:
    return brain_answer(
        move=MILESTONE,
        stat="none",
        location_change=None,
        player_intent="With the map deciphered, the way to the thief is clear",
        **overrides,
    )


def _swear(monkeypatch: pytest.MonkeyPatch, game: GameState, provider: TurnProvider) -> ProgressTrack:
    force_result(monkeypatch, "STRONG_HIT")
    process_turn(provider, game, "I swear to find the thief", stream=None)
    return next(t for t in game.progress_tracks if t.name == "Find the thief")


def _swear_answer() -> dict[str, Any]:
    return brain_answer(
        move="quest/swear_an_iron_vow",
        stat="heart",
        location_change=None,
        track_name="Find the thief",
        track_rank="troublesome",
    )


@pytest.mark.parametrize("setting_id", ["classic", "starforged"])
def test_reach_a_milestone_is_offered_only_while_a_vow_is_active(load_engine: None, setting_id: str) -> None:
    game = _game(setting_id)
    assert MILESTONE in available_moves(game)
    for track in game.progress_tracks:
        if track.track_type == "vow":
            track.status = "completed"
    assert MILESTONE not in available_moves(game)


def test_a_milestone_marks_the_named_vow_by_its_rank_without_a_roll(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = library_game()
    provider = TurnProvider(_swear_answer())
    vow = _swear(monkeypatch, game, provider)
    background = next(t for t in game.progress_tracks if t.id == "vow_background")
    background_ticks = background.ticks
    scene = game.narrative.scene_count

    provider.brains = [_milestone(target_track=vow.id)]
    _narration, roll, offer, _director = process_turn(provider, game, "The map is deciphered at last", stream=None)

    assert roll is None
    assert offer is None
    assert vow.ticks == rules().progress.ticks_per_mark[vow.rank]
    assert background.ticks == background_ticks
    assert game.narrative.scene_count == scene + 1
    entry = game.narrative.session_log[-1]
    assert entry.move == MILESTONE
    assert entry.result == "unrolled_move"
    assert game.world.current_scene_context.startswith(f"{action_phrase(MILESTONE)} at ")
    assert [c.kind for c in entry.consequences] == ["milestone"]
    prompt = provider.prompts[-1]
    assert '<scene type="unrolled_move"' in prompt
    assert get_prompt("task_unrolled_move") in prompt
    assert "<result" not in prompt
    told = [t.format(player=game.player_name) for t in eng().get_raw("consequence_templates")["milestone"]]
    assert any(f"<consequence>{sentence}</consequence>" in prompt for sentence in told)


def test_a_milestone_is_told_and_remembered_as_a_move_not_a_dialog(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = library_game()
    provider = TurnProvider(_swear_answer())
    vow = _swear(monkeypatch, game, provider)
    mira = game.npcs[0]
    mira.gather_count = 10
    thread = next(t for t in game.narrative.threads if t.linked_track_id == vow.id)
    weight, chaos = thread.weight, game.world.chaos_factor
    stance = resolve_npc_stance(game, mira, action_kind(MILESTONE), miss=False, hit=False).stance
    assert stance != resolve_npc_stance(game, mira, "social", miss=False, hit=False).stance

    brain = _milestone(target_track=vow.id, target_npc=mira.id)
    provider.brains = [brain]
    process_turn(provider, game, "With Mira's help the map is read", stream=None)

    prompt = provider.prompts[-1]
    assert f'stance="{stance}"' in prompt
    assert get_prompt("narrative_direction_perspective_label", perspective="action_detail") in prompt
    assert game.world.chaos_factor == chaos
    assert thread.weight > weight
    memory = mira.memory[-1].event
    assert action_phrase(MILESTONE) in memory
    assert gm().get_raw("memory_result_text")["unrolled_move"] in memory
    intent = brain["player_intent"][: eng().truncations.log_medium]
    assert game.narrative.narration_history[-1].prompt_summary == get_prompt("history_unrolled_move", intent=intent)


def test_a_milestone_with_several_vows_must_name_its_vow(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    game = library_game()
    provider = TurnProvider(_swear_answer())
    _swear(monkeypatch, game, provider)

    provider.brains = [_milestone(target_track=None)]
    with pytest.raises(AIUnavailableError, match="several active vow tracks"):
        process_turn(provider, game, "That is real progress", stream=None)


def test_a_dialog_turn_marks_no_milestone(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    game = library_game()
    provider = TurnProvider(_swear_answer())
    vow = _swear(monkeypatch, game, provider)

    for target in (vow.id, None):
        provider.brains = [_milestone(target_track=target, dialog_only=True)]
        process_turn(provider, game, "I tell Mira we are close", stream=None)
        assert game.narrative.session_log[-1].result == "dialog"
    assert vow.ticks == 0


@pytest.mark.parametrize("setting_id", ["classic", "starforged"])
def test_a_vow_is_fulfilled_after_its_milestones(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, setting_id: str
) -> None:
    game = _game(setting_id)
    provider = TurnProvider(_swear_answer())
    vow = _swear(monkeypatch, game, provider)
    xp = game.campaign.xp
    quests = {name: track.ticks for name, track in game.campaign.legacy.items()}

    provider.brains = [_milestone(target_track=vow.id)]
    marks = -(-rules().progress.max_ticks // rules().progress.ticks_per_mark[vow.rank])
    for _ in range(marks):
        process_turn(provider, game, "Another step closer to the thief", stream=None)
    assert vow.ticks == rules().progress.max_ticks
    monkeypatch.setattr(rolls, "_roll_challenge_dice", lambda: (1, 2))
    provider.brains = [
        brain_answer(move="quest/fulfill_your_vow", stat="none", location_change=None, target_track=vow.id)
    ]
    _narration, roll, _offer, _director = process_turn(provider, game, "I bring the thief to justice", stream=None)

    assert roll is not None
    assert roll.result == "STRONG_HIT"
    assert vow.status == "completed"
    if setting_id == "classic":
        assert game.campaign.xp == xp + rules().legacy.experience_by_rank[vow.rank]
    else:
        assert game.campaign.legacy["quests"].ticks == quests["quests"] + rules().legacy.ticks_by_rank[vow.rank]


def test_a_state_correction_retells_a_milestone_as_a_move_without_a_roll(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import process_correction

    game = library_game()
    background = next(t for t in game.progress_tracks if t.id == "vow_background")
    force_result(monkeypatch, "STRONG_HIT")
    provider = TurnProvider(_milestone(target_track=background.id))
    process_turn(provider, game, "The archive's lost index is found", stream=None)
    provider.correction = {**provider.correction, "correction_source": "state_error"}

    process_correction(provider, game, "Mira was there too")

    assert '<scene type="unrolled_move"' in provider.prompts[-1]
    assert game.narrative.session_log[-1].result == "unrolled_move"
    assert background.ticks == rules().progress.ticks_per_mark[background.rank]


def test_a_turn_corrected_into_a_milestone_keeps_no_roll(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.correction import process_correction

    game = library_game()
    background = next(t for t in game.progress_tracks if t.id == "vow_background")
    force_result(monkeypatch, "STRONG_HIT")
    provider = TurnProvider(brain_answer(location_change=None), _milestone(target_track=background.id))
    process_turn(provider, game, "I search the stacks for the lost index", stream=None)
    process_correction(provider, game, "I meant that finding the index is a milestone")
    assert game.narrative.session_log[-1].result == "unrolled_move"
    assert game.last_turn_snapshot is not None
    assert game.last_turn_snapshot.roll is None

    provider.correction = {**provider.correction, "correction_source": "state_error"}
    process_correction(provider, game, "Mira was there too")

    assert '<scene type="unrolled_move"' in provider.prompts[-1]
    assert "<result" not in provider.prompts[-1]
    analysis = next(c for c in reversed(provider.calls) if c.log_role == "correction")
    no_roll = eng().ai_text.narrator_defaults["no_roll"].format(result="unrolled_move")
    assert no_roll in str(analysis.messages[-1]["content"])
