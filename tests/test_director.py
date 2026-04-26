from straightjacket.engine.models import (
    GameState,
    SceneLogEntry,
    StoryAct,
    StoryBlueprint,
)
from tests._helpers import make_game_state, make_memory, make_npc


def _game() -> GameState:
    game = make_game_state(player_name="Hero")
    game.narrative.scene_count = 6
    game.narrative.session_log.append(SceneLogEntry(scene=6, summary="Last scene", scene_type="expected"))
    game.npcs = [
        make_npc(
            id="npc_1",
            name="Kira",
            disposition="friendly",
            agenda="protect archives",
            instinct="trust cautiously",
            description="Young archivist.",
            needs_reflection=True,
            importance_accumulator=35,
            memory=[make_memory(scene=5, event="Helped player", importance=5)],
        ),
        make_npc(
            id="npc_2",
            name="Borin",
            disposition="neutral",
            agenda="",
            instinct="",
            needs_reflection=True,
            importance_accumulator=31,
        ),
    ]
    return game


def _blueprint() -> StoryBlueprint:
    return StoryBlueprint(
        central_conflict="Shadow rises",
        antagonist_force="Darkness",
        thematic_thread="Cost of survival",
        structure_type="3act",
        acts=[
            StoryAct(
                phase="setup",
                title="Gathering",
                scene_range=[1, 7],
                mood="mysterious",
                transition_trigger="Allies gathered",
            ),
            StoryAct(
                phase="confrontation",
                title="Darkness",
                scene_range=[8, 14],
                mood="tense",
                transition_trigger="Shadow revealed",
            ),
            StoryAct(
                phase="climax", title="Final", scene_range=[15, 20], mood="desperate", transition_trigger="Resolution"
            ),
        ],
    )


def test_empty_guidance_resets_reflection_flags(stub_all: None) -> None:
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    assert game.npcs[0].needs_reflection is True
    apply_director_guidance(game, {})
    assert game.npcs[0].needs_reflection is False
    assert game.npcs[0].importance_accumulator == 0


def test_stores_narrator_guidance(stub_all: None) -> None:
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    apply_director_guidance(
        game,
        {
            "narrator_guidance": "Build tension slowly.",
            "npc_guidance": {"npc_1": "Kira should test loyalty."},
            "arc_notes": "Story progressing.",
        },
    )
    dg = game.narrative.director_guidance
    assert dg.narrator_guidance == "Build tension slowly."
    assert dg.npc_guidance == {"npc_1": "Kira should test loyalty."}


def test_enriches_session_log_with_summary(stub_all: None) -> None:
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    apply_director_guidance(game, {"scene_summary": "A tense exchange."})
    assert game.narrative.session_log[-1].rich_summary == "A tense exchange."


def test_reflection_adds_memory_and_resets_flag(stub_all: None) -> None:
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    apply_director_guidance(
        game,
        {
            "npc_reflections": [
                {
                    "npc_id": "npc_1",
                    "reflection": "Kira is beginning to trust the player.",
                    "tone": "reluctant_trust",
                    "tone_key": "conflicted",
                }
            ],
        },
    )
    kira = game.npcs[0]
    assert kira.needs_reflection is False
    assert kira.importance_accumulator == 0
    assert kira.last_reflection_scene == 6
    ref = [m for m in kira.memory if m.type == "reflection"]
    assert len(ref) >= 1
    assert "trust" in ref[-1].event
    assert ref[-1].tone == "reluctant_trust"
    assert ref[-1].tone_key == "conflicted"


def test_reflection_rejects_truncated(stub_all: None) -> None:
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    mem_before = len(game.npcs[0].memory)
    apply_director_guidance(
        game,
        {
            "npc_reflections": [
                {
                    "npc_id": "npc_1",
                    "reflection": "Kira is beginning to tru",
                    "tone_key": "conflicted",
                }
            ],
        },
    )

    assert len(game.npcs[0].memory) == mem_before

    assert game.npcs[0].needs_reflection is False


def test_reflection_fills_empty_agenda_instinct(stub_all: None) -> None:
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    apply_director_guidance(
        game,
        {
            "npc_reflections": [
                {
                    "npc_id": "npc_2",
                    "reflection": "Borin is watching carefully.",
                    "tone_key": "neutral",
                    "agenda": "survive at any cost",
                    "instinct": "goes quiet when cornered",
                }
            ],
        },
    )
    borin = game.npcs[1]
    assert borin.agenda == "survive at any cost"
    assert borin.instinct == "goes quiet when cornered"


def test_reflection_does_not_overwrite_existing_agenda(stub_all: None) -> None:
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    apply_director_guidance(
        game,
        {
            "npc_reflections": [
                {
                    "npc_id": "npc_1",
                    "reflection": "Kira reconsiders her goals.",
                    "tone_key": "conflicted",
                    "agenda": "new agenda",
                }
            ],
        },
    )
    assert game.npcs[0].agenda == "protect archives"


def test_reflection_updates_stale_agenda(stub_all: None) -> None:
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    apply_director_guidance(
        game,
        {
            "npc_reflections": [
                {
                    "npc_id": "npc_1",
                    "reflection": "Kira shifts her priorities.",
                    "tone_key": "conflicted",
                    "updated_agenda": "find the truth",
                }
            ],
        },
    )
    assert game.npcs[0].agenda == "find the truth"


def test_reflection_updates_arc(stub_all: None) -> None:
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    apply_director_guidance(
        game,
        {
            "npc_reflections": [
                {
                    "npc_id": "npc_1",
                    "reflection": "Kira is conflicted.",
                    "tone_key": "conflicted",
                    "updated_arc": "Torn between loyalty and self-preservation.",
                }
            ],
        },
    )
    assert game.npcs[0].arc == "Torn between loyalty and self-preservation."


def test_reflection_updates_description(stub_all: None) -> None:
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    apply_director_guidance(
        game,
        {
            "npc_reflections": [
                {
                    "npc_id": "npc_1",
                    "reflection": "Kira has changed.",
                    "tone_key": "conflicted",
                    "updated_description": "Battle-scarred archivist with haunted eyes.",
                }
            ],
        },
    )
    assert "Battle-scarred" in game.npcs[0].description


def test_reflection_strips_name_prefix_from_description(stub_all: None) -> None:
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    apply_director_guidance(
        game,
        {
            "npc_reflections": [
                {
                    "npc_id": "npc_1",
                    "reflection": "Kira has changed.",
                    "tone_key": "conflicted",
                    "updated_description": "Kira: Battle-scarred archivist with haunted eyes.",
                }
            ],
        },
    )
    assert not game.npcs[0].description.startswith("Kira:")
    assert "Battle-scarred" in game.npcs[0].description


def test_reflection_rejects_too_long_description(stub_all: None) -> None:
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    game.npcs[0].description = "Original."
    apply_director_guidance(
        game,
        {
            "npc_reflections": [
                {
                    "npc_id": "npc_1",
                    "reflection": "Kira evolves.",
                    "tone_key": "conflicted",
                    "updated_description": "x" * 201,
                }
            ],
        },
    )
    assert game.npcs[0].description == "Original."


def test_reflection_rejects_truncated_description(stub_all: None) -> None:
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    game.npcs[0].description = "Original description here."
    apply_director_guidance(
        game,
        {
            "npc_reflections": [
                {
                    "npc_id": "npc_1",
                    "reflection": "Kira evolves.",
                    "tone_key": "conflicted",
                    "updated_description": "Incomplete desc without",
                }
            ],
        },
    )
    assert game.npcs[0].description == "Original description here."


def test_act_transition_marks_blueprint(stub_all: None) -> None:
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    game.narrative.scene_count = 7
    game.narrative.story_blueprint = _blueprint()
    apply_director_guidance(game, {"narrator_guidance": "proceed"})
    assert "act_0" in game.narrative.story_blueprint.triggered_transitions


def test_act_transition_backfills_skipped_acts(stub_all: None) -> None:
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    game.narrative.scene_count = 14
    bp = _blueprint()
    bp.triggered_transitions = []
    game.narrative.story_blueprint = bp
    apply_director_guidance(game, {"narrator_guidance": "proceed"})
    assert "act_0" in bp.triggered_transitions
    assert "act_1" in bp.triggered_transitions


def test_act_transition_ignores_final_act(stub_all: None) -> None:
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    game.narrative.scene_count = 20
    bp = _blueprint()
    bp.triggered_transitions = ["act_0", "act_1"]
    game.narrative.story_blueprint = bp
    apply_director_guidance(game, {})

    assert "act_2" not in bp.triggered_transitions


def test_unreflected_npcs_get_reset(stub_all: None) -> None:
    from straightjacket.engine.director import apply_director_guidance

    game = _game()

    apply_director_guidance(
        game,
        {
            "npc_reflections": [
                {
                    "npc_id": "npc_1",
                    "reflection": "Kira is evolving.",
                    "tone_key": "conflicted",
                }
            ],
        },
    )

    assert game.npcs[1].needs_reflection is False
    assert game.npcs[1].importance_accumulator == 31


def test_should_call_on_miss(stub_all: None) -> None:
    from straightjacket.engine.director import should_call_director

    game = _game()
    assert should_call_director(game, roll_result="MISS") == "miss"


def test_should_call_on_chaos(stub_all: None) -> None:
    from straightjacket.engine.director import should_call_director

    game = _game()
    assert should_call_director(game, chaos_used=True) == "chaos"


def test_should_call_on_reflection_needed(stub_all: None) -> None:
    from straightjacket.engine.director import should_call_director

    game = _game()
    reason = should_call_director(game)
    assert reason is not None
    assert "reflection" in reason


def test_should_call_on_interval(stub_all: None) -> None:
    from straightjacket.engine.director import should_call_director

    game = _game()
    game.npcs = []
    game.narrative.scene_count = 9
    assert should_call_director(game) == "interval"


def test_should_call_returns_none_when_no_trigger(stub_all: None) -> None:
    from straightjacket.engine.director import should_call_director

    game = _game()
    game.npcs = []
    game.narrative.scene_count = 7
    assert should_call_director(game) is None


def test_reset_stale_reflection_flags(stub_all: None) -> None:
    from straightjacket.engine.director import reset_stale_reflection_flags

    game = _game()

    acc_before = {npc.id: npc.importance_accumulator for npc in game.npcs}
    reset_stale_reflection_flags(game)
    for npc in game.npcs:
        assert npc.needs_reflection is False
        assert npc.importance_accumulator == acc_before[npc.id]


def test_run_deferred_director_applies_guidance(stub_all: None) -> None:
    import json

    from straightjacket.engine.game.director_runner import run_deferred_director
    from straightjacket.engine import prompt_loader
    from tests._mocks import MockProvider, make_test_game

    prompt_loader._prompts = None
    prompt_loader._ensure_loaded()

    provider = MockProvider(
        json.dumps(
            {
                "scene_summary": "Tense.",
                "narrator_guidance": "Build tension.",
                "npc_guidance": [],
                "pacing": "building",
                "npc_reflections": [],
                "arc_notes": "Progressing.",
                "act_transition": False,
            }
        )
    )
    game = make_test_game()
    game.narrative.session_log.append(SceneLogEntry(scene=5, summary="Last", scene_type="expected"))
    run_deferred_director(
        provider,
        game,
        {"narration": "Text.", "config": None},
    )
    assert game.narrative.director_guidance.narrator_guidance == "Build tension."


def test_run_deferred_director_survives_api_error(stub_all: None) -> None:
    from straightjacket.engine.game.director_runner import run_deferred_director
    from tests._mocks import MockProvider, make_test_game

    provider = MockProvider(fail=True)
    game = make_test_game()
    run_deferred_director(
        provider,
        game,
        {"narration": "text", "config": None},
    )
