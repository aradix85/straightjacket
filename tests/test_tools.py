import sqlite3

from straightjacket.engine.db.connection import close_db, reset_db
from straightjacket.engine.db.sync import sync
from straightjacket.engine.models import (
    GameState,
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


def _fresh_db() -> sqlite3.Connection:
    return reset_db()


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
    game.world.clocks.append(make_clock(name="Vault heist", clock_type="scheme", segments=6, filled=2, owner="Kira"))
    game.world.clocks.append(
        make_clock(name="Storm", clock_type="threat", segments=4, filled=4, fired=True, fired_at_scene=5)
    )
    return game


def test_register_decorator() -> None:
    clear_registry()

    @register("test_role", description="my tool")
    def my_tool(game: GameState, query: str) -> dict:
        return {"result": query}

    assert "my_tool" in list_tools("test_role")
    assert get_handler("test_role", "my_tool") is my_tool
    clear_registry()


def test_register_multiple_roles() -> None:
    clear_registry()

    @register("brain", "director", description="shared between roles")
    def shared_tool(game: GameState, x: int) -> dict:
        return {"x": x}

    assert "shared_tool" in list_tools("brain")
    assert "shared_tool" in list_tools("director")
    clear_registry()


def test_get_tools_format() -> None:
    clear_registry()

    @register("test", description="Look up something by name.")
    def example(game: GameState, name: str, count: int = 5) -> dict:
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
    assert "count" not in params["required"]
    assert "game" not in params["properties"]
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
        return {}

    defn = _build_definition(typed_func, override_description="typed test")
    props = defn["function"]["parameters"]["properties"]
    assert props["name"]["type"] == "string"
    assert props["count"]["type"] == "integer"
    assert props["ratio"]["type"] == "number"
    assert props["flag"]["type"] == "boolean"


def test_execute_tool_call_success() -> None:
    clear_registry()

    @register("test", description="echo")
    def echo(game: GameState, message: str) -> dict:
        return {"echo": message}

    game = make_game_state()
    result = execute_tool_call("test", {"name": "echo", "arguments": {"message": "hello"}}, game)
    assert '"echo": "hello"' in result
    clear_registry()


def test_execute_tool_call_unknown() -> None:
    clear_registry()
    game = make_game_state()
    result = execute_tool_call("test", {"name": "nonexistent", "arguments": {}}, game)
    assert "unknown tool" in result
    clear_registry()


def test_execute_tool_call_error() -> None:
    clear_registry()

    @register("test", description="raises")
    def broken(game: GameState) -> dict:
        raise ValueError("boom")

    game = make_game_state()
    result = execute_tool_call("test", {"name": "broken", "arguments": {}}, game)
    assert "failed" in result
    assert "boom" in result
    clear_registry()


import importlib
import straightjacket.engine.tools.builtins as _builtins_mod
from tests._helpers import make_clock, make_game_state, make_memory, make_npc


def _reload_builtins() -> None:
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
    assert handler is not None
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
    from straightjacket.engine.tools.builtins import query_npc_list

    _fresh_db()
    game = _game_with_data()
    sync(game)

    result = query_npc_list(game=game, status="active")
    assert len(result["npcs"]) == 2
    names = {n["name"] for n in result["npcs"]}
    assert "Kira" in names
    assert "Rowan" in names
    close_db()


def test_builtin_query_npc_director_only() -> None:
    _reload_builtins()
    assert get_handler("brain", "query_npc") is None
    assert get_handler("director", "query_npc") is not None


def test_run_tool_loop_completes_after_tool_use(load_engine: None) -> None:
    from straightjacket.engine.ai.provider_base import AIResponse
    from straightjacket.engine.tools.handler import run_tool_loop

    clear_registry()

    @register("test", description="echo a message", params={"message": "the message"})
    def echo(game: GameState, message: str = "x") -> dict:
        return {"echo": message}

    initial = AIResponse(
        content="thinking",
        stop_reason="tool_use",
        tool_calls=[{"id": "c1", "name": "echo", "arguments": {"message": "hi"}}],
    )

    class _Provider:
        def __init__(self) -> None:
            self.calls = 0

        def create_message(self, **kwargs: object) -> AIResponse:
            self.calls += 1
            return AIResponse(content="final answer", stop_reason="complete")

    game = make_game_state(player_name="Test")
    final, log = run_tool_loop(
        _Provider(),
        initial,
        role="test",
        game=game,
        model="m",
        system="s",
        messages=[{"role": "user", "content": "do thing"}],
        max_tokens=100,
    )
    assert final == "final answer"
    assert len(log) == 1
    assert log[0]["name"] == "echo"
    assert "hi" in log[0]["result"]


def test_run_tool_loop_no_tool_calls_returns_immediately(load_engine: None) -> None:
    from straightjacket.engine.ai.provider_base import AIResponse
    from straightjacket.engine.tools.handler import run_tool_loop

    initial = AIResponse(content="just text", stop_reason="complete")

    class _Provider:
        def create_message(self, **kwargs: object) -> AIResponse:
            raise AssertionError("should not be called")

    game = make_game_state(player_name="Test")
    final, log = run_tool_loop(
        _Provider(),
        initial,
        role="test",
        game=game,
        model="m",
        system="s",
        messages=[{"role": "user", "content": "x"}],
        max_tokens=100,
    )
    assert final == "just text"
    assert log == []


def test_run_tool_loop_hits_max_rounds(load_engine: None) -> None:
    from straightjacket.engine.ai.provider_base import AIResponse
    from straightjacket.engine.tools.handler import run_tool_loop

    clear_registry()

    @register("test", description="loop forever")
    def loop(game: GameState) -> dict:
        return {"ok": True}

    initial = AIResponse(
        content="",
        stop_reason="tool_use",
        tool_calls=[{"id": "c0", "name": "loop", "arguments": {}}],
    )

    class _Provider:
        def create_message(self, **kwargs: object) -> AIResponse:
            return AIResponse(
                content="",
                stop_reason="tool_use",
                tool_calls=[{"id": "cN", "name": "loop", "arguments": {}}],
            )

    game = make_game_state(player_name="Test")
    final, log = run_tool_loop(
        _Provider(),
        initial,
        role="test",
        game=game,
        model="m",
        system="s",
        messages=[{"role": "user", "content": "x"}],
        max_tokens=100,
        max_tool_rounds=2,
    )
    assert len(log) == 2
