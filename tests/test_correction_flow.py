import json
from typing import Any

import pytest

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse
from straightjacket.engine.models import GameState
from tests._creation import create_game, force_miss

_TURN_BRAIN = {
    "move": "adventure/face_danger",
    "stat": "iron",
    "dialog_only": False,
    "player_intent": "Shove past the guard",
}


class MockProvider:
    def __init__(
        self,
        correction_source: str = "input_misread",
        brain_stat: str = "none",
        dialog_only: bool = True,
    ) -> None:
        self.calls: list = []
        self.narration_prompts: list[str] = []
        self._correction_source = correction_source
        self._brains: list[dict[str, Any]] = [
            _TURN_BRAIN,
            {"move": "dialog", "stat": brain_stat, "dialog_only": dialog_only, "player_intent": "Talk to Mira"},
        ]

    def create_message(self, spec: AICallSpec) -> AIResponse:
        json_schema = spec.json_schema
        self.calls.append({"json_schema": json_schema})

        if json_schema and "correction_source" in json_schema.get("properties", {}):
            return AIResponse(
                content=json.dumps(
                    {
                        "correction_source": self._correction_source,
                        "corrected_input": "I talk to Mira instead",
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
            brain = self._brains.pop(0) if len(self._brains) > 1 else self._brains[0]
            return AIResponse(
                content=json.dumps(
                    {
                        "approach": "speaking gently",
                        "target_npc": "npc_1",
                        **brain,
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

        self.narration_prompts.append(spec.messages[-1]["content"])
        return AIResponse(
            content="Mira looked up from the archive, a question forming behind her eyes. You spoke first.",
            usage={"input_tokens": 100, "output_tokens": 50},
        )


def _played_game(provider: MockProvider, monkeypatch: pytest.MonkeyPatch) -> GameState:
    from straightjacket.engine.game import process_turn

    game = create_game(
        "classic",
        location="Abandoned Library",
        npcs=[("Mira", "Young archivist with ink-stained hands", "friendly")],
        stats=(2, 2, 1, 1, 3),
        player_name="Kael",
        background_vow="Keep the archive whole",
    )
    force_miss(monkeypatch)
    _narration, _roll, _offer, _director = process_turn(provider, game, "I shove past the guard", stream=None)
    return game


def test_correction_input_misread_full_flow(
    load_engine: None, stub_emotions: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import process_correction

    provider = MockProvider(correction_source="input_misread")
    game = _played_game(provider, monkeypatch)
    assert game.last_turn_snapshot is not None
    snap_health = game.last_turn_snapshot.resources["health"]
    scene_before = game.narrative.scene_count
    history_len_before = len(game.narrative.narration_history)

    narration, _offer, _director_ctx = process_correction(provider, game, "I didn't want to attack")

    assert game.resources.health == snap_health
    assert game.narrative.scene_count == scene_before
    assert len(narration) > 10
    assert len(game.narrative.narration_history) == history_len_before
    assert game.narrative.narration_history[-1].narration == narration
    assert game.last_turn_snapshot is not None
    assert game.last_turn_snapshot.player_input == "I talk to Mira instead"


def test_correction_to_dialog_does_not_roll_even_with_a_stat(
    load_engine: None, stub_emotions: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import process_correction

    provider = MockProvider(correction_source="input_misread", brain_stat="heart", dialog_only=False)
    game = _played_game(provider, monkeypatch)
    narration, _offer, _director_ctx = process_correction(
        provider, game, "That's not what I said, I was asking a question"
    )

    assert len(narration) > 10
    assert game.narrative.session_log[-1].result == "dialog"


def test_correction_state_error_full_flow(
    load_engine: None, stub_emotions: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import process_correction

    provider = MockProvider(correction_source="state_error")
    game = _played_game(provider, monkeypatch)
    assert game.npcs[0].disposition == "friendly"
    history_len_before = len(game.narrative.narration_history)

    narration, _offer, _director_ctx = process_correction(provider, game, "Mira should be loyal")

    assert game.npcs[0].disposition == "loyal"
    assert len(narration) > 10
    assert len(game.narrative.narration_history) == history_len_before
    assert game.narrative.session_log[-1].summary.startswith("[corrected]")


def test_a_state_correction_retells_the_turn_with_its_own_scene_and_position(
    load_engine: None, stub_emotions: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import process_correction
    from straightjacket.engine.models import SceneSetup

    provider = MockProvider(correction_source="state_error")
    game = _played_game(provider, monkeypatch)
    assert game.last_turn_snapshot is not None
    game.last_turn_snapshot.scene_setup = SceneSetup(scene_type="keyed", narrative_hint="The bell tolls")
    game.narrative.session_log[-1].position = "desperate"
    game.narrative.session_log[-1].effect = "limited"

    process_correction(provider, game, "Mira should be loyal")

    retold = provider.narration_prompts[-1]
    assert "<keyed_scene>The bell tolls</keyed_scene>" in retold
    assert '<position level="desperate" effect="limited"/>' in retold


def test_a_state_correction_does_not_tell_a_clock_that_filled_after_the_turn(
    load_engine: None, stub_emotions: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import process_correction
    from straightjacket.engine.models import ClockEvent

    provider = MockProvider(correction_source="state_error")
    game = _played_game(provider, monkeypatch)
    game.narrative.session_log[-1].clock_events.append(
        ClockEvent(clock="A storm gathers", trigger="The storm breaks", autonomous=True, triggered=True)
    )

    process_correction(provider, game, "Mira should be loyal")

    assert "A storm gathers" not in provider.narration_prompts[-1]


def test_a_state_correction_extracts_with_the_turns_world_addition(
    load_engine: None, stub_emotions: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import process_correction
    from straightjacket.engine.game import finalization

    provider = MockProvider(correction_source="state_error")
    game = _played_game(provider, monkeypatch)
    assert game.last_turn_snapshot is not None
    assert game.last_turn_snapshot.brain is not None
    game.last_turn_snapshot.brain.world_addition = "A rope hangs from the gallery"
    seen: list[str] = []

    def capture(game: GameState, metadata: dict[str, Any], *, scene_present_ids: set[str], world_addition: str) -> None:
        seen.append(world_addition)

    monkeypatch.setattr(finalization, "apply_narrator_metadata", capture)
    process_correction(provider, game, "Mira should be loyal")

    assert seen == ["A rope hangs from the gallery"]


def test_a_snapshot_without_a_played_turn_is_refused(
    load_engine: None, stub_emotions: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import process_correction

    provider = MockProvider(correction_source="state_error")
    game = _played_game(provider, monkeypatch)
    assert game.last_turn_snapshot is not None
    game.last_turn_snapshot.brain = None
    with pytest.raises(ValueError, match="no Brain result"):
        process_correction(provider, game, "Mira should be loyal")


def test_correction_no_snapshot(load_engine: None, stub_emotions: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.correction import process_correction

    provider = MockProvider()
    game = _played_game(provider, monkeypatch)
    game.last_turn_snapshot = None

    narration, _offer, director_ctx = process_correction(provider, game, "Fix something")

    assert director_ctx is None
    assert isinstance(narration, str)
