import json

import pytest
from typing_extensions import override

from straightjacket.engine.ai.narrator import call_opening_setup
from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse
from straightjacket.engine.ai.schemas import get_opening_setup_schema
from straightjacket.engine.game import start_new_game
from straightjacket.engine.game.setup_common import apply_opening_setup, seed_opening_memories
from straightjacket.engine.models import GameState, OpeningMemory, OpeningSetup
from straightjacket.engine.serialization import read_key
from tests._creation import OpeningProvider, creation_data, opening_npc
from tests._helpers import make_clock, make_game_state, make_npc, schema_of
from tests._mocks import MockProvider


def _answer(*npcs: dict[str, object], location: str, scene_context: str) -> dict[str, object]:
    return {
        "npcs": list(npcs),
        "memory_updates": [],
        "location": location,
        "scene_context": scene_context,
        "deceased_npcs": [],
    }


def _setup(*npcs: dict[str, object]) -> OpeningSetup:
    return OpeningSetup.from_dict(_answer(*npcs, location="Dock", scene_context=""))


def test_an_opening_registers_neither_the_player_nor_a_known_npc_again() -> None:
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="npc_1", name="Kira", status="deceased")]
    apply_opening_setup(
        game,
        _setup(
            opening_npc("Kira", "Scout", "friendly"),
            opening_npc("Hero", "Player", "neutral"),
            opening_npc("Borin", "Smith", "neutral"),
        ),
        label="OpeningSetup",
    )
    assert [(n.id, n.name) for n in game.npcs] == [("npc_1", "Kira"), ("npc_2", "Borin")]


def test_an_opening_does_not_split_a_known_npc_by_a_shorter_name() -> None:
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="npc_1", name="Maren Silk", description="A smuggler.")]
    apply_opening_setup(game, _setup(opening_npc("Maren", "A smuggler", "neutral")), label="OpeningSetup")
    assert [n.name for n in game.npcs] == ["Maren Silk"]


def test_seed_opening_memories_matches_and_skips() -> None:
    game = make_game_state(player_name="Hero")
    game.narrative.scene_count = 1
    game.npcs = [make_npc(id="npc_1", name="Captain Ashwood")]
    seed_opening_memories(
        game,
        [
            OpeningMemory(npc_name="Ashwood", event="Nodded at player", emotional_weight="neutral"),
            OpeningMemory(npc_name="Nobody", event="Should be skipped", emotional_weight="neutral"),
        ],
    )
    assert len(game.npcs[0].memory) == 1


def test_opening_setup_sets_location_and_context_and_keeps_the_engines_clock_and_time() -> None:
    game = make_game_state(player_name="Hero")
    game.world.clocks = [make_clock(name="Engine clock")]
    game.world.time_of_day = "morning"
    setup = OpeningSetup(npcs=[], memory_updates=[], location="Market", scene_context="Busy.", deceased_npcs=[])
    apply_opening_setup(game, setup, label="OpeningSetup")
    assert game.world.current_location == "Market"
    assert game.world.current_scene_context == "Busy."
    assert [c.name for c in game.world.clocks] == ["Engine clock"]
    assert game.world.time_of_day == "morning"


def test_opening_setup_schema_leaves_clocks_and_time_to_the_engine() -> None:
    properties = read_key(get_opening_setup_schema(), "properties", dict, "schema")
    assert "clocks" not in properties
    assert "time_of_day" not in properties


def test_an_opening_extraction_that_follows_its_schema_is_read_whole() -> None:
    answer = _answer(opening_npc("Maren", "A smuggler", "neutral"), location="Dock", scene_context="Fog.")
    setup = call_opening_setup(MockProvider(json.dumps(answer)), "Fog on the dock.", make_game_state())
    assert [(n.name, n.secrets) for n in setup.npcs] == [("Maren", [])]
    assert (setup.location, setup.scene_context) == ("Dock", "Fog.")


def test_an_opening_whose_answers_bring_values_of_another_type_starts_plain_and_keeps_the_save_loadable() -> None:
    class Provider(OpeningProvider):
        @override
        def create_message(self, spec: AICallSpec) -> AIResponse:
            response = super().create_message(spec)
            props = schema_of(spec)["properties"] if spec.json_schema is not None else {}
            if "scene_context" in props or "central_conflict" in props:
                answer = json.loads(response.content)
                if "npcs" in answer:
                    answer["npcs"][0]["agenda"] = 7
                else:
                    answer["acts"][0]["title"] = None
                return AIResponse(content=json.dumps(answer), usage=response.usage)
            return response

    creation = creation_data("classic", stats=(2, 2, 1, 1, 3), player_name="Kael", background_vow="Keep the archive")
    game, _narration = start_new_game(Provider([("Mira", "An archivist", "friendly")], "Abandoned Library"), creation)
    assert not [n for n in game.npcs if n.name == "Mira"]
    assert game.narrative.story_blueprint is None
    assert GameState.from_dict(game.to_dict()) == game


@pytest.mark.parametrize(
    "wrong",
    [
        {"npcs": [opening_npc("Maren", "A smuggler", "neutral") | {"secrets": "none"}]},
        {"npcs": [opening_npc("Maren", "A smuggler", "neutral") | {"agenda": None}]},
        {"location": ["Dock"]},
        {"memory_updates": [{"npc_name": "Maren", "event": "Nodded", "emotional_weight": 2}]},
    ],
)
def test_an_opening_extraction_with_a_value_of_another_type_registers_nothing(wrong: dict[str, object]) -> None:
    answer = _answer(opening_npc("Maren", "A smuggler", "neutral"), location="Dock", scene_context="Fog.") | wrong
    setup = call_opening_setup(MockProvider(json.dumps(answer)), "Fog on the dock.", make_game_state())
    assert setup == OpeningSetup(npcs=[], location="", scene_context="", memory_updates=[], deceased_npcs=[])
