from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import pytest

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse
from straightjacket.engine.models import EngineConfig, GameState, RollResult, SceneSetup

OPENING_TEXT = "The opening scene settles around you."
STAT_ORDER = ("edge", "heart", "iron", "shadow", "wits")


class OpeningProvider:
    def __init__(self, npcs: Sequence[tuple[str, str, str]], location: str) -> None:
        self.npcs = list(npcs)
        self.location = location

    @staticmethod
    def _json(payload: dict[str, Any]) -> AIResponse:
        return AIResponse(content=json.dumps(payload), usage={"input_tokens": 10, "output_tokens": 10})

    def create_message(self, spec: AICallSpec) -> AIResponse:
        props = spec.json_schema["properties"] if spec.json_schema else {}
        if "central_conflict" in props:
            return self._json(_voicing(props))
        if "scene_context" in props:
            return self._json(
                {
                    "npcs": [
                        {
                            "name": name,
                            "description": description,
                            "agenda": "",
                            "instinct": "",
                            "secrets": [],
                            "disposition": disposition,
                        }
                        for name, description, disposition in self.npcs
                    ],
                    "location": self.location,
                    "scene_context": "",
                    "memory_updates": [],
                    "deceased_npcs": [],
                }
            )
        return AIResponse(content=OPENING_TEXT, usage={"input_tokens": 10, "output_tokens": 10})


def _voicing(props: dict[str, Any]) -> dict[str, Any]:
    return {
        "central_conflict": "A buried record threatens the settlement",
        "antagonist_force": "The ones who buried it",
        "thematic_thread": "What a place chooses to remember",
        "acts": [
            {"title": f"Act {i}", "goal": "g", "mood": "cold", "transition_trigger": "t"}
            for i in range(props["acts"]["minItems"])
        ],
        "revelations": [{"content": f"Revelation {i}"} for i in range(props["revelations"]["minItems"])],
        "possible_endings": [
            {"type": "earned", "description": f"Ending {i}"} for i in range(props["possible_endings"]["minItems"])
        ],
    }


def force_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.game import turn

    def _roll(stat_name: str, stat_value: int, move: str, momentum: int, adds: int) -> RollResult:
        return RollResult(
            d1=1,
            c1=4,
            c2=5,
            stat_name=stat_name,
            stat_value=stat_value,
            action_score=1 + stat_value,
            result="MISS",
            move=move,
            match=False,
        )

    monkeypatch.setattr(turn, "roll_action", _roll)
    monkeypatch.setattr(turn, "check_scene", lambda _game: SceneSetup(scene_type="expected", chaos_roll=10))


def create_game(
    setting_id: str,
    *,
    location: str,
    npcs: Sequence[tuple[str, str, str]],
    stats: tuple[int, int, int, int, int],
    player_name: str,
    background_vow: str,
) -> GameState:
    from straightjacket.engine.datasworn.settings import load_package
    from straightjacket.engine.game import start_new_game

    creation = {
        "setting_id": setting_id,
        "tone": load_package(setting_id).default_tone,
        "stats": dict(zip(STAT_ORDER, stats, strict=True)),
        "player_name": player_name,
        "pronouns": "she/her",
        "background_vow": background_vow,
        "paths": [],
        "backstory": "",
    }
    provider = OpeningProvider(npcs, location)
    game, _narration = start_new_game(provider, creation, EngineConfig(narration_lang="English"))
    return game
