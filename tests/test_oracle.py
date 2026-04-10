#!/usr/bin/env python3
"""Tests for oracle roller: loading, rolling, tool registration, setting isolation.

Run: python -m pytest tests/test_oracle.py -v
"""

import importlib

import straightjacket.engine.tools.builtins as _builtins_mod
from straightjacket.engine.datasworn.loader import load_setting, list_available
from straightjacket.engine.models import GameState
from straightjacket.engine.tools.registry import get_handler, get_tools


def _reload_builtins() -> None:
    """Force re-execution of @register decorators after clear_registry()."""
    importlib.reload(_builtins_mod)


# ── Oracle loading per setting ───────────────────────────────────


def test_all_settings_load_oracles() -> None:
    """Every available setting loads with at least one oracle table."""
    for setting_id in list_available():
        s = load_setting(setting_id)
        assert len(s.oracle_ids()) > 0, f"{setting_id} has no oracle tables"


def test_starforged_has_core_action() -> None:
    sf = load_setting("starforged")
    table = sf.oracle("core/action")
    assert table is not None
    assert len(table.rows) == 100


def test_classic_has_action_theme() -> None:
    cl = load_setting("classic")
    table = cl.oracle("action_and_theme/action")
    assert table is not None
    assert len(table.rows) == 100


def test_sundered_isles_loads() -> None:
    si = load_setting("sundered_isles")
    assert len(si.oracle_ids()) > 200


def test_delve_loads() -> None:
    de = load_setting("delve")
    assert len(de.oracle_ids()) > 10


# ── Roll distribution ────────────────────────────────────────────


def test_roll_returns_valid_row() -> None:
    sf = load_setting("starforged")
    table = sf.oracle("core/action")
    assert table is not None
    for _ in range(50):
        result = table.roll()
        assert 1 <= result.roll <= 100
        assert result.value
        assert result.table_path == "core/action"


def test_roll_distribution_covers_range() -> None:
    """100 rolls on a 100-row table should hit multiple distinct values."""
    sf = load_setting("starforged")
    table = sf.oracle("core/action")
    assert table is not None
    results = {table.roll().value for _ in range(100)}
    assert len(results) > 20, f"Only {len(results)} distinct values in 100 rolls"


# ── Unknown path handling ────────────────────────────────────────


def test_oracle_unknown_path_returns_none() -> None:
    sf = load_setting("starforged")
    assert sf.oracle("nonexistent/path") is None


def test_roll_oracle_unknown_path_raises() -> None:
    sf = load_setting("starforged")
    try:
        sf.roll_oracle("nonexistent/path")
        raise AssertionError("Should have raised KeyError")
    except KeyError:
        pass


# ── Setting isolation ────────────────────────────────────────────


def test_setting_isolation() -> None:
    """Starforged tables are not in Classic and vice versa."""
    sf = load_setting("starforged")
    cl = load_setting("classic")
    # core/action is Starforged-specific
    assert sf.oracle("core/action") is not None
    assert cl.oracle("core/action") is None
    # action_and_theme/action is Classic-specific
    assert cl.oracle("action_and_theme/action") is not None
    assert sf.oracle("action_and_theme/action") is None


# ── Tool registration ───────────────────────────────────────────


def test_roll_oracle_registered_for_brain() -> None:
    _reload_builtins()
    handler = get_handler("brain", "roll_oracle")
    assert handler is not None


def test_roll_oracle_not_registered_for_director() -> None:
    _reload_builtins()
    handler = get_handler("director", "roll_oracle")
    assert handler is None


def test_roll_oracle_tool_schema() -> None:
    _reload_builtins()
    tools = get_tools("brain")
    oracle_tools = [t for t in tools if t["function"]["name"] == "roll_oracle"]
    assert len(oracle_tools) == 1
    func = oracle_tools[0]["function"]
    assert "table_path" in func["parameters"]["properties"]
    assert func["parameters"]["properties"]["table_path"]["type"] == "string"
    assert "table_path" in func["parameters"]["required"]


# ── Tool execution ───────────────────────────────────────────────


def test_roll_oracle_tool_success() -> None:
    _reload_builtins()
    handler = get_handler("brain", "roll_oracle")
    assert handler is not None
    game = GameState(setting_id="starforged")
    result = handler(game=game, table_path="core/action")
    assert "value" in result
    assert result["table_path"] == "core/action"
    assert result["setting"] == "starforged"
    assert result["value"]  # non-empty string


def test_roll_oracle_tool_unknown_table() -> None:
    _reload_builtins()
    handler = get_handler("brain", "roll_oracle")
    assert handler is not None
    game = GameState(setting_id="starforged")
    result = handler(game=game, table_path="nonexistent/table")
    assert "error" in result
    assert "not found" in result["error"]


def test_roll_oracle_tool_no_setting() -> None:
    _reload_builtins()
    handler = get_handler("brain", "roll_oracle")
    assert handler is not None
    game = GameState()
    result = handler(game=game, table_path="core/action")
    assert "error" in result


def test_roll_oracle_tool_invalid_setting() -> None:
    _reload_builtins()
    handler = get_handler("brain", "roll_oracle")
    assert handler is not None
    game = GameState(setting_id="nonexistent_setting")
    result = handler(game=game, table_path="core/action")
    assert "error" in result


def test_roll_oracle_tool_per_setting() -> None:
    """Tool uses game.setting_id to select the correct setting."""
    _reload_builtins()
    handler = get_handler("brain", "roll_oracle")
    assert handler is not None
    # Starforged has core/action
    game_sf = GameState(setting_id="starforged")
    result_sf = handler(game=game_sf, table_path="core/action")
    assert "value" in result_sf

    # Classic does NOT have core/action
    game_cl = GameState(setting_id="classic")
    result_cl = handler(game=game_cl, table_path="core/action")
    assert "error" in result_cl

    # Classic has action_and_theme/action
    result_cl2 = handler(game=game_cl, table_path="action_and_theme/action")
    assert "value" in result_cl2
