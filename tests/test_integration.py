import pytest

from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.models import labels_of
from straightjacket.engine.ruleset.progress import menace_per_mark, ticks_per_mark
from tests._creation import TurnProvider, brain_answer, fixed_roll, force_result, library_game
from tests._helpers import (
    action_prompt_kwargs,
    dialog_prompt_kwargs,
    fix_dice,
    make_brain_result,
    make_clock,
    make_memory,
    make_npc,
    make_scene_setup,
)

_SEARCH = brain_answer(player_intent="I search the room for clues", location_change=None)
_TALK = brain_answer(
    move="dialog",
    stat="none",
    dialog_only=True,
    target_npc="npc_1",
    player_intent="I talk to Mira",
    location_change=None,
)


def test_turn_action_produces_narration(load_engine: None) -> None:
    from straightjacket.engine.game.turn import process_turn

    provider = TurnProvider(_SEARCH)
    game = library_game()
    initial_scene = game.narrative.scene_count

    narration, roll, _burn_info, _director_ctx = process_turn(
        provider,
        game,
        "I search the room for clues",
        stream=None,
    )

    assert game.narrative.scene_count == initial_scene + 1

    assert narration == provider.narrations[-1]

    assert roll is not None
    assert roll.move == "adventure/face_danger"
    assert roll.stat_name == "wits"
    assert roll.result in ("STRONG_HIT", "WEAK_HIT", "MISS")

    assert game.last_turn_snapshot is not None
    assert game.last_turn_snapshot.player_input == "I search the room for clues"

    assert [entry.result for entry in game.narrative.session_log] == ["opening", roll.result]
    assert game.narrative.session_log[-1].move == "adventure/face_danger"

    assert {"brain", "narrator", "narrator_metadata"} <= {call.log_role for call in provider.calls}


def test_an_npc_the_narration_leaves_out_was_not_in_the_scene(load_engine: None) -> None:
    from straightjacket.engine.game.turn import process_turn

    game = library_game()
    mira = game.npcs[0]
    game.world.current_scene_context = "conversation at Abandoned Library with Mira"
    for _ in range(2):
        process_turn(TurnProvider(_SEARCH), game, "I search the room for clues", stream=None)

    assert [m.scene for m in mira.memory if m.scene > 1] == []
    assert "Mira" not in game.world.current_scene_context


def test_a_turn_ends_the_act_at_its_last_scene_without_the_director(load_engine: None) -> None:
    from straightjacket.engine.game.turn import process_turn
    from straightjacket.engine.models_story import StoryAct
    from straightjacket.engine.story_state import get_current_act
    from tests._helpers import make_blueprint

    game = library_game()
    game.narrative.story_blueprint = make_blueprint(
        central_conflict="x",
        acts=[
            StoryAct(
                phase=f"phase_{i}",
                title=f"Act {i + 1}",
                goal="",
                scene_range=list(r),
                mood="tense",
                transition_trigger=f"trigger_{i}",
            )
            for i, r in enumerate([(1, 2), (3, 4), (5, 6)])
        ],
    )

    _narration, _roll, _burn_info, _director_ctx = process_turn(
        TurnProvider(_SEARCH), game, "I search the room for clues", stream=None
    )

    assert game.narrative.scene_count == 2
    assert game.narrative.story_blueprint is not None
    assert game.narrative.story_blueprint.triggered_transitions == ["act_0"]
    assert get_current_act(game).act_number == 2


def test_a_journey_is_started_once_and_then_continued_by_its_id(load_engine: None) -> None:
    from straightjacket.engine.game.turn import process_turn

    journey = brain_answer(move="adventure/undertake_a_journey", location_change=None)
    provider = TurnProvider(
        {**journey, "track_name": "To the ridge"},
        {**journey, "track_name": "Across the moor", "target_track": "journey_to_the_ridge"},
    )
    game = library_game()
    hits = 0
    for _ in range(2):
        _narration, roll, _burn_info, _director_ctx = process_turn(provider, game, "I travel on", stream=None)
        assert roll is not None
        hits += roll.result in ("STRONG_HIT", "WEAK_HIT")
    [track] = [t for t in game.progress_tracks if t.track_type == "journey"]
    assert (track.id, track.status) == ("journey_to_the_ridge", "active")
    assert track.ticks == hits * ticks_per_mark(track)


@pytest.mark.parametrize("result", ["STRONG_HIT", "MISS"])
def test_a_connection_made_in_play_grows_through_its_tests_and_once_bonded_develops_by_rank(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, result: str
) -> None:
    from straightjacket.engine.game.turn import process_turn
    from tests._creation import create_game

    game = create_game(
        "starforged",
        location="Drift Station",
        npcs=[("Kira Vance", "A pilot with a burned hand.", "friendly")],
        stats=(2, 2, 1, 1, 3),
        player_name="Aria",
        background_vow="Keep the station running",
    )
    kira = game.npcs[0].id
    force_result(monkeypatch, result)
    provider = TurnProvider(
        brain_answer(
            move="connection/make_a_connection", stat="heart", target_npc=kira, track_name="Kira", location_change=None
        ),
        brain_answer(move="connection/test_your_relationship", stat="heart", target_npc=kira, location_change=None),
        brain_answer(move="connection/develop_your_relationship", stat="none", target_npc=kira, location_change=None),
    )
    _narration, _roll, _burn, _director = process_turn(provider, game, "I share a drink with Kira", stream=None)
    connections = [t for t in game.progress_tracks if t.track_type == "connection"]

    if result == "MISS":
        assert connections == []
        return
    [track] = connections
    assert track.id == f"connection_{kira}"
    process_turn(provider, game, "I stand by Kira when her crew turns on her", stream=None)
    assert track.ticks == ticks_per_mark(track)
    track.status = "bonded"
    _narration, roll, _burn, _director = process_turn(provider, game, "I help Kira fix her ship", stream=None)
    assert roll is not None
    assert (roll.move, roll.stat_name) == ("connection/develop_your_relationship", "dangerous")


def test_turn_dialog_skips_roll(load_engine: None) -> None:
    from straightjacket.engine.game.turn import process_turn

    provider = TurnProvider(_TALK)
    game = library_game()
    narration, roll, _burn_info, _director_ctx = process_turn(provider, game, "I talk to Mira", stream=None)

    assert roll is None
    assert narration == provider.narrations[-1]
    assert game.narrative.scene_count == 2
    assert game.narrative.session_log[-1].result == "dialog"


def test_a_menace_that_fills_at_scene_end_forsakes_its_vow_in_the_next_turn_and_is_told(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.game import turn
    from tests._helpers import make_threat

    monkeypatch.setattr(turn, "check_scene", lambda _game: make_scene_setup(scene_type="expected"))
    from straightjacket.engine.ruleset import threats as threats_module

    monkeypatch.setattr(threats_module.random, "random", lambda: 0.0)
    game = library_game()
    [vow] = [t for t in game.progress_tracks if t.track_type == "vow"]
    threat = make_threat(id="t_king", name="The Hollow King", linked_vow_id=vow.id, rank="dangerous")
    threat.menace_ticks = threat.max_menace_ticks - menace_per_mark(threat)
    game.threats.append(threat)
    provider = TurnProvider(_TALK)

    turn.process_turn(provider, game, "I talk to Mira", stream=None)
    assert (threat.menace_full, threat.status, vow.status) == (True, "active", "active")

    turn.process_turn(provider, game, "I talk to Mira again", stream=None)
    assert '<vow_forsaken threat="The Hollow King"/>' in provider.prompts[-1]
    assert (threat.status, vow.status) == ("resolved", "failed")


def test_harm_at_zero_in_a_turn_is_endured_and_does_not_end_the_game(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.game import turn
    from straightjacket.engine.ruleset import move_outcome

    force_result(monkeypatch, "WEAK_HIT")
    monkeypatch.setattr(move_outcome, "roll_action", fixed_roll("MISS"))
    game = library_game()
    game.resources.meters["health"], game.resources.meters["spirit"], game.resources.meters["supply"] = 0, 0, 0
    provider = TurnProvider(_SEARCH)

    turn.process_turn(provider, game, "I climb the crumbling shelves", stream=None)

    assert (game.game_over, game.crisis_mode, game.impacts) == (False, True, ["wounded"])
    assert "follow-up move Endure Harm: MISS" in provider.prompts[-1]
    assert "follow-up move Endure Harm: MISS" in labels_of(game.narrative.session_log[-1].consequences)


def test_a_dying_character_who_does_not_heal_faces_death_in_a_dialog_turn(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.game import turn
    from straightjacket.engine.ruleset import move_outcome
    from straightjacket.engine.ruleset.suffer import start_dying_clock

    monkeypatch.setattr(turn, "check_scene", lambda _game: make_scene_setup(scene_type="expected"))
    monkeypatch.setattr(move_outcome, "roll_action", fixed_roll("MISS"))
    game = library_game()
    game.resources.meters["health"] = 0
    start_dying_clock(game)
    game.world.clocks[-1].filled = 1
    provider = TurnProvider(_TALK)

    turn.process_turn(provider, game, "I whisper to Mira", stream=None)

    prompt = provider.prompts[-1]
    assert game.game_over
    for told in ("Dying: out of time", "follow-up move Face Death: MISS", "you are dead"):
        assert f"<consequence>{told}</consequence>" in prompt
    assert "FINAL_SCENE" in prompt


def test_turn_consequences_applied_on_miss(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
    from tests._helpers import record_price_tables

    rolled = record_price_tables(monkeypatch)
    game = library_game()

    result = resolve_move_outcome(game, "adventure/face_danger", "MISS", target_npc_id=None, match=False)

    assert rolled == ["Pay the Price"]
    assert labels_of(result.consequences)


def test_scene_test_produces_three_types(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.gamemaster.scene import check_scene

    game = library_game()
    game.world.chaos_factor = 9

    def scene_type(roll: int) -> str:
        game.narrative.keyed_scenes = []
        fix_dice(monkeypatch, roll)
        return check_scene(game).scene_type

    assert [scene_type(roll) for roll in (10, 9, 8)] == ["expected", "altered", "interrupt"]


def test_dialog_prompt_contains_world_and_character(load_engine: None) -> None:
    from straightjacket.engine.prompt_dialog import build_dialog_prompt

    game = library_game()
    brain = make_brain_result(
        move="dialog",
        target_npc="npc_1",
        player_intent="Ask about the archives",
    )
    prompt = build_dialog_prompt(game, brain, **dialog_prompt_kwargs(player_words="I ask Mira about the archives"))

    assert '<world genre="classic"' in prompt
    assert "Kael" in prompt
    assert "Mira" in prompt
    assert "dialog" in prompt


def test_action_prompt_contains_result_and_position(load_engine: None) -> None:
    from straightjacket.engine.models import RollResult
    from straightjacket.engine.prompt_action import build_action_prompt

    game = library_game()
    brain = make_brain_result(
        move="adventure/face_danger",
        stat="wits",
        player_intent="Search for hidden compartments",
        approach="carefully examining every surface",
    )
    roll = RollResult(
        d1=4,
        c1=5,
        c2=8,
        stat_name="wits",
        stat_value=2,
        action_score=9,
        result="STRONG_HIT",
        move="adventure/face_danger",
        match=False,
    )

    prompt = build_action_prompt(
        game,
        brain,
        roll,
        consequences=[],
        npc_agency=[],
        **action_prompt_kwargs(
            consequence_sentences=["The tide shifts. Hero can feel it."],
            player_words="I search for hidden compartments",
        ),
    )

    assert "STRONG_HIT" in prompt
    assert "risky" in prompt
    assert "Search" in prompt or "search" in prompt


def test_narrator_system_prompt_includes_constraints(load_engine: None) -> None:
    from straightjacket.engine.prompt_blocks import get_narrator_system

    game = library_game()
    game.preferences.content_lines = "no spiders"

    system, cached_prefix = get_narrator_system(game)

    assert "<world>" in system
    assert "<player>" in system
    assert "spiders" in system
    assert system.startswith(cached_prefix)
    assert "spiders" in cached_prefix
    assert "<character_state" not in cached_prefix


def test_correction_brain_parses_response(load_engine: None) -> None:
    from straightjacket.engine.correction.analysis import call_correction_brain

    provider = TurnProvider()
    game = library_game()

    snap = game.snapshot()
    snap.player_input = "I attack the guard"
    brain = make_brain_result(move="combat/strike", stat="iron", player_intent="Attack the guard")

    result = call_correction_brain(
        provider, game, "I didn't want to attack, just talk", snap, brain, "You swing your sword..."
    )

    assert "correction_source" in result
    assert result["correction_source"] in ("input_misread", "state_error")


def test_momentum_burn_upgrades_result() -> None:
    from straightjacket.engine.models import RollResult
    from straightjacket.engine.ruleset.rolls import can_burn_momentum

    game = library_game()
    game.resources.meters["momentum"] = 7

    roll = RollResult(
        d1=1,
        c1=5,
        c2=6,
        stat_name="wits",
        stat_value=2,
        action_score=4,
        result="MISS",
        move="adventure/face_danger",
        match=False,
    )

    upgrade = can_burn_momentum(game, roll)
    assert upgrade == "STRONG_HIT"

    roll2 = RollResult(
        d1=1,
        c1=5,
        c2=9,
        stat_name="wits",
        stat_value=2,
        action_score=4,
        result="MISS",
        move="adventure/face_danger",
        match=False,
    )

    upgrade2 = can_burn_momentum(game, roll2)
    assert upgrade2 == "WEAK_HIT"


def test_story_completion_triggers() -> None:
    from straightjacket.engine.models import StoryBlueprint
    from straightjacket.engine.story_state import get_current_act

    game = library_game()
    game.narrative.story_blueprint = StoryBlueprint.from_dict(
        {
            "structure_type": "3act",
            "central_conflict": "The shadow threatens all",
            "antagonist_force": "The creeping darkness",
            "thematic_thread": "What is worth saving?",
            "acts": [
                {
                    "phase": "setup",
                    "title": "Gathering",
                    "goal": "Find allies",
                    "scene_range": [1, 7],
                    "mood": "mysterious",
                    "transition_trigger": "Allies gathered",
                },
                {
                    "phase": "confrontation",
                    "title": "Into Darkness",
                    "goal": "Face the shadow",
                    "scene_range": [8, 14],
                    "mood": "tense",
                    "transition_trigger": "Shadow revealed",
                },
                {
                    "phase": "climax",
                    "title": "Final Stand",
                    "goal": "Defeat or submit",
                    "scene_range": [15, 20],
                    "mood": "desperate",
                    "transition_trigger": "Resolution",
                },
            ],
            "revelations": [],
            "possible_endings": [],
            "triggered_transitions": ["act_0"],
            "triggered_director_phases": [],
            "revealed": [],
            "story_complete": False,
        }
    )
    game.narrative.scene_count = 10

    act = get_current_act(game)
    assert act.phase == "confrontation"
    assert act.act_number == 2


def test_correction_state_ops_npc_edit(load_engine: None) -> None:
    from straightjacket.engine.correction.ops import apply_correction_ops

    game = library_game()
    original_name = game.npcs[0].name

    apply_correction_ops(
        game,
        [
            {
                "op": "npc_edit",
                "npc_id": "npc_1",
                "fields": {"description": "Updated description", "disposition": "hostile"},
                "split_name": None,
                "split_description": None,
                "merge_source_id": None,
                "value": None,
            }
        ],
    )
    assert game.npcs[0].description == "Updated description"
    assert game.npcs[0].disposition == "hostile"
    assert game.npcs[0].name == original_name


def test_correction_state_ops_npc_rename(load_engine: None) -> None:
    from straightjacket.engine.correction.ops import apply_correction_ops

    game = library_game()

    apply_correction_ops(
        game,
        [
            {
                "op": "npc_edit",
                "npc_id": "npc_1",
                "fields": {"name": "Captain Voss"},
                "split_name": None,
                "split_description": None,
                "merge_source_id": None,
                "value": None,
            }
        ],
    )
    assert game.npcs[0].name == "Captain Voss"
    assert "Mira" in game.npcs[0].aliases


def test_correction_state_ops_location_edit(load_engine: None) -> None:
    from straightjacket.engine.correction.ops import apply_correction_ops

    game = library_game()

    apply_correction_ops(
        game,
        [
            {
                "op": "location_edit",
                "npc_id": None,
                "fields": None,
                "split_name": None,
                "split_description": None,
                "merge_source_id": None,
                "value": "The Dark Tower",
            }
        ],
    )
    assert game.world.current_location == "The Dark Tower"


def test_correction_state_ops_npc_split(load_engine: None) -> None:
    from straightjacket.engine.correction.ops import apply_correction_ops

    game = library_game()
    count_before = len(game.npcs)

    apply_correction_ops(
        game,
        [
            {
                "op": "npc_split",
                "npc_id": "npc_1",
                "split_name": "Mira's Twin",
                "split_description": "Identical but different",
                "fields": None,
                "merge_source_id": None,
                "value": None,
            }
        ],
    )
    assert len(game.npcs) == count_before + 1
    new_npc = next(n for n in game.npcs if n.name == "Mira's Twin")
    assert new_npc.description == "Identical but different"


def _op(op: str, **fields: object) -> dict[str, object]:
    base: dict[str, object] = {
        "op": op,
        "npc_id": None,
        "fields": None,
        "split_name": None,
        "split_description": None,
        "merge_source_id": None,
        "value": None,
    }
    return {**base, **fields}


def test_a_correction_keeps_the_name_when_it_is_given_an_empty_one(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import ops

    warnings: list[str] = []
    monkeypatch.setattr(ops, "log", lambda msg, level="info": warnings.append(msg) if level == "warning" else None)
    game = library_game()
    ops.apply_correction_ops(game, [_op("npc_edit", npc_id="npc_1", fields={"name": " ", "agenda": "hide"})])
    assert (game.npcs[0].name, game.npcs[0].agenda) == ("Mira", "hide")
    assert warnings == ["[Correction] npc_edit: Mira keeps its name, the analysis gave an empty one"]


def test_a_correction_that_marks_an_npc_dead_leaves_the_description_whole(load_engine: None) -> None:
    from straightjacket.engine.correction.ops import apply_correction_ops

    game = library_game()
    game.npcs[0].description = "A tall woman who guards the totem of the dead king"
    apply_correction_ops(game, [_op("npc_edit", npc_id="npc_1", fields={"status": "deceased"})])
    assert game.npcs[0].status == "deceased"
    assert game.npcs[0].description == "A tall woman who guards the totem of the dead king"


def test_a_split_without_a_name_rolls_one_and_numbers_the_npc(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import ops

    monkeypatch.setattr(ops, "roll_oracle_name", lambda game: "Bren Hollow")
    game = library_game()
    game.npcs[0].last_location = "Abandoned Library"
    ops.apply_correction_ops(game, [_op("npc_split", npc_id="npc_1")])
    twin = game.npcs[-1]
    assert (twin.id, twin.name, twin.name_rolled, twin.description) == ("npc_2", "Bren Hollow", True, "")
    assert twin.last_location == "Abandoned Library"


_UNAPPLICABLE_OPS = [
    _op("npc_edit"),
    _op("npc_split"),
    _op("npc_merge", npc_id="npc_1", merge_source_id="npc_1"),
    _op("location_edit", value=""),
    _op("scene_context"),
    _op("time_edit", value="teatime"),
    _op("backstory_append"),
]


@pytest.mark.parametrize("op", _UNAPPLICABLE_OPS)
def test_an_op_the_engine_cannot_apply_is_reported_and_changes_nothing(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, op: dict[str, object]
) -> None:
    from straightjacket.engine.correction import ops

    warnings: list[str] = []
    monkeypatch.setattr(ops, "log", lambda msg, level="info": warnings.append(msg) if level == "warning" else None)
    game = library_game()
    before = game.to_dict()
    ops.apply_correction_ops(game, [op])
    assert game.to_dict() == before
    [warning] = warnings
    assert warning.startswith(f"[Correction] {op['op']} skipped: ")


def test_every_correction_op_the_analysis_is_offered_is_applied_above(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng

    assert sorted(op["op"] for op in _UNAPPLICABLE_OPS) == sorted(eng().correction.ops)


def test_description_match_catches_identity_reveal(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.npc.description_match import description_match_existing_npc

    game = library_game()

    match = description_match_existing_npc(
        game,
        "The archivist with ink-stained hands and spectacles",
        "mysterious_stranger",
    )
    assert match is not None
    assert match.name == "Mira"


def test_description_match_rejects_short_descriptions(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.npc.description_match import description_match_existing_npc

    game = library_game()
    match = description_match_existing_npc(game, "Short", "stranger")
    assert match is None


def test_merge_npc_identity_updates_clock_owner(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.npc.lifecycle import merge_npc_identity

    game = library_game()
    game.world.clocks = [
        make_clock(name="Mira's scheme", clock_type="scheme", owner_kind="npc", owner_id="Mira"),
    ]
    npc = game.npcs[0]
    merge_npc_identity(npc, "Captain Voss", game=game)
    assert game.world.clocks[0].owner_id == "Captain Voss"


def test_correction_state_ops_npc_merge(load_engine: None) -> None:
    from straightjacket.engine.correction.ops import apply_correction_ops

    game = library_game()
    source = make_npc(
        id="npc_3",
        name="Stranger",
        disposition="neutral",
        memory=[make_memory(scene=2, event="saw fire", importance=5)],
    )
    game.npcs.append(source)
    ops = [{"op": "npc_merge", "npc_id": "npc_1", "merge_source_id": "npc_3"}]
    apply_correction_ops(game, ops)
    assert not any(n.id == "npc_3" for n in game.npcs), "source should be removed"
    target = next(n for n in game.npcs if n.id == "npc_1")
    assert any(m.event == "saw fire" for m in target.memory), "memories should transfer"
    assert "Stranger" in target.aliases, "source name should become alias"


def test_dialog_turn_runs_npc_agency_on_interval_scene(load_engine: None) -> None:
    from straightjacket.engine.game.turn import process_turn

    provider = TurnProvider(_TALK)
    game = library_game()
    for npc in game.npcs:
        npc.status = "active"
        npc.agenda = "Keep the archive sealed"
    game.narrative.scene_count = gm().pacing.npc_agency_interval - 1
    process_turn(provider, game, "I talk to Mira", stream=None)
    assert "<npc_agency>" in provider.prompts[-1]
