import importlib

import straightjacket.engine.tools.builtins as _builtins_mod
from straightjacket.engine.datasworn.loader import load_setting, list_available
from straightjacket.engine.tools.registry import get_handler
from tests._helpers import make_game_state


def _reload_builtins() -> None:
    importlib.reload(_builtins_mod)


def test_all_settings_load_oracles() -> None:
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
    sf = load_setting("starforged")
    table = sf.oracle("core/action")
    assert table is not None
    results = {table.roll().value for _ in range(100)}
    assert len(results) > 20, f"Only {len(results)} distinct values in 100 rolls"


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


def test_setting_isolation() -> None:
    sf = load_setting("starforged")
    cl = load_setting("classic")

    assert sf.oracle("core/action") is not None
    assert cl.oracle("core/action") is None

    assert cl.oracle("action_and_theme/action") is not None
    assert sf.oracle("action_and_theme/action") is None


def test_roll_oracle_not_registered_for_brain() -> None:
    _reload_builtins()
    handler = get_handler("brain", "roll_oracle")
    assert handler is None


def test_roll_oracle_not_registered_for_director() -> None:
    _reload_builtins()
    handler = get_handler("director", "roll_oracle")
    assert handler is None


def test_roll_oracle_success() -> None:
    from straightjacket.engine.tools.builtins import roll_oracle

    game = make_game_state(setting_id="starforged")
    result = roll_oracle(game=game, table_path="core/action")
    assert "value" in result
    assert result["table_path"] == "core/action"
    assert result["setting"] == "starforged"
    assert result["value"]


def test_roll_oracle_unknown_table() -> None:
    from straightjacket.engine.tools.builtins import roll_oracle

    game = make_game_state(setting_id="starforged")
    result = roll_oracle(game=game, table_path="nonexistent/table")
    assert "error" in result
    assert "not found" in result["error"]


def test_roll_oracle_no_setting() -> None:
    from straightjacket.engine.tools.builtins import roll_oracle

    game = make_game_state()
    result = roll_oracle(game=game, table_path="core/action")
    assert "error" in result


def test_roll_oracle_invalid_setting() -> None:
    from straightjacket.engine.tools.builtins import roll_oracle

    game = make_game_state(setting_id="nonexistent_setting")
    result = roll_oracle(game=game, table_path="core/action")
    assert "error" in result


def test_roll_oracle_per_setting() -> None:
    from straightjacket.engine.tools.builtins import roll_oracle

    game_sf = make_game_state(setting_id="starforged")
    result_sf = roll_oracle(game=game_sf, table_path="core/action")
    assert "value" in result_sf

    game_cl = make_game_state(setting_id="classic")
    result_cl = roll_oracle(game=game_cl, table_path="core/action")
    assert "error" in result_cl

    result_cl2 = roll_oracle(game=game_cl, table_path="action_and_theme/action")
    assert "value" in result_cl2
