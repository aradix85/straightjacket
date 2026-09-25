import json
from typing import Any

import pytest

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse, AIUnavailableError
from straightjacket.engine.models import ProgressTrack
from tests._helpers import make_game_state
from tests.modeltest.capture import BRAIN_FIELDS


def _offered(game: Any) -> list[str]:
    from straightjacket.engine.ai.schemas import get_brain_output_schema
    from straightjacket.engine.tools.builtins import available_moves

    schema = get_brain_output_schema([m["move"] for m in available_moves(game)["moves"]])
    offered: list[str] = schema["properties"]["move"]["enum"]
    return offered


def _starforged() -> Any:
    game = make_game_state()
    game.setting_id = "starforged"
    return game


def test_a_strike_is_offered_only_in_a_fight(load_engine: None) -> None:
    game = _starforged()
    assert "combat/strike" not in _offered(game)
    game.progress_tracks.append(ProgressTrack.new(id="fight", name="Fight", track_type="combat", rank="dangerous"))
    game.world.combat_position = "in_control"
    assert "combat/strike" in _offered(game)
    assert "dialog" in _offered(game)


class _BrainAnswers:
    def __init__(self, move: str) -> None:
        self.move = move
        self.schemas: list[dict[str, Any]] = []

    def create_message(self, spec: AICallSpec) -> AIResponse:
        assert spec.json_schema is not None
        self.schemas.append(spec.json_schema)
        answer = {**BRAIN_FIELDS, "move": self.move, "stat": "iron", "player_intent": "strike"}
        return AIResponse(content=json.dumps(answer), usage={"input_tokens": 0, "output_tokens": 0})


def test_the_brain_cannot_play_a_move_the_situation_does_not_allow(load_engine: None) -> None:
    from straightjacket.engine.ai.brain import call_brain

    provider = _BrainAnswers("combat/strike")
    with pytest.raises(AIUnavailableError, match="not available"):
        call_brain(provider, _starforged(), "I stab at the raider.")
    assert "combat/strike" not in provider.schemas[0]["properties"]["move"]["enum"]


def test_the_brain_plays_an_available_move(load_engine: None) -> None:
    from straightjacket.engine.ai.brain import call_brain

    assert call_brain(_BrainAnswers("adventure/face_danger"), _starforged(), "I jump the gap.").move == (
        "adventure/face_danger"
    )
