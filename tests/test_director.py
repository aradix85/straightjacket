#!/usr/bin/env python3
"""Tests for director.py: guidance application, reflection processing, act transitions."""

from straightjacket.engine import engine_loader, emotions_loader
from straightjacket.engine.config_loader import _ConfigNode
from straightjacket.engine.models import (
    GameState,
    MemoryEntry,
    NpcData,
    SceneLogEntry,
    StoryAct,
    StoryBlueprint,
)


def _stub() -> None:
    engine_loader._eng = _ConfigNode(
        {
            "bonds": {"start": 0, "max": 4},
            "npc": {
                "max_active": 12,
                "reflection_threshold": 30,
                "max_memory_entries": 25,
                "max_observations": 15,
                "max_reflections": 8,
                "memory_recency_decay": 0.92,
            },
            "pacing": {"director_interval": 3, "window_size": 5, "intense_threshold": 3, "calm_threshold": 2},
        },
        "engine",
    )
    emotions_loader._data = {
        "importance": {"neutral": 2, "reflective": 4, "curious": 3, "conflicted": 6},
        "keyword_boosts": {},
        "disposition_map": {"neutral": "neutral", "friendly": "friendly"},
    }


def _game() -> GameState:
    game = GameState(player_name="Hero")
    game.narrative.scene_count = 6
    game.narrative.session_log.append(SceneLogEntry(scene=6, summary="Last scene"))
    game.npcs = [
        NpcData(
            id="npc_1",
            name="Kira",
            disposition="friendly",
            bond=2,
            agenda="protect archives",
            instinct="trust cautiously",
            description="Young archivist.",
            needs_reflection=True,
            importance_accumulator=35,
            memory=[MemoryEntry(scene=5, event="Helped player", importance=5)],
        ),
        NpcData(
            id="npc_2",
            name="Borin",
            disposition="neutral",
            bond=0,
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


# ── apply_director_guidance: empty guidance resets flags ─────


def test_empty_guidance_resets_reflection_flags() -> None:
    _stub()
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    assert game.npcs[0].needs_reflection is True
    apply_director_guidance(game, {})
    assert game.npcs[0].needs_reflection is False
    assert game.npcs[0].importance_accumulator == 0


# ── apply_director_guidance: stores guidance ─────────────────


def test_stores_narrator_guidance() -> None:
    _stub()
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    apply_director_guidance(
        game,
        {
            "narrator_guidance": "Build tension slowly.",
            "npc_guidance": {"npc_1": "Kira should test loyalty."},
            "pacing": "building",
            "arc_notes": "Story progressing.",
        },
    )
    dg = game.narrative.director_guidance
    assert dg.narrator_guidance == "Build tension slowly."
    assert dg.npc_guidance == {"npc_1": "Kira should test loyalty."}
    assert dg.pacing == "building"


# ── apply_director_guidance: scene summary ───────────────────


def test_enriches_session_log_with_summary() -> None:
    _stub()
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    apply_director_guidance(game, {"scene_summary": "A tense exchange."})
    assert game.narrative.session_log[-1].rich_summary == "A tense exchange."


# ── apply_director_guidance: reflections ─────────────────────


def test_reflection_adds_memory_and_resets_flag() -> None:
    _stub()
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


def test_reflection_rejects_truncated() -> None:
    _stub()
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    mem_before = len(game.npcs[0].memory)
    apply_director_guidance(
        game,
        {
            "npc_reflections": [
                {
                    "npc_id": "npc_1",
                    "reflection": "Kira is beginning to tru",  # truncated, no sentence-ending punctuation
                    "tone_key": "conflicted",
                }
            ],
        },
    )
    # Truncated reflection rejected — no new memory
    assert len(game.npcs[0].memory) == mem_before
    # But flag still gets reset via fallback
    assert game.npcs[0].needs_reflection is False


def test_reflection_fills_empty_agenda_instinct() -> None:
    _stub()
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


def test_reflection_does_not_overwrite_existing_agenda() -> None:
    _stub()
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
                    "agenda": "new agenda",  # Should NOT overwrite — Kira already has one
                }
            ],
        },
    )
    assert game.npcs[0].agenda == "protect archives"


def test_reflection_updates_stale_agenda() -> None:
    _stub()
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


def test_reflection_updates_arc() -> None:
    _stub()
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


def test_reflection_rejects_too_long_arc() -> None:
    _stub()
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    game.npcs[0].arc = "Old arc."
    apply_director_guidance(
        game,
        {
            "npc_reflections": [
                {
                    "npc_id": "npc_1",
                    "reflection": "Kira evolves.",
                    "tone_key": "conflicted",
                    "updated_arc": "x" * 301,
                }
            ],
        },
    )
    assert game.npcs[0].arc == "Old arc."


def test_reflection_updates_description() -> None:
    _stub()
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


def test_reflection_strips_name_prefix_from_description() -> None:
    _stub()
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


def test_reflection_rejects_too_long_description() -> None:
    _stub()
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


def test_reflection_rejects_truncated_description() -> None:
    _stub()
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
                    "updated_description": "Incomplete desc without",  # no sentence-ending punctuation
                }
            ],
        },
    )
    assert game.npcs[0].description == "Original description here."


# ── apply_director_guidance: act transitions ─────────────────


def test_act_transition_marks_blueprint() -> None:
    _stub()
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    game.narrative.story_blueprint = _blueprint()
    apply_director_guidance(game, {"act_transition": True})
    assert "act_0" in game.narrative.story_blueprint.triggered_transitions


def test_act_transition_backfills_skipped_acts() -> None:
    _stub()
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    game.narrative.scene_count = 12
    bp = _blueprint()
    bp.triggered_transitions = []  # Nothing triggered yet
    game.narrative.story_blueprint = bp
    apply_director_guidance(game, {"act_transition": True})
    # At scene 12 with no transitions, current act is confrontation (act_1)
    # Back-fill should add act_0, then act_1
    assert "act_0" in bp.triggered_transitions
    assert "act_1" in bp.triggered_transitions


def test_act_transition_ignores_final_act() -> None:
    _stub()
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    game.narrative.scene_count = 18
    bp = _blueprint()
    bp.triggered_transitions = ["act_0", "act_1"]
    game.narrative.story_blueprint = bp
    apply_director_guidance(game, {"act_transition": True})
    # Final act (act_2) should NOT be added
    assert "act_2" not in bp.triggered_transitions


# ── apply_director_guidance: stale reflection reset ──────────


def test_unreflected_npcs_get_reset() -> None:
    _stub()
    from straightjacket.engine.director import apply_director_guidance

    game = _game()
    # Only reflect Kira, not Borin
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
    # Borin was not reflected — should still get reset
    assert game.npcs[1].needs_reflection is False
    assert game.npcs[1].importance_accumulator == 0


# ── should_call_director ─────────────────────────────────────


def test_should_call_on_miss() -> None:
    _stub()
    from straightjacket.engine.director import should_call_director

    game = _game()
    assert should_call_director(game, roll_result="MISS") == "miss"


def test_should_call_on_chaos() -> None:
    _stub()
    from straightjacket.engine.director import should_call_director

    game = _game()
    assert should_call_director(game, chaos_used=True) == "chaos"


def test_should_call_on_reflection_needed() -> None:
    _stub()
    from straightjacket.engine.director import should_call_director

    game = _game()
    reason = should_call_director(game)
    assert reason is not None
    assert "reflection" in reason


def test_should_call_on_interval() -> None:
    _stub()
    from straightjacket.engine.director import should_call_director

    game = _game()
    game.npcs = []  # No reflection triggers
    game.narrative.scene_count = 9  # divisible by director_interval=3
    assert should_call_director(game) == "interval"


def test_should_call_returns_none_when_no_trigger() -> None:
    _stub()
    from straightjacket.engine.director import should_call_director

    game = _game()
    game.npcs = []
    game.narrative.scene_count = 7  # not divisible by 3
    assert should_call_director(game) is None


# ── reset_stale_reflection_flags ─────────────────────────────


def test_reset_stale_reflection_flags() -> None:
    _stub()
    from straightjacket.engine.director import reset_stale_reflection_flags

    game = _game()
    reset_stale_reflection_flags(game)
    for npc in game.npcs:
        assert npc.needs_reflection is False
        assert npc.importance_accumulator == 0
