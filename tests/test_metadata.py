import json

import pytest
from typing_extensions import override

from straightjacket.engine.ai.metadata import apply_narrator_metadata, process_deceased_npcs
from straightjacket.engine.ai.narrator import call_narrator_metadata
from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse
from straightjacket.engine.game import process_turn
from straightjacket.engine.models import DeceasedNpc, GameState, NarratorMetadata
from tests._creation import TurnProvider, brain_answer, force_result, library_game
from tests._helpers import friendly_kira, make_brain_result, make_game_state, make_memory, make_npc, schema_of
from tests._mocks import MockProvider, make_test_game


def _game() -> GameState:
    game = make_game_state(player_name="Hero")
    game.narrative.scene_count = 5
    game.world.current_location = "Tavern"
    game.world.time_of_day = "evening"
    game.npcs = [
        friendly_kira(
            status="active",
            last_location="Tavern",
            memory=[make_memory(scene=4, event="Talked to player", importance=3)],
        ),
        make_npc(id="npc_2", name="Borin", disposition="neutral", status="active", last_location="Tavern"),
    ]
    return game


def _answer(**reported: object) -> dict[str, object]:
    return {"new_npcs": [], "npc_renames": [], "npc_details": [], "deceased_npcs": [], "lore_npcs": [], **reported}


def _apply(game: GameState, present: set[str], **reported: list[dict[str, str]]) -> None:
    metadata = NarratorMetadata.from_dict(_answer(**reported))
    apply_narrator_metadata(game, metadata, scene_present_ids=present, world_addition="")


def test_a_reported_death_marks_an_npc_present_in_the_scene() -> None:
    game = _game()
    _apply(game, {"npc_1"}, deceased_npcs=[{"npc_id": "npc_1"}])
    assert game.npcs[0].status == "deceased"


def test_a_reported_death_of_an_npc_not_in_the_scene_is_refused() -> None:
    game = _game()
    _apply(game, {"npc_2"}, deceased_npcs=[{"npc_id": "npc_1"}])
    assert game.npcs[0].status == "active"


def test_a_reported_death_of_an_npc_with_a_memory_of_this_scene_is_taken() -> None:
    game = _game()
    game.npcs[0].memory.append(make_memory(scene=5, event="Just arrived", importance=5))
    _apply(game, {"npc_2"}, deceased_npcs=[{"npc_id": "npc_1"}])
    assert game.npcs[0].status == "deceased"


def test_a_reported_death_of_an_unknown_npc_changes_nothing() -> None:
    game = _game()
    _apply(game, {"npc_1", "npc_2"}, deceased_npcs=[{"npc_id": "nobody"}])
    assert [n.status for n in game.npcs] == ["active", "active"]


def test_an_openings_reported_death_needs_no_presence() -> None:
    game = _game()
    process_deceased_npcs(game, [DeceasedNpc(npc_id="npc_1"), DeceasedNpc(npc_id="nobody")])
    assert [n.status for n in game.npcs] == ["deceased", "active"]


def test_a_figure_only_spoken_of_becomes_a_lore_npc() -> None:
    game = _game()
    _apply(game, {"npc_1", "npc_2"}, lore_npcs=[{"name": "Ancient King", "description": "Legendary ruler"}])
    [lore] = [n for n in game.npcs if n.status == "lore"]
    assert (lore.name, lore.description) == ("Ancient King", "Legendary ruler")


def test_a_lore_figure_that_is_known_or_nameless_adds_no_npc() -> None:
    game = _game()
    _apply(
        game,
        {"npc_1", "npc_2"},
        lore_npcs=[{"name": "Kira", "description": "Already exists"}, {"name": " ", "description": "No name"}],
    )
    assert [n.name for n in game.npcs] == ["Kira", "Borin"]


_ORLA = {"name": "Orla", "description": "a ferrywoman", "disposition": "neutral"}


@pytest.mark.parametrize("rename", [None, {"npc_id": "npc_1", "new_name": "Orla Fenn"}])
def test_a_rename_when_no_npc_is_known_fails_the_extraction_only(rename: object) -> None:
    game = make_game_state(player_name="Hero")
    reply = _answer(new_npcs=[_ORLA], npc_renames=[rename])
    metadata = call_narrator_metadata(MockProvider(json.dumps(reply)), "Orla waits.", game, make_brain_result(), [])
    assert not metadata.npc_renames
    assert not metadata.new_npcs


def test_an_extraction_that_follows_its_schema_is_read_whole() -> None:
    reply = _answer(new_npcs=[_ORLA], npc_details=[{"npc_id": "npc_1", "full_name": None, "description": "Tired."}])
    metadata = call_narrator_metadata(
        MockProvider(json.dumps(reply)), "Orla waits.", make_test_game(), make_brain_result(), []
    )
    assert [(n.name, n.disposition) for n in metadata.new_npcs] == [("Orla", "neutral")]
    assert [(d.npc_id, d.full_name, d.description) for d in metadata.npc_details] == [("npc_1", None, "Tired.")]


def test_a_turn_whose_extraction_brings_a_value_of_another_type_adds_nothing_and_keeps_the_save_loadable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Provider(TurnProvider):
        @override
        def create_message(self, spec: AICallSpec) -> AIResponse:
            if spec.json_schema is not None and "lore_npcs" in schema_of(spec)["properties"]:
                reply = _answer(lore_npcs=[{"name": "Ancient King", "description": 7}])
                return AIResponse(content=json.dumps(reply), usage={"input_tokens": 1, "output_tokens": 1})
            return super().create_message(spec)

    game = library_game()
    known = [n.id for n in game.npcs]
    force_result(monkeypatch, "WEAK_HIT")
    process_turn(Provider(brain_answer(location_change=None)), game, "I search the shelves", stream=None)
    assert [n.id for n in game.npcs] == known
    assert GameState.from_dict(game.to_dict()) == game


@pytest.mark.parametrize(
    "reported",
    [
        {"new_npcs": [_ORLA | {"description": 7}]},
        {"new_npcs": [_ORLA | {"mood": "wary"}]},
        {"npc_details": [{"npc_id": "npc_1", "full_name": ["Kira", "Voss"], "description": None}]},
        {"deceased_npcs": [{"npc_id": None}]},
        {"lore_npcs": "none"},
    ],
)
def test_an_extraction_with_a_value_of_another_type_fails_the_extraction_only(reported: dict[str, object]) -> None:
    reply = _answer(new_npcs=[_ORLA]) | reported
    metadata = call_narrator_metadata(
        MockProvider(json.dumps(reply)), "Orla waits.", make_test_game(), make_brain_result(), []
    )
    assert metadata == NarratorMetadata(new_npcs=[], npc_renames=[], npc_details=[], deceased_npcs=[], lore_npcs=[])
