import json
from typing import Any

import pytest

from straightjacket.engine.engine_loader import eng
from straightjacket.engine.models import GameState, ThreadEntry
from straightjacket.engine.tools import execute_tool_call, get_tools, handler, registry
from straightjacket.engine.tools.builtins import query_game_state
from tests._helpers import make_clock, make_game_state, make_memory, make_npc


def _game_with_data() -> GameState:
    game = make_game_state(player_name="Ash", setting_id="starforged")
    game.npcs = [
        make_npc(
            id="npc_1",
            name="Kira",
            agenda="Access the vault",
            disposition="distrustful",
            status="active",
            last_location="docks",
            memory=[
                make_memory(scene=1, event="Met at the docks", importance=5, emotional_weight="curious"),
                make_memory(scene=3, event="Broke a promise", importance=8, emotional_weight="betrayed"),
            ],
        ),
        make_npc(
            id="npc_2",
            name="Rowan",
            disposition="friendly",
            status="active",
            memory=[
                make_memory(scene=2, event="Healed the player", importance=4, type="observation"),
            ],
        ),
    ]
    game.narrative.threads.append(
        ThreadEntry(id="thread_1", name="Find the vault", thread_type="vow", weight=2, active=True, source="creation")
    )
    game.world.clocks.append(
        make_clock(name="Vault heist", clock_type="scheme", segments=6, filled=2, owner_kind="npc", owner_id="Kira")
    )
    game.world.clocks.append(
        make_clock(name="Storm", clock_type="threat", segments=4, filled=4, fired=True, fired_at_scene=5)
    )
    return game


def test_the_director_is_offered_its_one_tool_without_parameters() -> None:
    [definition] = get_tools()
    assert definition == {
        "type": "function",
        "function": {
            "name": "query_game_state",
            "description": eng().get_raw("tool_descriptions")["query_game_state"],
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }


def test_query_game_state_returns_threads_clocks_and_npcs_at_once() -> None:
    result = query_game_state(_game_with_data())
    assert [t["name"] for t in result["threads"]] == ["Find the vault"]
    assert [c["name"] for c in result["clocks"]] == ["Vault heist"]
    kira = next(n for n in result["npcs"] if n["id"] == "npc_1")
    assert kira["name"] == "Kira"
    assert kira["disposition"] == "distrustful"
    assert len(kira["recent_memories"]) == 2


def test_query_game_state_shows_the_memories_the_reflection_block_shows(load_engine: None) -> None:
    from straightjacket.engine.director import _build_reflection_block

    game = _game_with_data()
    kira = game.npcs[0]
    kira.memory.append(make_memory(scene=4, event="Doubts the player", importance=6, type="reflection"))
    shown = next(n for n in query_game_state(game)["npcs"] if n["id"] == "npc_1")["recent_memories"]
    assert [m["event"] for m in shown] == ["Met at the docks", "Broke a promise"]
    block = _build_reflection_block(game, kira)
    assert all(m["event"] in block for m in shown)


def test_query_game_state_leaves_out_dead_and_lore_npcs(load_engine: None) -> None:
    game = make_game_state()
    game.npcs = [
        make_npc(id="npc_1", name="Mira", status="active"),
        make_npc(id="npc_2", name="Tobin", status="background"),
        make_npc(id="npc_9", name="Old Vess", status="deceased"),
        make_npc(id="npc_8", name="The Founder", status="lore"),
    ]
    assert [n["id"] for n in query_game_state(game)["npcs"]] == ["npc_1", "npc_2"]


def test_a_tool_call_returns_the_tools_answer_as_json() -> None:
    game = _game_with_data()
    assert json.loads(execute_tool_call("query_game_state", {}, game)) == json.loads(json.dumps(query_game_state(game)))


def test_arguments_the_tool_does_not_take_are_ignored_and_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(handler, "log", lambda msg, level="info": warnings.append(msg) if level == "warning" else None)
    answer = json.loads(execute_tool_call("query_game_state", {"threads": True, "npc_id": "npc_1"}, _game_with_data()))
    assert answer["ignored_arguments"] == ["npc_id", "threads"]
    assert [t["name"] for t in answer["threads"]] == ["Find the vault"]
    assert warnings == ["[Tools] query_game_state: ignored arguments it does not take: npc_id, threads"]


def test_an_unknown_tool_answers_with_an_error() -> None:
    answer = json.loads(execute_tool_call("respond", {}, make_game_state()))
    assert answer == {"error": "unknown tool: respond"}


def test_an_engine_fault_in_a_tool_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(game: GameState) -> dict[str, Any]:
        raise KeyError("missing")

    monkeypatch.setitem(registry._registry, "broken", (broken, {}))
    with pytest.raises(KeyError, match="missing"):
        execute_tool_call("broken", {}, make_game_state())
