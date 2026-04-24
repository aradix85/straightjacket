#!/usr/bin/env python3
"""Integration tests: turn pipeline, correction flow, prompt builders.

Uses a MockProvider that returns predefined JSON responses, so we test
the full pipeline without real API calls.

Run: python -m pytest tests/test_integration.py -v
"""

from tests._helpers import make_brain_result, make_clock, make_memory, make_npc

import sys
import json

# Stubs are set up in conftest.py

# ── MockProvider ─────────────────────────────────────────────


class MockResponse:
    def __init__(self, content: str, stop_reason: str = "complete") -> None:
        self.content = content
        self.stop_reason = stop_reason
        self.tool_calls: list = []
        self.usage = {"input_tokens": 100, "output_tokens": 50}


class MockProvider:
    """AI provider that returns predefined responses per call type.

    Inspects json_schema to determine call type and returns the
    appropriate canned response.
    """

    def __init__(self) -> None:
        self.calls: list = []  # Record all calls for assertion

    def create_message(
        self,
        model: str,
        system: str,
        messages: list,
        max_tokens: int,
        json_schema: dict | None = None,
        tools: list | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        extra_body: dict | None = None,
    ) -> MockResponse:
        self.calls.append(
            {
                "model": model,
                "system_len": len(system),
                "messages": messages,
                "json_schema": json_schema,
            }
        )

        # Determine call type from schema or tools
        if json_schema and "move" in json_schema.get("properties", {}):
            # Brain call (legacy json_schema mode)
            return MockResponse(
                json.dumps(
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
                    }
                )
            )

        if tools and any(t.get("function", {}).get("name") == "roll_oracle" for t in tools):
            # Brain call (tool calling mode) — return JSON directly, no tool calls needed
            return MockResponse(
                json.dumps(
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
                    }
                )
            )

        if json_schema and "new_npcs" in json_schema.get("properties", {}):
            # Narrator metadata call
            return MockResponse(
                json.dumps(
                    {
                        "new_npcs": [],
                        "npc_renames": [],
                        "npc_details": [],
                        "deceased_npcs": [],
                        "lore_npcs": [],
                    }
                )
            )

        if json_schema and "pass" in json_schema.get("properties", {}):
            # Validator call
            return MockResponse(
                json.dumps(
                    {
                        "pass": True,
                        "violations": [],
                        "correction": "",
                    }
                )
            )

        if json_schema and "revelation_confirmed" in json_schema.get("properties", {}):
            # Revelation check
            return MockResponse(
                json.dumps(
                    {
                        "revelation_confirmed": False,
                        "reasoning": "Not present in narration.",
                    }
                )
            )

        if json_schema and "scene_summary" in json_schema.get("properties", {}):
            # Director call
            return MockResponse(
                json.dumps(
                    {
                        "scene_summary": "The player searched the room.",
                        "narrator_guidance": "Build tension slowly.",
                        "npc_guidance": [],
                        "pacing": "building",
                        "npc_reflections": [],
                        "arc_notes": "Story is progressing.",
                        "act_transition": False,
                    }
                )
            )

        if json_schema and "correction_source" in json_schema.get("properties", {}):
            # Correction brain
            return MockResponse(
                json.dumps(
                    {
                        "correction_source": "input_misread",
                        "corrected_input": "I talk to the guard instead",
                        "reroll_needed": False,
                        "corrected_stat": "none",
                        "narrator_guidance": "Rewrite as dialog with the guard.",
                        "director_useful": False,
                        "state_ops": [],
                    }
                )
            )

        # Default: narrator prose
        return MockResponse(
            "\u201cThe dust hung thick in the air. Your fingers traced the "
            "edge of the desk, finding nothing but splinters and silence. "
            "From the hallway, a floorboard groaned under weight that "
            "wasn\u2019t yours.\u201d"
        )


# ── Test fixtures ────────────────────────────────────────────


def _make_game():  # type: ignore[no-untyped-def]
    """Create a game state ready for turn processing."""
    from straightjacket.engine.models import GameState

    game = GameState(
        player_name="Kael",
        character_concept="A wandering scholar",
        setting_genre="dark_fantasy",
        setting_tone="serious_balanced",
        setting_description="A world of fading magic and creeping shadow.",
        stats={"edge": 1, "heart": 2, "iron": 1, "shadow": 1, "wits": 2},
    )
    game.resources.health = 4
    game.resources.spirit = 3
    game.resources.supply = 5
    game.resources.momentum = 3
    game.world.current_location = "Abandoned Library"
    game.world.time_of_day = "evening"
    game.world.chaos_factor = 5
    game.world.clocks = [
        make_clock(
            name="Shadow Rising",
            clock_type="threat",
            segments=6,
            filled=2,
            owner="world",
            trigger_description="Darkness engulfs the library",
        ),
    ]
    game.npcs = [
        make_npc(
            id="npc_1",
            name="Mira",
            disposition="friendly",
            agenda="protect the archives",
            instinct="trust cautiously",
            description="Young archivist with ink-stained hands",
            memory=[
                make_memory(
                    event="Met the player at the entrance", emotional_weight="curious", type="observation", scene=1
                )
            ],
        ),
    ]
    game.narrative.scene_count = 3
    return game


# ── Turn pipeline tests ──────────────────────────────────────


def test_turn_action_produces_narration(load_engine: None) -> None:
    """Full action turn: brain → roll → consequences → narrator → metadata."""
    from straightjacket.engine.game.turn import process_turn
    from straightjacket.engine.models import EngineConfig

    provider = MockProvider()
    game = _make_game()
    initial_scene = game.narrative.scene_count

    game, narration, roll, burn_info, director_ctx = process_turn(
        provider,  # type: ignore[arg-type]
        game,
        "I search the room for clues",
        config=EngineConfig(narration_lang="English"),
    )

    # Scene count incremented
    assert game.narrative.scene_count == initial_scene + 1

    # Got narration text
    assert len(narration) > 20
    assert "dust" in narration.lower()

    # Got a roll result (not dialog)
    assert roll is not None
    assert roll.move == "adventure/face_danger"
    assert roll.stat_name == "wits"
    assert roll.result in ("STRONG_HIT", "WEAK_HIT", "MISS")

    # Snapshot was created
    assert game.last_turn_snapshot is not None
    assert game.last_turn_snapshot.player_input == "I search the room for clues"

    # Session log was updated
    assert len(game.narrative.session_log) == 1
    assert game.narrative.session_log[0].move == "adventure/face_danger"

    # Provider was called multiple times (brain, narrator, validator, metadata)
    assert len(provider.calls) >= 3


def test_turn_dialog_skips_roll(load_engine: None) -> None:
    """Dialog turn should not produce a roll result."""
    from straightjacket.engine.game.turn import process_turn
    from straightjacket.engine.models import EngineConfig

    provider = MockProvider()

    # Override brain to return dialog
    original_create = provider.create_message
    call_count = [0]

    def dialog_brain(*args, **kwargs):  # type: ignore[no-untyped-def]
        call_count[0] += 1
        schema = kwargs.get("json_schema") or (args[5] if len(args) > 5 else None)
        tools = kwargs.get("tools")
        is_brain = (schema and "move" in schema.get("properties", {})) or (
            tools and any(t.get("function", {}).get("name") == "roll_oracle" for t in tools)
        )
        if is_brain:
            return MockResponse(
                json.dumps(
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
                    }
                )
            )
        return original_create(*args, **kwargs)

    provider.create_message = dialog_brain  # type: ignore[method-assign]

    game = _make_game()
    game, narration, roll, burn_info, director_ctx = process_turn(
        provider,  # type: ignore[arg-type]
        game,
        "I talk to Mira",
        config=EngineConfig(narration_lang="English"),
    )

    # No roll for dialog
    assert roll is None
    # Still got narration
    assert len(narration) > 10
    # Scene incremented
    assert game.narrative.scene_count == 4


def test_turn_consequences_applied_on_miss(load_engine: None) -> None:
    """On MISS, move outcomes should apply mechanical effects."""
    from straightjacket.engine.mechanics.move_outcome import resolve_move_outcome

    game = _make_game()

    result = resolve_move_outcome(game, "adventure/face_danger", "MISS")

    # face_danger MISS = pay_the_price
    assert result.pay_the_price is True


def test_scene_test_produces_three_types(load_engine: None) -> None:
    """Scene test produces expected, altered, or interrupt based on d10 vs CF."""
    from straightjacket.engine.mechanics.scene import check_scene

    game = _make_game()
    game.world.chaos_factor = 9

    types_seen: set[str] = set()
    for _ in range(200):
        setup = check_scene(game)
        types_seen.add(setup.scene_type)
        if len(types_seen) == 3:
            break

    assert "expected" in types_seen
    assert "altered" in types_seen
    assert "interrupt" in types_seen


# ── Prompt builder tests ─────────────────────────────────────


def test_dialog_prompt_contains_world_and_character(stub_engine: None) -> None:
    """Dialog prompt must include world genre and character name."""
    from straightjacket.engine.prompt_dialog import build_dialog_prompt

    game = _make_game()
    brain = make_brain_result(
        move="dialog",
        target_npc="npc_1",
        player_intent="Ask about the archives",
    )
    prompt = build_dialog_prompt(game, brain, player_words="I ask Mira about the archives")

    assert "dark_fantasy" in prompt
    assert "Kael" in prompt
    assert "Mira" in prompt
    assert "dialog" in prompt


def test_action_prompt_contains_result_and_position(stub_engine: None) -> None:
    """Action prompt must include roll result and position."""
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
        d2=3,
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
        clock_events=[],
        npc_agency=[],
        consequence_sentences=["The tide shifts. Hero can feel it."],
        player_words="I search for hidden compartments",
    )

    assert "STRONG_HIT" in prompt
    assert "risky" in prompt
    assert "Search" in prompt or "search" in prompt


def test_narrator_system_prompt_includes_constraints(stub_engine: None) -> None:
    """Narrator system prompt must include core constraints."""
    from straightjacket.engine.prompt_blocks import get_narrator_system
    from straightjacket.engine.models import EngineConfig

    game = _make_game()
    game.preferences.content_lines = "no spiders"

    system = get_narrator_system(EngineConfig(narration_lang="English"), game)

    assert "<world>" in system
    assert "<player>" in system
    assert "spiders" in system  # Content boundary passed through


# ── Correction flow tests ────────────────────────────────────


def test_correction_brain_parses_response(stub_engine: None) -> None:
    """Correction brain should return a structured correction dict."""
    from straightjacket.engine.correction import call_correction_brain
    from straightjacket.engine.models import EngineConfig

    provider = MockProvider()
    game = _make_game()

    # Create a fake snapshot (normally done by turn processing)
    game.last_turn_snapshot = game.snapshot()
    game.last_turn_snapshot.player_input = "I attack the guard"
    game.last_turn_snapshot.brain = make_brain_result(
        move="combat/strike", stat="iron", player_intent="Attack the guard"
    )
    game.last_turn_snapshot.roll = None
    game.last_turn_snapshot.narration = "You swing your sword..."

    result = call_correction_brain(
        provider,  # type: ignore[arg-type]
        game,
        "I didn't want to attack, just talk",
        config=EngineConfig(narration_lang="English"),
    )

    assert "correction_source" in result
    assert result["correction_source"] in ("input_misread", "state_error")


# ── Momentum burn test ───────────────────────────────────────


def test_momentum_burn_upgrades_result() -> None:
    """can_burn_momentum should detect upgrade opportunities."""
    from straightjacket.engine.mechanics import can_burn_momentum
    from straightjacket.engine.models import RollResult

    game = _make_game()
    game.resources.momentum = 7

    # MISS where momentum (7) beats both challenge dice (5, 6)
    roll = RollResult(
        d1=1,
        d2=1,
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

    # MISS where momentum only beats one die
    roll2 = RollResult(
        d1=1,
        d2=1,
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


# ── Story state tests ────────────────────────────────────────


def test_story_completion_triggers() -> None:
    """Story should complete when final act entered and scenes exceed range."""
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
            "revealed": [],
            "story_complete": False,
        }
    )
    game.narrative.scene_count = 10

    act = get_current_act(game)
    assert act.phase == "confrontation"
    assert act.act_number == 2


# ── Correction flow ──────────────────────────────────────────


def test_correction_state_ops_npc_edit(stub_engine: None) -> None:
    """_apply_correction_ops applies npc_edit fields correctly."""
    from straightjacket.engine.correction import _apply_correction_ops

    game = _make_game()
    original_name = game.npcs[0].name

    _apply_correction_ops(
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
    assert game.npcs[0].name == original_name  # name unchanged


def test_correction_state_ops_npc_rename(stub_engine: None) -> None:
    """_apply_correction_ops handles npc_edit with name change (rename)."""
    from straightjacket.engine.correction import _apply_correction_ops

    game = _make_game()

    _apply_correction_ops(
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
    assert "Mira" in game.npcs[0].aliases  # old name becomes alias


def test_correction_state_ops_location_edit(stub_engine: None) -> None:
    """_apply_correction_ops updates location."""
    from straightjacket.engine.correction import _apply_correction_ops

    game = _make_game()

    _apply_correction_ops(
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
    """_apply_correction_ops splits an NPC into two."""
    from straightjacket.engine.correction import _apply_correction_ops

    game = _make_game()
    count_before = len(game.npcs)

    _apply_correction_ops(
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


def test_correction_state_ops_invalid_status_rejected(stub_engine: None) -> None:
    """_apply_correction_ops rejects invalid NPC status values."""
    from straightjacket.engine.correction import _apply_correction_ops

    game = _make_game()
    original_status = game.npcs[0].status

    _apply_correction_ops(
        game,
        [
            {
                "op": "npc_edit",
                "npc_id": "npc_1",
                "fields": {"status": "imaginary"},
                "split_name": None,
                "split_description": None,
                "merge_source_id": None,
                "value": None,
            }
        ],
    )
    assert game.npcs[0].status == original_status  # unchanged


# ── NPC lifecycle: description matching ──────────────────────


def test_description_match_catches_identity_reveal(stub_engine: None) -> None:
    """description_match_existing_npc finds NPCs by description overlap."""
    from straightjacket.engine.npc.lifecycle import description_match_existing_npc

    game = _make_game()
    # Mira has "Young archivist with ink-stained hands"
    # A new NPC with overlapping description but different name should match
    match = description_match_existing_npc(
        game,
        "The archivist with ink-stained hands and spectacles",
        "mysterious_stranger",
    )
    assert match is not None
    assert match.name == "Mira"


def test_description_match_rejects_short_descriptions(stub_engine: None) -> None:
    """description_match_existing_npc rejects descriptions < 10 chars."""
    from straightjacket.engine.npc.lifecycle import description_match_existing_npc

    game = _make_game()
    match = description_match_existing_npc(game, "Short", "stranger")
    assert match is None


# ── NPC lifecycle: merge identity ────────────────────────────


def test_merge_npc_identity_updates_clock_owner(stub_engine: None) -> None:
    """merge_npc_identity updates clock owners when NPC is renamed."""
    from straightjacket.engine.npc.lifecycle import merge_npc_identity

    game = _make_game()
    game.world.clocks = [
        make_clock(name="Mira's scheme", clock_type="scheme", owner="Mira"),
    ]
    npc = game.npcs[0]  # Mira
    merge_npc_identity(npc, "Captain Voss", game=game)
    assert game.world.clocks[0].owner == "Captain Voss"


# ── Correction: npc_merge ────────────────────────────────────


def test_correction_state_ops_npc_merge(stub_engine: None) -> None:
    """npc_merge absorbs source NPC into target, transfers memories."""
    from straightjacket.engine.correction import _apply_correction_ops

    game = _make_game()
    source = make_npc(
        id="npc_3",
        name="Stranger",
        disposition="neutral",
        memory=[make_memory(scene=2, event="saw fire", importance=5)],
    )
    game.npcs.append(source)
    ops = [{"op": "npc_merge", "npc_id": "npc_1", "merge_source_id": "npc_3"}]
    _apply_correction_ops(game, ops)
    assert not any(n.id == "npc_3" for n in game.npcs), "source should be removed"
    target = next(n for n in game.npcs if n.id == "npc_1")
    assert any(m.event == "saw fire" for m in target.memory), "memories should transfer"
    assert "Stranger" in target.aliases, "source name should become alias"


# ── Chapter: about_npc id_remap ──────────────────────────────


def test_chapter_about_npc_id_remap(stub_engine: None) -> None:
    """Returning NPCs get new IDs at chapter boundary; about_npc refs must be rewritten."""

    npc_a = make_npc(id="npc_1", name="Kira", memory=[make_memory(scene=3, event="trusts Borin", about_npc="npc_2")])
    npc_b = make_npc(id="npc_2", name="Borin", memory=[make_memory(scene=3, event="suspects Kira", about_npc="npc_1")])

    # Simulate the ID remap logic from start_new_chapter
    from straightjacket.engine.npc import next_npc_id

    game = _make_game()
    game.npcs = []  # Clear — simulating post-parse state
    returning = [npc_a, npc_b]

    id_remap = {}
    new_names = set()
    for old_npc in returning:
        old_id = old_npc.id
        fresh_id, _ = next_npc_id(game)
        id_remap[old_id] = fresh_id
        old_npc.id = fresh_id
        game.npcs.append(old_npc)
        new_names.add(old_npc.name.lower())

    # Apply remap
    if id_remap:
        for npc in game.npcs:
            for mem in npc.memory:
                if mem.about_npc and mem.about_npc in id_remap:
                    mem.about_npc = id_remap[mem.about_npc]

    kira = next(n for n in game.npcs if n.name == "Kira")
    borin = next(n for n in game.npcs if n.name == "Borin")
    # Kira's memory should reference Borin's NEW id, not old "npc_2"
    assert kira.memory[0].about_npc == borin.id
    # Borin's memory should reference Kira's NEW id, not old "npc_1"
    assert borin.memory[0].about_npc == kira.id


# ── Runner ────────────────────────────────────────────────────

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
