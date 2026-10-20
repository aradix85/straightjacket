from __future__ import annotations

import json
from collections.abc import Callable, Sequence
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
        self.calls: list[AICallSpec] = []

    @staticmethod
    def _json(payload: dict[str, Any]) -> AIResponse:
        return AIResponse(content=json.dumps(payload), usage={"input_tokens": 10, "output_tokens": 10})

    def create_message(self, spec: AICallSpec) -> AIResponse:
        self.calls.append(spec)
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


def correction_answer(**overrides: Any) -> dict[str, Any]:
    correction: dict[str, Any] = {
        "correction_source": "input_misread",
        "corrected_input": "I shoulder the vault door",
        "narrator_guidance": "The player used force, not finesse.",
        "director_useful": False,
        "state_ops": [],
    }
    correction.update(overrides)
    return correction


class TurnProvider:
    def __init__(self, *brains: dict[str, Any]) -> None:
        self.brains = list(brains)
        self.correction = correction_answer()
        self.calls: list[AICallSpec] = []
        self.narrations: list[str] = []
        self.prompts: list[str] = []

    @staticmethod
    def _json(payload: dict[str, Any]) -> AIResponse:
        return AIResponse(content=json.dumps(payload), usage={"input_tokens": 10, "output_tokens": 10})

    def create_message(self, spec: AICallSpec) -> AIResponse:
        self.calls.append(spec)
        props = spec.json_schema["properties"] if spec.json_schema else {}
        if "move" in props:
            return self._json(self.brains.pop(0) if len(self.brains) > 1 else self.brains[0])
        if "correction_source" in props:
            return self._json(self.correction)
        if "new_npcs" in props:
            return self._json(
                {"new_npcs": [], "npc_renames": [], "npc_details": [], "deceased_npcs": [], "lore_npcs": []}
            )
        if "revelation_confirmed" in props:
            return self._json({"revelation_confirmed": False, "reasoning": "Absent."})
        if "scene_summary" in props:
            return self._json(
                {
                    "scene_summary": "",
                    "narrator_guidance": "",
                    "npc_guidance": [],
                    "npc_reflections": {},
                    "arc_notes": "",
                }
            )
        text = f"Scene text number {len(self.narrations) + 1}. Dust drifts through the lamplight."
        if spec.log_role == "narrator":
            self.narrations.append(text)
            self.prompts.append(str(spec.messages[-1]["content"]))
        return AIResponse(content=text, usage={"input_tokens": 10, "output_tokens": 10})

    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse:
        response = self.create_message(spec)
        on_text(response.content)
        return response


def fixed_roll(result: str) -> Callable[[str, int, str, int, int], RollResult]:
    def _roll(stat_name: str, stat_value: int, move: str, momentum: int, adds: int) -> RollResult:
        return RollResult(
            d1=1,
            c1=4,
            c2=5,
            stat_name=stat_name,
            stat_value=stat_value,
            action_score=1 + stat_value,
            result=result,
            move=move,
            match=False,
        )

    return _roll


def force_result(monkeypatch: pytest.MonkeyPatch, result: str) -> None:
    from straightjacket.engine.game import turn
    from straightjacket.engine.ruleset import make_move

    monkeypatch.setattr(make_move, "roll_action", fixed_roll(result))
    monkeypatch.setattr(turn, "check_scene", lambda _game: make_scene_setup(scene_type="expected"))


def creation_data(
    setting_id: str, *, stats: tuple[int, int, int, int, int], player_name: str, background_vow: str
) -> dict[str, Any]:
    from straightjacket.engine.setting.packages import load_package

    return {
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

    creation = creation_data(setting_id, stats=stats, player_name=player_name, background_vow=background_vow)
    game, _narration = start_new_game(OpeningProvider(npcs, location), creation)
    return game


def library_game() -> GameState:
    game = create_game(
        "classic",
        location="Abandoned Library",
        npcs=[("Mira", "Young archivist with ink-stained hands", "friendly")],
        stats=(2, 2, 1, 1, 3),
        player_name="Kael",
        background_vow="Keep the archive whole",
    )
    game.resources.meters["momentum"] = 6
    return game
