from __future__ import annotations

import contextlib
import json
import random
import re
from pathlib import Path
from typing import Any

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse, AIUnavailableError
from straightjacket.engine.game.turn import process_turn
from straightjacket.engine.models import EngineConfig, GameState, ProgressTrack
from tests._helpers import make_clock, make_memory, make_npc

RESULT_TAG = re.compile(r'<result type="(\w+)"')

BRAIN_FIELDS: dict[str, Any] = {
    "type": "action",
    "approach": "",
    "target_npc": None,
    "dialog_only": False,
    "player_intent": "",
    "world_addition": None,
    "location_change": None,
    "track_name": None,
    "track_rank": None,
    "target_track": None,
    "bonus_id": None,
}


class _NarratorReached(Exception):
    pass


class _CaptureProvider:
    def __init__(self, brain: dict[str, Any]) -> None:
        self.brain = {**BRAIN_FIELDS, **brain}
        self.spec: AICallSpec | None = None

    def create_message(self, spec: AICallSpec) -> AIResponse:
        if spec.log_role == "narrator":
            self.spec = spec
            raise _NarratorReached
        return AIResponse(content=json.dumps(self.brain), usage={"input_tokens": 0, "output_tokens": 0})


def scene_text(messages: list[dict[str, Any]]) -> str:
    return "\n".join(m["content"] for m in messages if isinstance(m["content"], str))


def build_game(definition: dict[str, Any], common: dict[str, Any]) -> GameState:
    setting_id, genre, description = definition["setting"]
    name, concept = definition["player"]
    game = GameState(
        player_name=name,
        character_concept=concept,
        setting_id=setting_id,
        setting_genre=genre,
        setting_tone=common["tone"],
        setting_description=description,
        stats=dict(definition["stats"]),
    )
    resources = definition["resources"]
    game.resources.health = resources["health"]
    game.resources.spirit = resources["spirit"]
    game.resources.supply = resources["supply"]
    game.resources.momentum = resources["momentum"]
    game.world.current_location = definition["location"]
    game.world.time_of_day = definition["time"]
    game.world.chaos_factor = common["chaos_factor"]
    game.world.clocks = [make_clock(**clock) for clock in definition["clocks"]]
    game.npcs = [
        make_npc(
            **{key: value for key, value in npc.items() if key != "memory"},
            memory=[make_memory(**npc["memory"], type="observation", scene=1)],
        )
        for npc in definition["npcs"]
    ]
    if "combat" in definition:
        game.progress_tracks.append(
            ProgressTrack.new(id="combat_scene", name=definition["combat"], track_type="combat", rank="dangerous")
        )
        game.world.combat_position = "in_control"
    game.narrative.scene_count = common["scene_count"]
    return game


def capture_scenario(
    definition: dict[str, Any], common: dict[str, Any], seed_limit: int, narration_lang: str
) -> dict[str, Any] | None:
    for seed in range(seed_limit):
        random.seed(seed)
        provider = _CaptureProvider(definition["brain"])
        with contextlib.suppress(AIUnavailableError):
            process_turn(
                provider,
                build_game(definition, common),
                definition["text"],
                EngineConfig(narration_lang=narration_lang),
            )
        if provider.spec is None:
            continue
        found = RESULT_TAG.search(scene_text(provider.spec.messages))
        result = found.group(1) if found else "dialog"
        if result == definition["want"]:
            return {"system": provider.spec.system, "messages": provider.spec.messages, "seed": seed, "result": result}
    return None


def capture_all(definitions: dict[str, Any], out_dir: Path, settings: dict[str, Any]) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for name, definition in definitions["scenarios"].items():
        captured = capture_scenario(
            definition, definitions["common"], settings["seed_limit"], settings["narration_lang"]
        )
        if captured is None:
            lines.append(f"{name}: no seed below {settings['seed_limit']} gives {definition['want']}")
            continue
        (out_dir / f"{name}.json").write_text(json.dumps(captured, ensure_ascii=False, indent=2), encoding="utf-8")
        lines.append(f"{name}: seed {captured['seed']}, {captured['result']}")
    return lines
