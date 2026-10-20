from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import pytest

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse
from straightjacket.engine.models import GameState, RollResult
from tests._helpers import make_scene_setup

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


BRAIN_FIELDS: dict[str, Any] = {
    "approach": "",
    "target_npc": None,
    "dialog_only": False,
    "player_intent": "",
    "world_addition": None,
    "location_change": None,
    "track_name": None,
    "track_rank": None,
    "target_track": None,
    "target_clock": None,
    "target_threat": None,
    "bonus_id": None,
    "undetermined_facts": [],
    "boasts": [],
}


class BrainAnswers:
    def __init__(self, move: str, **fields: Any) -> None:
        self.move = move
        self.fields = fields
        self.schemas: list[dict[str, Any]] = []
        self.systems: list[str] = []
        self.user_messages: list[str] = []

    def create_message(self, spec: AICallSpec) -> AIResponse:
        assert spec.json_schema is not None
        self.schemas.append(spec.json_schema)
        self.systems.append(spec.system)
        self.user_messages.append(spec.messages[-1]["content"])
        answer = {**BRAIN_FIELDS, "move": self.move, "stat": "iron", "player_intent": "strike", **self.fields}
        return AIResponse(content=json.dumps(answer), usage={"input_tokens": 0, "output_tokens": 0})


def brain_answer(**overrides: Any) -> dict[str, Any]:
    brain: dict[str, Any] = {
        "move": "adventure/face_danger",
        "stat": "wits",
        "approach": "quietly",
        "target_npc": None,
        "dialog_only": False,
        "player_intent": "I slip past Mira into the archive vault",
        "world_addition": None,
        "location_change": {"name": "Archive Vault", "kind": "location"},
        "track_name": "Reach the vault",
        "track_rank": "dangerous",
        "target_track": None,
        "target_clock": None,
        "target_threat": None,
        "bonus_id": None,
        "undetermined_facts": [],
        "boasts": [],
    }
    brain.update(overrides)
    return brain


class TurnProvider:
    def __init__(self, brain: dict[str, Any]) -> None:
        self.brain = brain
        self.narrations: list[str] = []
        self.prompts: list[str] = []

    @staticmethod
    def _json(payload: dict[str, Any]) -> AIResponse:
        return AIResponse(content=json.dumps(payload), usage={"input_tokens": 10, "output_tokens": 10})

    def create_message(self, spec: AICallSpec) -> AIResponse:
        props = spec.json_schema.get("properties", {}) if spec.json_schema else {}
        if "move" in props:
            return self._json(self.brain)
        if "new_npcs" in props:
            return self._json(
                {"new_npcs": [], "npc_renames": [], "npc_details": [], "deceased_npcs": [], "lore_npcs": []}
            )
        if "revelation_confirmed" in props:
            return self._json({"revelation_confirmed": False, "reasoning": "Absent."})
        text = f"Scene text number {len(self.narrations) + 1}. Dust drifts through the lamplight."
        self.narrations.append(text)
        self.prompts.append(str(spec.messages[-1]["content"]))
        return AIResponse(content=text, usage={"input_tokens": 10, "output_tokens": 10})


def force_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.game import turn
    from straightjacket.engine.ruleset import make_move

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

    monkeypatch.setattr(make_move, "roll_action", _roll)
    monkeypatch.setattr(turn, "check_scene", lambda _game: make_scene_setup(scene_type="expected"))


def create_game(
    setting_id: str,
    *,
    location: str,
    npcs: Sequence[tuple[str, str, str]],
    stats: tuple[int, int, int, int, int],
    player_name: str,
    background_vow: str,
) -> GameState:
    from straightjacket.engine.game import start_new_game
    from straightjacket.engine.setting.packages import load_package

    creation = {
        "setting_id": setting_id,
        "tone": load_package(setting_id).default_tone,
        "stats": dict(zip(STAT_ORDER, stats, strict=True)),
        "player_name": player_name,
        "pronouns": "she/her",
        "background_vow": background_vow,
        "paths": [],
        "backstory": "",
        "background_vow_rank": "",
        "vow_subject": "",
        "assets": [],
        "truths": {},
        "wishes": "",
        "content_lines": "",
    }
    provider = OpeningProvider(npcs, location)
    game, _narration = start_new_game(provider, creation)
    return game
