from __future__ import annotations

import json
import random
import re
import xml.etree.ElementTree as ET

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse
from tests.test_integration import MockProvider, _make_game


class _NarratorCapture(MockProvider):
    def __init__(self, dialog: bool) -> None:
        super().__init__()
        self.dialog = dialog
        self.prompts: list[str] = []

    def create_message(self, spec: AICallSpec) -> AIResponse:
        schema = spec.json_schema
        if self.dialog and schema and "move" in schema["properties"]:
            brain = {
                "type": "action",
                "move": "dialog",
                "stat": "none",
                "approach": "",
                "target_npc": "npc_1",
                "dialog_only": True,
                "player_intent": "Ask who the ledger belongs to",
                "world_addition": None,
                "location_change": None,
            }
            return AIResponse(content=json.dumps(brain), usage={"input_tokens": 1, "output_tokens": 1})
        if spec.log_role == "narrator":
            self.prompts.append("\n".join(m["content"] for m in spec.messages if isinstance(m["content"], str)))
        return super().create_message(spec)


def _narrator_prompt(seed: int, dialog: bool) -> tuple[str | None, str]:
    from straightjacket.engine.game.turn import process_turn
    from straightjacket.engine.models import EngineConfig

    random.seed(seed)
    provider = _NarratorCapture(dialog)
    _, _, roll, _, _ = process_turn(
        provider,
        _make_game(),
        "I try to take the ledger from the counter.",
        config=EngineConfig(narration_lang="English"),
    )
    return (roll.result if roll else None), provider.prompts[0]


def _scene_block(prompt: str) -> str:
    match = re.search(r"<scene\b.*</scene>", prompt, re.S)
    assert match, prompt[:200]
    return match.group(0)


def test_action_scene_is_well_formed_xml_for_every_result(load_engine: None) -> None:
    prompts: dict[str, str] = {}
    for seed in range(200):
        result, prompt = _narrator_prompt(seed, dialog=False)
        if result is not None:
            prompts.setdefault(result, prompt)
        if len(prompts) == 3:
            break
    assert set(prompts) == {"MISS", "WEAK_HIT", "STRONG_HIT"}
    for prompt in prompts.values():
        assert ET.fromstring(_scene_block(prompt)).tag == "scene"


def test_dialog_scene_is_well_formed_xml(load_engine: None) -> None:
    _, prompt = _narrator_prompt(0, dialog=True)
    assert ET.fromstring(_scene_block(prompt)).tag == "scene"
