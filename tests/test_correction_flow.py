#!/usr/bin/env python3
"""End-to-end correction flow tests.

One test per path: input_misread, state_error, momentum_burn.
Each walks the full pipeline — snapshot, restore, re-narrate, metadata,
session log — instead of testing individual assertions in isolation.

Run: python -m pytest tests/test_correction_flow.py -v
"""

import json

from straightjacket.engine import engine_loader
from straightjacket.engine.models import (
    BrainResult, EngineConfig, GameState, MemoryEntry,
    NarrationEntry, NpcData, RollResult, SceneLogEntry,
)


# ── MockProvider ─────────────────────────────────────────────

class MockResponse:
    def __init__(self, content, stop_reason="complete"):
        self.content = content
        self.stop_reason = stop_reason
        self.tool_calls = []
        self.usage = {"input_tokens": 100, "output_tokens": 50}


class MockProvider:
    def __init__(self, correction_source="input_misread"):
        self.calls = []
        self._correction_source = correction_source

    def create_message(self, model, system, messages, max_tokens,
                       json_schema=None, tools=None,
                       temperature=None, top_p=None, top_k=None):
        self.calls.append({"json_schema": json_schema})

        if json_schema and "correction_source" in json_schema.get("properties", {}):
            return MockResponse(json.dumps({
                "correction_source": self._correction_source,
                "corrected_input": "I talk to Mira instead",
                "reroll_needed": False,
                "corrected_stat": "none",
                "narrator_guidance": "Rewrite as peaceful dialog.",
                "director_useful": False,
                "state_ops": [{
                    "op": "npc_edit", "npc_id": "npc_1",
                    "split_name": None, "split_description": None,
                    "merge_source_id": None,
                    "fields": {"disposition": "loyal"},
                    "value": None,
                }] if self._correction_source == "state_error" else [],
            }))

        if json_schema and "move" in json_schema.get("properties", {}):
            return MockResponse(json.dumps({
                "type": "action", "move": "dialog", "stat": "none",
                "approach": "speaking gently",
                "target_npc": "npc_1", "dialog_only": True,
                "player_intent": "Talk to Mira",
                "world_addition": None, "position": "controlled",
                "effect": "standard", "dramatic_question": "",
                "location_change": None, "time_progression": "none",
            }))

        if json_schema and "scene_context" in json_schema.get("properties", {}):
            return MockResponse(json.dumps({
                "scene_context": "Talking with Mira.",
                "location_update": None, "time_update": None,
                "memory_updates": [], "new_npcs": [],
                "npc_renames": [], "npc_details": [],
                "deceased_npcs": [], "lore_npcs": [],
            }))

        if json_schema and "pass" in json_schema.get("properties", {}):
            return MockResponse(json.dumps({
                "pass": True, "violations": [], "correction": "",
            }))

        return MockResponse(
            "Mira looked up from the archive, a question forming "
            "behind her eyes. You spoke first."
        )


# ── Fixtures ─────────────────────────────────────────────────

def _load_engine():
    engine_loader._eng = None
    engine_loader.eng()


def _stub_emotions():
    from straightjacket.engine import emotions_loader
    emotions_loader._data = {
        "importance": {"neutral": 2, "curious": 4, "friendly": 3},
        "keyword_boosts": {},
        "disposition_map": {
            "neutral": "neutral", "friendly": "friendly",
            "loyal": "loyal", "hostile": "hostile",
        },
    }


def _game() -> GameState:
    game = GameState(
        player_name="Kael", character_concept="Wandering scholar",
        setting_genre="dark_fantasy", setting_tone="serious_balanced",
        setting_description="A world of fading magic.",
        edge=1, heart=2, iron=1, shadow=1, wits=2,
    )
    game.resources.health = 4
    game.resources.spirit = 3
    game.resources.supply = 5
    game.resources.momentum = 5
    game.world.current_location = "Abandoned Library"
    game.world.time_of_day = "evening"
    game.world.chaos_factor = 5
    game.npcs = [
        NpcData(id="npc_1", name="Mira", disposition="friendly",
                bond=2, bond_max=4, agenda="protect the archives",
                instinct="trust cautiously",
                description="Young archivist with ink-stained hands",
                memory=[MemoryEntry(event="Met the player",
                         emotional_weight="curious", type="observation",
                         scene=1)]),
    ]
    game.narrative.scene_count = 3
    game.narrative.session_log.append(SceneLogEntry(
        scene=3, summary="Searched the room", move="face_danger",
        result="MISS", consequences=["health -2"]))
    game.narrative.narration_history.append(NarrationEntry(
        scene=3, prompt_summary="Original scene", narration="Old narration."))
    game.last_turn_snapshot = game.snapshot()
    game.last_turn_snapshot.player_input = "I attack the guard"
    game.last_turn_snapshot.brain = BrainResult(
        move="strike", stat="iron", player_intent="Attack the guard")
    game.last_turn_snapshot.roll = RollResult(
        d1=2, d2=3, c1=7, c2=8, stat_name="iron", stat_value=1,
        action_score=6, result="MISS", move="strike")
    game.last_turn_snapshot.narration = "You swung wildly and missed."
    # Damage state after snapshot to verify restore
    game.resources.health = 1
    return game


# ── input_misread: full flow ─────────────────────────────────

def test_correction_input_misread_full_flow():
    """input_misread: restore snapshot, re-brain, re-narrate, metadata, log."""
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.correction import process_correction

    game = _game()
    snap_health = game.last_turn_snapshot.resources["health"]
    scene_before = game.narrative.scene_count
    history_len_before = len(game.narrative.narration_history)

    provider = MockProvider(correction_source="input_misread")
    game, narration, director_ctx = process_correction(
        provider, game, "I didn't want to attack",
        config=EngineConfig(narration_lang="English"))

    assert game.resources.health == snap_health
    assert game.narrative.scene_count == scene_before + 1
    assert len(narration) > 10
    assert len(game.narrative.narration_history) > history_len_before
    assert "[corrected]" in game.narrative.narration_history[-1].prompt_summary
    assert game.narrative.session_log[-1].summary.startswith("[corrected]")


# ── state_error: full flow ───────────────────────────────────

def test_correction_state_error_full_flow():
    """state_error: patch NPC, re-narrate, metadata, replace last log entry."""
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.correction import process_correction

    game = _game()
    assert game.npcs[0].disposition == "friendly"
    history_len_before = len(game.narrative.narration_history)

    provider = MockProvider(correction_source="state_error")
    game, narration, director_ctx = process_correction(
        provider, game, "Mira should be loyal",
        config=EngineConfig(narration_lang="English"))

    assert game.npcs[0].disposition == "loyal"
    assert len(narration) > 10
    assert len(game.narrative.narration_history) == history_len_before
    assert game.narrative.session_log[-1].summary.startswith("[corrected]")


# ── momentum burn: full flow ─────────────────────────────────

def test_momentum_burn_full_flow():
    """Burn: restore, reset momentum, STRONG_HIT consequences, re-narrate, update log."""
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.correction import process_momentum_burn

    game = _game()
    pre_snap = game.last_turn_snapshot
    snap_health = pre_snap.resources["health"]
    game.narrative.session_log.append(SceneLogEntry(
        scene=4, summary="Attack", move="strike", result="MISS"))

    provider = MockProvider()
    game, narration = process_momentum_burn(
        provider, game, pre_snap.roll, "STRONG_HIT",
        BrainResult(move="strike", stat="iron", player_intent="Attack"),
        config=EngineConfig(narration_lang="English"),
        pre_snapshot=pre_snap)

    assert game.resources.health == snap_health
    _e = engine_loader.eng()
    assert game.resources.momentum == _e.momentum.start + _e.momentum.gain.strong_hit.standard
    assert len(narration) > 10
    assert game.narrative.session_log[-1].result == "STRONG_HIT"


# ── no snapshot: graceful error ──────────────────────────────

def test_correction_no_snapshot():
    """No snapshot available: returns error string, no crash."""
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.correction import process_correction

    game = _game()
    game.last_turn_snapshot = None

    provider = MockProvider()
    game, narration, director_ctx = process_correction(
        provider, game, "Fix something",
        config=EngineConfig(narration_lang="English"))

    assert director_ctx is None
    assert isinstance(narration, str)
