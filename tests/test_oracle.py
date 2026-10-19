import pytest

from straightjacket.engine.setting import loader
from straightjacket.engine.setting.loader import load_setting
from straightjacket.engine.setting.packages import list_packages


def test_all_settings_load_oracles() -> None:
    for setting_id in list_packages():
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
        row = table.roll()
        assert row in table.rows
        assert row.text


def test_roll_distribution_covers_range() -> None:
    sf = load_setting("starforged")
    table = sf.oracle("core/action")
    assert table is not None
    results = {table.roll().text for _ in range(100)}
    assert len(results) > 20, f"Only {len(results)} distinct values in 100 rolls"


def test_a_row_of_a_shared_table_without_a_roll_is_left_out() -> None:
    table = load_setting("starforged").oracle("planet/furnace/atmosphere")
    assert table is not None
    assert "Ideal" not in {row.text for row in table.rows}
    assert {table.roll().text for _ in range(200)} <= {row.text for row in table.rows}


def test_a_table_rolls_over_the_rows_it_holds(monkeypatch: pytest.MonkeyPatch) -> None:
    table = load_setting("sundered_isles").oracle("overland/region_landmarks/highlands")
    assert table is not None
    ranges: list[tuple[int, int]] = []
    monkeypatch.setattr(loader.random, "randint", lambda low, high: ranges.append((low, high)) or high)
    assert table.roll() is table.rows[-1]
    assert ranges == [(1, 50)]


def test_oracle_unknown_path_returns_none() -> None:
    sf = load_setting("starforged")
    assert sf.oracle("nonexistent/path") is None


def test_an_oracle_path_missing_from_the_setting_chain_raises() -> None:
    from straightjacket.engine.setting.packages import load_package

    with pytest.raises(KeyError, match="nonexistent/path"):
        load_package("sundered_isles").oracle_table("nonexistent/path")


def test_an_oracle_table_comes_from_the_parent_setting() -> None:
    from straightjacket.engine.setting.packages import load_package

    path = "launching_your_campaign/character/backstory"
    sundered = load_package("sundered_isles")
    assert sundered.data.oracle(path) is None
    assert sundered.has_oracle(path)
    assert sundered.oracle_table(path) is load_package("starforged").data.oracle(path)


def test_setting_isolation() -> None:
    sf = load_setting("starforged")
    cl = load_setting("classic")

    assert sf.oracle("core/action") is not None
    assert cl.oracle("core/action") is None

    assert cl.oracle("action_and_theme/action") is not None
    assert sf.oracle("action_and_theme/action") is None
