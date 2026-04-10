#!/usr/bin/env python3
"""Tests for tool calling infrastructure: registry, handler, builtins.

Run: python -m pytest tests/test_tools.py -v
"""

# Stubs are set up in conftest.py

from straightjacket.engine.db.connection import close_db, reset_db
from straightjacket.engine.db.sync import sync
from straightjacket.engine.models import (
    ClockData,
    GameState,
    MemoryEntry,
    NpcData,
    ThreadEntry,
)
from straightjacket.engine.tools.registry import (
    _build_definition,
    clear_registry,
    get_handler,
    get_tools,
    list_tools,
    register,
)
from straightjacket.engine.tools.handler import execute_tool_call


def _fresh_db():
    return reset_db()


def _game_with_data() -> GameState:
    """GameState with NPCs, threads, clocks for tool testing."""
    game = GameState(player_name="Ash", setting_id="starforged")
    game.npcs = [
        NpcData(
            id="npc_1",
            name="Kira",
            agenda="Access the vault",
            disposition="distrustful",
            bond=1,
            status="active",
            last_location="docks",
            memory=[
                MemoryEntry(scene=1, event="Met at the docks", importance=5, emotional_weight="curious"),
                MemoryEntry(scene=3, event="Broke a promise", importance=8, emotional_weight="betrayed"),
            ],
        ),
        NpcData(
            id="npc_2",
            name="Rowan",
            disposition="friendly",
            bond=3,
            status="active",
            memory=[
                MemoryEntry(scene=2, event="Healed the player", importance=4, type="observation"),
            ],
        ),
    ]
    game.narrative.threads.append(
        ThreadEntry(id="thread_1", name="Find the vault", thread_type="vow", weight=2, active=True)
    )
    game.world.clocks.append(ClockData(name="Vault heist", clock_type="scheme", segments=6, filled=2, owner="Kira"))
    game.world.clocks.append(
        ClockData(name="Storm", clock_type="threat", segments=4, filled=4, fired=True, fired_at_scene=5)
    )
    return game


# ── Registry ──────────────────────────────────────────────────


def test_register_decorator() -> None:
    clear_registry()

    @register("test_role")
    def my_tool(game: GameState, query: str) -> dict:
        """Search for something.

        query: what to search for
        """
        return {"result": query}

    assert "my_tool" in list_tools("test_role")
    assert get_handler("test_role", "my_tool") is my_tool
    clear_registry()


def test_register_multiple_roles() -> None:
    clear_registry()

    @register("brain", "director")
    def shared_tool(game: GameState, x: int) -> dict:
        """A shared tool."""
        return {"x": x}

    assert "shared_tool" in list_tools("brain")
    assert "shared_tool" in list_tools("director")
    clear_registry()


def test_get_tools_format() -> None:
    clear_registry()

    @register("test")
    def example(game: GameState, name: str, count: int = 5) -> dict:
        """Look up something by name.

        name: the name to look up
        count: how many results
        """
        return {}

    tools = get_tools("test")
    assert len(tools) == 1
    defn = tools[0]
    assert defn["type"] == "function"
    func = defn["function"]
    assert func["name"] == "example"
    assert func["description"] == "Look up something by name."
    params = func["parameters"]
    assert "name" in params["properties"]
    assert params["properties"]["name"]["type"] == "string"
    assert params["properties"]["count"]["type"] == "integer"
    assert "name" in params["required"]
    assert "count" not in params["required"]  # has default
    assert "game" not in params["properties"]  # injected, not exposed
    clear_registry()


def test_get_tools_empty_role() -> None:
    clear_registry()
    assert get_tools("nonexistent") == []
    clear_registry()


def test_get_handler_unknown() -> None:
    clear_registry()
    assert get_handler("brain", "nonexistent") is None
    clear_registry()


def test_build_definition_types() -> None:
    def typed_func(game: GameState, name: str, count: int, ratio: float, flag: bool) -> dict:
        """A typed function."""
        return {}

    defn = _build_definition(typed_func)
    props = defn["function"]["parameters"]["properties"]
    assert props["name"]["type"] == "string"
    assert props["count"]["type"] == "integer"
    assert props["ratio"]["type"] == "number"
    assert props["flag"]["type"] == "boolean"


# ── Handler ───────────────────────────────────────────────────


def test_execute_tool_call_success() -> None:
    clear_registry()

    @register("test")
    def echo(game: GameState, message: str) -> dict:
        """Echo a message."""
        return {"echo": message}

    game = GameState()
    result = execute_tool_call("test", {"name": "echo", "arguments": {"message": "hello"}}, game)
    assert '"echo": "hello"' in result
    clear_registry()


def test_execute_tool_call_unknown() -> None:
    clear_registry()
    game = GameState()
    result = execute_tool_call("test", {"name": "nonexistent", "arguments": {}}, game)
    assert "unknown tool" in result
    clear_registry()


def test_execute_tool_call_error() -> None:
    clear_registry()

    @register("test")
    def broken(game: GameState) -> dict:
        """Always fails."""
        raise ValueError("boom")

    game = GameState()
    result = execute_tool_call("test", {"name": "broken", "arguments": {}}, game)
    assert "failed" in result
    assert "boom" in result
    clear_registry()


# ── Builtins ──────────────────────────────────────────────────
# Import builtins module-level to trigger @register decorators once.
# Tests that call clear_registry() must re-import to re-register.

import importlib
import straightjacket.engine.tools.builtins as _builtins_mod


def _reload_builtins() -> None:
    """Force re-execution of @register decorators after clear_registry()."""
    importlib.reload(_builtins_mod)


def test_builtin_query_npc() -> None:
    _fresh_db()
    game = _game_with_data()
    sync(game)
    _reload_builtins()

    handler = get_handler("director", "query_npc")
    assert handler is not None
    result = handler(game=game, npc_id="npc_1")
    assert result["name"] == "Kira"
    assert result["disposition"] == "distrustful"
    assert len(result["recent_memories"]) == 2
    close_db()


def test_builtin_query_npc_not_found() -> None:
    _fresh_db()
    game = _game_with_data()
    sync(game)
    _reload_builtins()

    handler = get_handler("director", "query_npc")
    result = handler(game=game, npc_id="nonexistent")
    assert "error" in result
    close_db()


def test_builtin_query_active_threads() -> None:
    _fresh_db()
    game = _game_with_data()
    sync(game)
    _reload_builtins()

    handler = get_handler("director", "query_active_threads")
    assert handler is not None
    result = handler(game=game, active_only=True)
    assert len(result["threads"]) == 1
    assert result["threads"][0]["name"] == "Find the vault"
    close_db()


def test_builtin_query_active_clocks() -> None:
    _fresh_db()
    game = _game_with_data()
    sync(game)
    _reload_builtins()

    handler = get_handler("director", "query_active_clocks")
    assert handler is not None
    result = handler(game=game, unfired_only=True)
    assert len(result["clocks"]) == 1
    assert result["clocks"][0]["name"] == "Vault heist"
    close_db()


def test_builtin_query_npc_list() -> None:
    _fresh_db()
    game = _game_with_data()
    sync(game)
    _reload_builtins()

    handler = get_handler("brain", "query_npc_list")
    assert handler is not None
    result = handler(game=game, status="active")
    assert len(result["npcs"]) == 2
    names = {n["name"] for n in result["npcs"]}
    assert "Kira" in names
    assert "Rowan" in names
    close_db()


def test_builtin_query_npc_shared_registration() -> None:
    """query_npc is registered for both brain and director."""
    _reload_builtins()
    assert get_handler("brain", "query_npc") is not None
    assert get_handler("director", "query_npc") is not None
