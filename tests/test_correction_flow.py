import json

from straightjacket.engine import engine_loader
from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse
from straightjacket.engine.models import (
    EngineConfig,
    GameState,
    NarrationEntry,
    RollResult,
    SceneLogEntry,
)
from tests._helpers import make_brain_result, make_memory, make_npc


class MockProvider:
    def __init__(self, correction_source: str = "input_misread") -> None:
        self.calls: list = []
        self._correction_source = correction_source

    def create_message(self, spec: AICallSpec) -> AIResponse:
        json_schema = spec.json_schema
        self.calls.append({"json_schema": json_schema})

        if json_schema and "correction_source" in json_schema.get("properties", {}):
            return AIResponse(
                content=json.dumps(
                    {
                        "correction_source": self._correction_source,
                        "corrected_input": "I talk to Mira instead",
                        "reroll_needed": False,
                        "corrected_stat": "none",
                        "narrator_guidance": "Rewrite as peaceful dialog.",
                        "director_useful": False,
                        "state_ops": [
                            {
                                "op": "npc_edit",
                                "npc_id": "npc_1",
                                "split_name": None,
                                "split_description": None,
                                "merge_source_id": None,
                                "fields": {"disposition": "loyal"},
                                "value": None,
                            }
                        ]
                        if self._correction_source == "state_error"
                        else [],
                    }
                ),
                usage={"input_tokens": 100, "output_tokens": 50},
            )

        if json_schema and "move" in json_schema.get("properties", {}):
            return AIResponse(
                content=json.dumps(
                    {
                        "type": "action",
                        "move": "dialog",
                        "stat": "none",
                        "approach": "speaking gently",
                        "target_npc": "npc_1",
                        "dialog_only": True,
                        "player_intent": "Talk to Mira",
                        "world_addition": None,
                        "location_change": None,
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

        return AIResponse(
            content="Mira looked up from the archive, a question forming behind her eyes. You spoke first.",
            usage={"input_tokens": 100, "output_tokens": 50},
        )


def _game() -> "GameState":
    game = GameState(
        player_name="Kael",
        character_concept="Wandering scholar",
        setting_genre="dark_fantasy",
        setting_tone="serious_balanced",
        setting_description="A world of fading magic.",
        stats={"edge": 1, "heart": 2, "iron": 1, "shadow": 1, "wits": 2},
    )
    game.resources.health = 4
    game.resources.spirit = 3
    game.resources.supply = 5
    game.resources.momentum = 5
    game.world.current_location = "Abandoned Library"
    game.world.time_of_day = "evening"
    game.world.chaos_factor = 5
    game.npcs = [
        make_npc(
            id="npc_1",
            name="Mira",
            disposition="friendly",
            agenda="protect the archives",
            instinct="trust cautiously",
            description="Young archivist with ink-stained hands",
            memory=[make_memory(event="Met the player", emotional_weight="curious", type="observation", scene=1)],
        ),
    ]
    game.narrative.scene_count = 3
    game.narrative.session_log.append(
        SceneLogEntry(
            scene=3,
            summary="Searched the room",
            move="adventure/face_danger",
            result="MISS",
            consequences=["health -2"],
            scene_type="expected",
        )
    )
    game.narrative.narration_history.append(
        NarrationEntry(scene=3, prompt_summary="Original scene", narration="Old narration.")
    )
    game.last_turn_snapshot = game.snapshot()
    game.last_turn_snapshot.player_input = "I attack the guard"
    game.last_turn_snapshot.brain = make_brain_result(
        move="combat/strike", stat="iron", player_intent="Attack the guard"
    )
    game.last_turn_snapshot.roll = RollResult(
        d1=2,
        d2=3,
        c1=7,
        c2=8,
        stat_name="iron",
        stat_value=1,
        action_score=6,
        result="MISS",
        move="combat/strike",
        match=False,
    )
    game.last_turn_snapshot.narration = "You swung wildly and missed."

    game.resources.health = 1
    return game


def test_correction_input_misread_full_flow(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.correction import process_correction

    game = _game()
    assert game.last_turn_snapshot is not None
    snap_health = game.last_turn_snapshot.resources["health"]
    scene_before = game.narrative.scene_count
    history_len_before = len(game.narrative.narration_history)

    provider = MockProvider(correction_source="input_misread")
    game, narration, director_ctx = process_correction(
        provider,
        game,
        "I didn't want to attack",
        config=EngineConfig(narration_lang="English"),
    )

    assert game.resources.health == snap_health
    assert game.narrative.scene_count == scene_before + 1
    assert len(narration) > 10
    assert len(game.narrative.narration_history) > history_len_before
    assert "[corrected]" in game.narrative.narration_history[-1].prompt_summary
    assert game.narrative.session_log[-1].summary.startswith("[corrected]")


def test_correction_state_error_full_flow(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.correction import process_correction

    game = _game()
    assert game.npcs[0].disposition == "friendly"
    history_len_before = len(game.narrative.narration_history)

    provider = MockProvider(correction_source="state_error")
    game, narration, director_ctx = process_correction(
        provider,
        game,
        "Mira should be loyal",
        config=EngineConfig(narration_lang="English"),
    )

    assert game.npcs[0].disposition == "loyal"
    assert len(narration) > 10
    assert len(game.narrative.narration_history) == history_len_before
    assert game.narrative.session_log[-1].summary.startswith("[corrected]")


def test_momentum_burn_full_flow(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.game.momentum_burn import process_momentum_burn

    game = _game()
    pre_snap = game.last_turn_snapshot
    assert pre_snap is not None
    snap_health = pre_snap.resources["health"]
    game.narrative.session_log.append(
        SceneLogEntry(scene=4, summary="Attack", move="combat/strike", result="MISS", scene_type="expected")
    )

    provider = MockProvider()
    game, narration = process_momentum_burn(
        provider,
        game,
        pre_snap.roll,
        "STRONG_HIT",
        make_brain_result(move="combat/strike", stat="iron", player_intent="Attack"),
        config=EngineConfig(narration_lang="English"),
        pre_snapshot=pre_snap,
    )

    assert game.resources.health == snap_health
    _e = engine_loader.eng()

    assert game.resources.momentum == _e.momentum.start
    assert len(narration) > 10
    assert game.narrative.session_log[-1].result == "STRONG_HIT"


def test_correction_no_snapshot(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.correction import process_correction

    game = _game()
    game.last_turn_snapshot = None

    provider = MockProvider()
    game, narration, director_ctx = process_correction(
        provider,
        game,
        "Fix something",
        config=EngineConfig(narration_lang="English"),
    )

    assert director_ctx is None
    assert isinstance(narration, str)
