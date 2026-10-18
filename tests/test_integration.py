import pytest

from tests._helpers import (
    action_prompt_kwargs,
    dialog_prompt_kwargs,
    fix_dice,
    make_brain_result,
    make_clock,
    make_memory,
    make_npc,
)

import sys
import json
from collections.abc import Callable

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse


class MockProvider:
    def __init__(self) -> None:
        self.calls: list = []

    def create_message(self, spec: AICallSpec) -> AIResponse:
        json_schema = spec.json_schema
        self.calls.append(
            {
                "model": spec.model,
                "system_len": len(spec.system),
                "messages": spec.messages,
                "json_schema": json_schema,
            }
        )

        if json_schema and "move" in json_schema.get("properties", {}):
            return AIResponse(
                content=json.dumps(
                    {
                        "type": "action",
                        "move": "adventure/face_danger",
                        "stat": "wits",
                        "approach": "carefully examining the area",
                        "target_npc": None,
                        "dialog_only": False,
                        "player_intent": "I search the room for clues",
                        "world_addition": None,
                        "location_change": None,
                        "track_name": None,
                        "track_rank": None,
                        "target_track": None,
                        "target_clock": None,
                        "bonus_id": None,
                        "undetermined_facts": [],
                        "boasts": [],
                    }
                ),
                usage={"input_tokens": 100, "output_tokens": 50},
            )

        if json_schema and "new_npcs" in json_schema.get("properties", {}):
            return AIResponse(
                content=json.dumps(
                    {
                        "new_npcs": [],
                        "npc_renames": [],
                        "npc_details": [],
                        "deceased_npcs": [],
                        "lore_npcs": [],
                    }
                ),
                usage={"input_tokens": 100, "output_tokens": 50},
            )

        if json_schema and "pass" in json_schema.get("properties", {}):
            return AIResponse(
                content=json.dumps(
                    {
                        "pass": True,
                        "violations": [],
                        "correction": "",
                    }
                ),
                usage={"input_tokens": 100, "output_tokens": 50},
            )

        if json_schema and "revelation_confirmed" in json_schema.get("properties", {}):
            return AIResponse(
                content=json.dumps(
                    {
                        "revelation_confirmed": False,
                        "reasoning": "Not present in narration.",
                    }
                ),
                usage={"input_tokens": 100, "output_tokens": 50},
            )

        if json_schema and "scene_summary" in json_schema.get("properties", {}):
            return AIResponse(
                content=json.dumps(
                    {
                        "scene_summary": "The player searched the room.",
                        "narrator_guidance": "Build tension slowly.",
                        "npc_guidance": [],
                        "npc_reflections": {},
                        "arc_notes": "Story is progressing.",
                    }
                ),
                usage={"input_tokens": 100, "output_tokens": 50},
            )

        if json_schema and "correction_source" in json_schema.get("properties", {}):
            return AIResponse(
                content=json.dumps(
                    {
                        "correction_source": "input_misread",
                        "corrected_input": "I talk to the guard instead",
                        "narrator_guidance": "Rewrite as dialog with the guard.",
                        "director_useful": False,
                        "state_ops": [],
                    }
                ),
                usage={"input_tokens": 100, "output_tokens": 50},
            )

        return AIResponse(
            content="\u201cThe dust hung thick in the air. Your fingers traced the "
            "edge of the desk, finding nothing but splinters and silence. "
            "From the hallway, a floorboard groaned under weight that "
            "wasn\u2019t yours.\u201d",
            usage={"input_tokens": 100, "output_tokens": 50},
        )

    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse:
        response = self.create_message(spec)
        on_text(response.content)
        return response


def _make_game():
    from tests._creation import create_game

    game = create_game(
        "classic",
        location="Abandoned Library",
        npcs=[("Mira", "Young archivist with ink-stained hands", "friendly")],
        stats=(2, 2, 1, 1, 3),
        player_name="Kael",
        background_vow="Keep the archive whole",
    )
    mira = game.npcs[0]
    mira.agenda = "protect the archives"
    mira.instinct = "trust cautiously"
    mira.memory.append(
        make_memory(event="Met the player at the entrance", emotional_weight="curious", type="observation", scene=1)
    )
    game.world.clocks.append(
        make_clock(
            name="Shadow Rising",
            clock_type="threat",
            segments=6,
            filled=2,
            owner_kind="world",
            trigger_description="Darkness engulfs the library",
        )
    )
    return game


def test_turn_action_produces_narration(load_engine: None) -> None:
    from straightjacket.engine.game.turn import process_turn

    provider = MockProvider()
    game = _make_game()
    initial_scene = game.narrative.scene_count

    game, narration, roll, _burn_info, _director_ctx = process_turn(
        provider,
        game,
        "I search the room for clues",
        stream=None,
    )

    assert game.narrative.scene_count == initial_scene + 1

    assert len(narration) > 20
    assert "dust" in narration.lower()

    assert roll is not None
    assert roll.move == "adventure/face_danger"
    assert roll.stat_name == "wits"
    assert roll.result in ("STRONG_HIT", "WEAK_HIT", "MISS")

    assert game.last_turn_snapshot is not None
    assert game.last_turn_snapshot.player_input == "I search the room for clues"

    assert [entry.result for entry in game.narrative.session_log] == ["opening", roll.result]
    assert game.narrative.session_log[-1].move == "adventure/face_danger"

    assert len(provider.calls) >= 3


def test_a_turn_ends_the_act_at_its_last_scene_without_the_director(load_engine: None) -> None:
    from straightjacket.engine.game.turn import process_turn
    from straightjacket.engine.models_story import StoryAct
    from straightjacket.engine.story_state import get_current_act
    from tests._helpers import make_blueprint

    game = _make_game()
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

    game, _narration, _roll, _burn_info, _director_ctx = process_turn(
        MockProvider(), game, "I search the room for clues", stream=None
    )

    assert game.narrative.scene_count == 2
    assert game.narrative.story_blueprint is not None
    assert game.narrative.story_blueprint.triggered_transitions == ["act_0"]
    assert get_current_act(game).act_number == 2


class _ScriptedBrain(MockProvider):
    def __init__(self, *answers: dict) -> None:
        super().__init__()
        self.answers = list(answers)

    def create_message(self, spec: AICallSpec) -> AIResponse:
        from tests.test_brain_move_availability import BRAIN_FIELDS

        if spec.json_schema and "move" in spec.json_schema["properties"]:
            answer = {**BRAIN_FIELDS, **self.answers.pop(0)}
            return AIResponse(content=json.dumps(answer), usage={"input_tokens": 100, "output_tokens": 50})
        return super().create_message(spec)


def test_a_journey_is_started_once_and_then_continued_by_its_id(load_engine: None) -> None:
    from straightjacket.engine.game.turn import process_turn

    journey = {"move": "adventure/undertake_a_journey", "stat": "wits", "track_rank": "dangerous"}
    provider = _ScriptedBrain(
        {**journey, "track_name": "To the ridge"},
        {**journey, "track_name": "Across the moor", "target_track": "journey_to_the_ridge"},
    )
    game = _make_game()
    hits = 0
    for _ in range(2):
        game, _narration, roll, _burn_info, _director_ctx = process_turn(provider, game, "I travel on", stream=None)
        assert roll is not None
        hits += roll.result in ("STRONG_HIT", "WEAK_HIT")
    [track] = [t for t in game.progress_tracks if t.track_type == "journey"]
    assert (track.id, track.status) == ("journey_to_the_ridge", "active")
    assert track.ticks == hits * track.ticks_per_mark


def _rolling(result: str) -> Callable[[str, int, str, int, int], object]:
    from straightjacket.engine.models import RollResult

    def _roll(stat_name: str, stat_value: int, move: str, momentum: int, adds: int) -> RollResult:
        hit = result != "MISS"
        return RollResult(
            d1=6 if hit else 1,
            c1=1 if hit else 9,
            c2=2 if hit else 10,
            stat_name=stat_name,
            stat_value=stat_value,
            action_score=min(6 + stat_value, 10) if hit else 1 + stat_value,
            result=result,
            move=move,
            match=False,
        )

    return _roll


def _force_result(monkeypatch: pytest.MonkeyPatch, result: str) -> None:
    from straightjacket.engine.game import turn
    from straightjacket.engine.models import SceneSetup

    monkeypatch.setattr(turn, "roll_action", _rolling(result))
    monkeypatch.setattr(turn, "check_scene", lambda _game: SceneSetup(scene_type="expected", chaos_roll=10))


@pytest.mark.parametrize("result", ["STRONG_HIT", "MISS"])
def test_a_connection_made_in_play_is_the_npcs_and_can_be_developed(
    load_engine: None, stub_emotions: None, monkeypatch: pytest.MonkeyPatch, result: str
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
    _force_result(monkeypatch, result)
    provider = _ScriptedBrain(
        {
            "move": "connection/make_a_connection",
            "stat": "heart",
            "target_npc": kira,
            "track_name": "Kira",
            "track_rank": "dangerous",
        },
        {"move": "connection/develop_your_relationship", "stat": "none", "target_npc": kira},
    )
    game, _narration, _roll, _burn, _director = process_turn(provider, game, "I share a drink with Kira", stream=None)
    connections = [t.id for t in game.progress_tracks if t.track_type == "connection"]

    if result == "MISS":
        assert connections == []
        return
    assert connections == [f"connection_{kira}"]
    game, _narration, roll, _burn, _director = process_turn(provider, game, "I help Kira fix her ship", stream=None)
    assert roll is not None
    assert (roll.move, roll.stat_name) == ("connection/develop_your_relationship", "dangerous")


def test_turn_dialog_skips_roll(load_engine: None) -> None:
    from straightjacket.engine.game.turn import process_turn

    provider = MockProvider()

    original_create = provider.create_message
    call_count = [0]

    def dialog_brain(spec):
        call_count[0] += 1
        schema = spec.json_schema
        is_brain = bool(schema and "move" in schema.get("properties", {}))
        if is_brain:
            return AIResponse(
                content=json.dumps(
                    {
                        "type": "action",
                        "move": "dialog",
                        "stat": "none",
                        "approach": "",
                        "target_npc": "npc_1",
                        "dialog_only": True,
                        "player_intent": "I talk to Mira",
                        "world_addition": None,
                        "location_change": None,
                        "track_name": None,
                        "track_rank": None,
                        "target_track": None,
                        "target_clock": None,
                        "bonus_id": None,
                        "undetermined_facts": [],
                        "boasts": [],
                    }
                ),
                usage={"input_tokens": 100, "output_tokens": 50},
            )
        return original_create(spec)

    provider.create_message = dialog_brain

    game = _make_game()
    game, narration, roll, _burn_info, _director_ctx = process_turn(
        provider,
        game,
        "I talk to Mira",
        stream=None,
    )

    assert roll is None

    assert len(narration) > 10

    assert game.narrative.scene_count == 2


def test_a_menace_that_fills_at_scene_end_forsakes_its_vow_in_the_next_turn_and_is_told(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.game import turn
    from straightjacket.engine.models import SceneSetup
    from tests._helpers import make_threat

    monkeypatch.setattr(turn, "check_scene", lambda _game: SceneSetup(scene_type="expected", chaos_roll=10))
    monkeypatch.setattr(eng().threats, "autonomous_tick_chance", 1.0)
    game = _make_game()
    [vow] = [t for t in game.progress_tracks if t.track_type == "vow"]
    threat = make_threat(id="t_king", name="The Hollow King", linked_vow_id=vow.id, rank="dangerous")
    threat.menace_ticks = threat.max_menace_ticks - threat.menace_per_mark
    game.threats.append(threat)
    talk = {"move": "dialog", "stat": "none", "dialog_only": True, "target_npc": game.npcs[0].id}
    provider = _ScriptedBrain(talk, talk)

    game, *_ = turn.process_turn(provider, game, "I talk to Mira", stream=None)
    assert (threat.menace_full, threat.status, vow.status) == (True, "active", "active")

    game, *_ = turn.process_turn(provider, game, "I talk to Mira again", stream=None)
    narrator_prompt = [c for c in provider.calls if not c["json_schema"]][-1]["messages"][-1]["content"]
    assert '<vow_forsaken threat="The Hollow King"/>' in narrator_prompt
    assert (threat.status, vow.status) == ("resolved", "failed")


def _last_narrator_prompt(provider: MockProvider) -> str:
    prompt: str = [c for c in provider.calls if not c["json_schema"]][-1]["messages"][-1]["content"]
    return prompt


def test_harm_at_zero_in_a_turn_is_endured_and_does_not_end_the_game(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.game import turn
    from straightjacket.engine.mechanics import move_outcome

    _force_result(monkeypatch, "WEAK_HIT")
    monkeypatch.setattr(move_outcome, "roll_action", _rolling("MISS"))
    game = _make_game()
    game.resources.health, game.resources.spirit, game.resources.supply = 0, 0, 0
    provider = _ScriptedBrain({"move": "adventure/face_danger", "stat": "wits"})

    game, *_ = turn.process_turn(provider, game, "I climb the crumbling shelves", stream=None)

    assert (game.game_over, game.crisis_mode, game.impacts) == (False, True, ["wounded"])
    assert "follow-up move Endure Harm: MISS" in _last_narrator_prompt(provider)
    assert "follow-up move Endure Harm: MISS" in game.narrative.session_log[-1].consequences


def test_a_dying_character_who_does_not_heal_faces_death_in_a_dialog_turn(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.game import turn
    from straightjacket.engine.mechanics import move_outcome
    from straightjacket.engine.mechanics.suffer import start_dying_clock
    from straightjacket.engine.models import SceneSetup

    monkeypatch.setattr(turn, "check_scene", lambda _game: SceneSetup(scene_type="expected", chaos_roll=10))
    monkeypatch.setattr(move_outcome, "roll_action", _rolling("MISS"))
    game = _make_game()
    game.resources.health = 0
    start_dying_clock(game)
    game.world.clocks[-1].filled = 1
    provider = _ScriptedBrain({"move": "dialog", "stat": "none", "dialog_only": True, "target_npc": game.npcs[0].id})

    game, *_ = turn.process_turn(provider, game, "I whisper to Mira", stream=None)

    prompt = _last_narrator_prompt(provider)
    assert game.game_over
    for told in ("Dying: out of time", "follow-up move Face Death: MISS", "you are dead"):
        assert f"<consequence>{told}</consequence>" in prompt
    assert "FINAL_SCENE" in prompt


def test_turn_consequences_applied_on_miss(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.mechanics.move_outcome import resolve_move_outcome
    from tests._helpers import record_price_tables

    rolled = record_price_tables(monkeypatch)
    game = _make_game()

    result = resolve_move_outcome(game, "adventure/face_danger", "MISS", target_npc_id=None, match=False)

    assert rolled == [eng().pay_the_price.oracle_path]
    assert result.consequences


def test_scene_test_produces_three_types(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.mechanics.scene import check_scene

    game = _make_game()
    game.world.chaos_factor = 9

    def scene_type(roll: int) -> str:
        game.narrative.keyed_scenes = []
        fix_dice(monkeypatch, roll)
        return check_scene(game).scene_type

    assert [scene_type(roll) for roll in (10, 9, 8)] == ["expected", "altered", "interrupt"]


def test_dialog_prompt_contains_world_and_character(stub_engine: None) -> None:
    from straightjacket.engine.prompt_dialog import build_dialog_prompt

    game = _make_game()
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


def test_action_prompt_contains_result_and_position(stub_engine: None) -> None:
    from straightjacket.engine.prompt_action import build_action_prompt
    from straightjacket.engine.models import RollResult

    game = _make_game()
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


def test_narrator_system_prompt_includes_constraints(stub_engine: None) -> None:
    from straightjacket.engine.prompt_blocks import get_narrator_system

    game = _make_game()
    game.preferences.content_lines = "no spiders"

    system, cached_prefix = get_narrator_system(game)

    assert "<world>" in system
    assert "<player>" in system
    assert "spiders" in system
    assert system.startswith(cached_prefix)
    assert "spiders" in cached_prefix
    assert "<character_state" not in cached_prefix


def test_correction_brain_parses_response(stub_engine: None) -> None:
    from straightjacket.engine.correction.analysis import call_correction_brain

    provider = MockProvider()
    game = _make_game()

    snap = game.snapshot()
    snap.player_input = "I attack the guard"
    brain = make_brain_result(move="combat/strike", stat="iron", player_intent="Attack the guard")

    result = call_correction_brain(
        provider, game, "I didn't want to attack, just talk", snap, brain, "You swing your sword..."
    )

    assert "correction_source" in result
    assert result["correction_source"] in ("input_misread", "state_error")


def test_momentum_burn_upgrades_result() -> None:
    from straightjacket.engine.mechanics import can_burn_momentum
    from straightjacket.engine.models import RollResult

    game = _make_game()
    game.resources.momentum = 7

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
    from straightjacket.engine.story_state import get_current_act

    from straightjacket.engine.models import StoryBlueprint

    game = _make_game()
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


def test_correction_state_ops_npc_edit(stub_engine: None) -> None:
    from straightjacket.engine.correction.ops import apply_correction_ops

    game = _make_game()
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


def test_correction_state_ops_npc_rename(stub_engine: None) -> None:
    from straightjacket.engine.correction.ops import apply_correction_ops

    game = _make_game()

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


def test_correction_state_ops_location_edit(stub_engine: None) -> None:
    from straightjacket.engine.correction.ops import apply_correction_ops

    game = _make_game()

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


def test_correction_state_ops_npc_split(stub_engine: None) -> None:
    from straightjacket.engine.correction.ops import apply_correction_ops

    game = _make_game()
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
    stub_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import ops

    warnings: list[str] = []
    monkeypatch.setattr(ops, "log", lambda msg, level="info": warnings.append(msg) if level == "warning" else None)
    game = _make_game()
    ops.apply_correction_ops(game, [_op("npc_edit", npc_id="npc_1", fields={"name": " ", "agenda": "hide"})])
    assert (game.npcs[0].name, game.npcs[0].agenda) == ("Mira", "hide")
    assert warnings == ["[Correction] npc_edit: Mira keeps its name, the analysis gave an empty one"]


def test_a_correction_that_marks_an_npc_dead_leaves_the_description_whole(stub_engine: None) -> None:
    from straightjacket.engine.correction.ops import apply_correction_ops

    game = _make_game()
    game.npcs[0].description = "A tall woman who guards the totem of the dead king"
    apply_correction_ops(game, [_op("npc_edit", npc_id="npc_1", fields={"status": "deceased"})])
    assert game.npcs[0].status == "deceased"
    assert game.npcs[0].description == "A tall woman who guards the totem of the dead king"


def test_a_split_without_a_name_rolls_one_and_numbers_the_npc(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import ops

    monkeypatch.setattr(ops, "roll_oracle_name", lambda game: "Bren Hollow")
    game = _make_game()
    game.npcs[0].last_location = "Abandoned Library"
    ops.apply_correction_ops(game, [_op("npc_split", npc_id="npc_1")])
    twin = game.npcs[-1]
    assert (twin.id, twin.name, twin.name_rolled, twin.description) == ("npc_2", "Bren Hollow", True, "")
    assert twin.last_location == "Abandoned Library"


@pytest.mark.parametrize(
    "op",
    [
        _op("npc_edit"),
        _op("npc_split"),
        _op("npc_merge", npc_id="npc_1", merge_source_id="npc_1"),
        _op("location_edit", value=""),
        _op("scene_context"),
        _op("time_edit", value="teatime"),
        _op("backstory_append"),
    ],
)
def test_an_op_the_engine_cannot_apply_is_reported_and_changes_nothing(
    stub_engine: None, monkeypatch: pytest.MonkeyPatch, op: dict[str, object]
) -> None:
    from straightjacket.engine.correction import ops

    warnings: list[str] = []
    monkeypatch.setattr(ops, "log", lambda msg, level="info": warnings.append(msg) if level == "warning" else None)
    game = _make_game()
    before = game.to_dict()
    ops.apply_correction_ops(game, [op])
    assert game.to_dict() == before
    [warning] = warnings
    assert warning.startswith(f"[Correction] {op['op']} skipped: ")


def test_every_correction_op_has_a_handler(load_engine: None) -> None:
    from straightjacket.engine.correction.ops import _OP_HANDLERS
    from straightjacket.engine.engine_loader import eng

    assert list(_OP_HANDLERS) == eng().correction.ops


def test_description_match_catches_identity_reveal(stub_engine: None) -> None:
    from straightjacket.engine.npc.lifecycle import description_match_existing_npc

    game = _make_game()

    match = description_match_existing_npc(
        game,
        "The archivist with ink-stained hands and spectacles",
        "mysterious_stranger",
    )
    assert match is not None
    assert match.name == "Mira"


def test_description_match_rejects_short_descriptions(stub_engine: None) -> None:
    from straightjacket.engine.npc.lifecycle import description_match_existing_npc

    game = _make_game()
    match = description_match_existing_npc(game, "Short", "stranger")
    assert match is None


def test_merge_npc_identity_updates_clock_owner(stub_engine: None) -> None:
    from straightjacket.engine.npc.lifecycle import merge_npc_identity

    game = _make_game()
    game.world.clocks = [
        make_clock(name="Mira's scheme", clock_type="scheme", owner_kind="npc", owner_id="Mira"),
    ]
    npc = game.npcs[0]
    merge_npc_identity(npc, "Captain Voss", game=game)
    assert game.world.clocks[0].owner_id == "Captain Voss"


def test_correction_state_ops_npc_merge(stub_engine: None) -> None:
    from straightjacket.engine.correction.ops import apply_correction_ops

    game = _make_game()
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


def test_chapter_about_npc_id_remap(stub_engine: None) -> None:
    npc_a = make_npc(id="npc_1", name="Kira", memory=[make_memory(scene=3, event="trusts Borin", about_npc="npc_2")])
    npc_b = make_npc(id="npc_2", name="Borin", memory=[make_memory(scene=3, event="suspects Kira", about_npc="npc_1")])

    from straightjacket.engine.npc import next_npc_id

    game = _make_game()
    game.npcs = []
    returning = [npc_a, npc_b]

    id_remap = {}
    new_names = set()
    for old_npc in returning:
        old_id = old_npc.id
        fresh_id = next_npc_id(game)
        id_remap[old_id] = fresh_id
        old_npc.id = fresh_id
        game.npcs.append(old_npc)
        new_names.add(old_npc.name.lower())

    if id_remap:
        for npc in game.npcs:
            for mem in npc.memory:
                if mem.about_npc and mem.about_npc in id_remap:
                    mem.about_npc = id_remap[mem.about_npc]

    kira = next(n for n in game.npcs if n.name == "Kira")
    borin = next(n for n in game.npcs if n.name == "Borin")

    assert kira.memory[0].about_npc == borin.id

    assert borin.memory[0].about_npc == kira.id


if __name__ == "__main__":
    tests = [(name, obj) for name, obj in globals().items() if name.startswith("test_") and callable(obj)]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS: {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {name}: {e}")
            import traceback

            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {passed + failed}")
    sys.exit(1 if failed else 0)


def test_dialog_turn_runs_npc_agency_on_interval_scene(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.game.turn import process_turn

    provider = MockProvider()
    original_create = provider.create_message

    def dialog_brain(spec: AICallSpec) -> AIResponse:
        schema = spec.json_schema
        if schema and "move" in schema["properties"]:
            return AIResponse(
                content=json.dumps(
                    {
                        "type": "action",
                        "move": "dialog",
                        "stat": "none",
                        "approach": "",
                        "target_npc": "npc_1",
                        "dialog_only": True,
                        "player_intent": "I talk to Mira",
                        "world_addition": None,
                        "location_change": None,
                        "track_name": None,
                        "track_rank": None,
                        "target_track": None,
                        "target_clock": None,
                        "bonus_id": None,
                        "undetermined_facts": [],
                        "boasts": [],
                    }
                ),
                usage={"input_tokens": 100, "output_tokens": 50},
            )
        return original_create(spec)

    provider.create_message = dialog_brain
    game = _make_game()
    for npc in game.npcs:
        npc.status = "active"
        npc.agenda = "Keep the archive sealed"
    game.narrative.scene_count = eng().pacing.npc_agency_interval - 1
    process_turn(provider, game, "I talk to Mira", stream=None)
    prompts = [
        message["content"]
        for call in provider.calls
        if not call["json_schema"]
        for message in call["messages"]
        if isinstance(message["content"], str)
    ]
    assert any("<npc_agency>" in prompt for prompt in prompts)
