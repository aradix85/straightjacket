import json
from typing import Any

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse
from tests._helpers import make_game_state, make_npc


def _minimal(schema: dict[str, Any]) -> Any:
    if "anyOf" in schema:
        options = schema["anyOf"]
        return None if {"type": "null"} in options else _minimal(options[0])
    kind = schema.get("type")
    if "enum" in schema:
        return schema["enum"][0]
    if kind == "object":
        return {key: _minimal(value) for key, value in schema["properties"].items()}
    if kind == "array":
        return []
    if kind in ("integer", "number"):
        return 0
    if kind == "boolean":
        return False
    if kind == "null":
        return None
    return ""


class _Director:
    def __init__(self) -> None:
        self.schemas: list[dict[str, Any]] = []

    def create_message(self, spec: AICallSpec) -> AIResponse:
        if spec.json_schema is None:
            return AIResponse(content="", usage={"input_tokens": 0, "output_tokens": 0})
        self.schemas.append(spec.json_schema)
        return AIResponse(content=json.dumps(_minimal(spec.json_schema)), usage={"input_tokens": 0, "output_tokens": 0})


def _reflections(schema: dict[str, Any]) -> Any:
    return schema["properties"]["npc_reflections"]


def test_the_director_may_reflect_only_on_the_npcs_chosen_for_reflection(load_engine: None) -> None:
    from straightjacket.engine.director import call_director

    game = make_game_state()
    game.npcs = [
        make_npc(id="npc_1", name="Kira", needs_reflection=True, agenda="Hold the pass", instinct="Strikes first"),
        make_npc(id="npc_2", name="Borin", needs_reflection=False, agenda="Sell the map", instinct="Lies easily"),
    ]
    provider = _Director()
    call_director(provider, game, "Kira watches the pass while Borin counts coins.")
    reflections = _reflections(provider.schemas[-1])
    assert list(reflections["properties"]) == ["npc_1"]
    assert reflections["required"] == ["npc_1"]
    assert reflections["additionalProperties"] is False
    assert "npc_id" not in reflections["properties"]["npc_1"]["properties"]


def test_without_chosen_npcs_there_is_no_reflection_to_write(load_engine: None) -> None:
    from straightjacket.engine.ai.schemas import get_director_output_schema

    reflections = _reflections(get_director_output_schema([]))
    assert reflections["properties"] == {}
    assert reflections["required"] == []
