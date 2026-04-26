from __future__ import annotations

import random

import pytest

from straightjacket.engine.engine_loader import eng
from straightjacket.engine.mechanics.adventure_crafter import (
    PlotPointResult,
    _META_HANDLERS,
    _load_ac_data,
    _validate_random_themes,
    assign_themes,
    dispatch_meta,
    get_meta_handler_names,
    lookup_meta_plot_point,
    lookup_plot_point,
)


_SPECIAL_BOUNDARIES = [
    (1, "conclusion"),
    (8, "conclusion"),
    (9, "none"),
    (24, "none"),
    (25, None),
    (95, None),
    (96, "meta"),
    (100, "meta"),
]


def test_ac_config_loads_required_fields():
    cfg = eng().adventure_crafter
    assert cfg.themes == ["action", "tension", "mystery", "social", "personal"]
    assert cfg.theme_slots == 5

    assert len(cfg.theme_die_table) == 10
    assert set(cfg.theme_die_table.values()) == set(cfg.themes)
    sr = cfg.special_ranges
    assert (sr.conclusion_min, sr.conclusion_max) == (1, 8)
    assert (sr.none_min, sr.none_max) == (9, 24)
    assert (sr.meta_min, sr.meta_max) == (96, 100)


def test_ac_data_validation_passes_on_real_data():
    data = _load_ac_data()
    _validate_random_themes(data)


def test_ac_data_validation_raises_on_theme_mismatch():
    bad = {
        "random_themes": [
            {"min": 1, "max": 2, "theme": "action"},
            {"min": 3, "max": 4, "theme": "tension"},
            {"min": 5, "max": 6, "theme": "mystery"},
            {"min": 7, "max": 8, "theme": "social"},
            {"min": 9, "max": 10, "theme": "horror"},
        ]
    }
    with pytest.raises(ValueError, match="theme_die_table"):
        _validate_random_themes(bad)


def test_assign_themes_returns_theme_slots_entries():
    rng = random.Random(0)
    out = assign_themes(rng)
    assert len(out) == eng().adventure_crafter.theme_slots
    for theme in out:
        assert theme in eng().adventure_crafter.themes


def test_assign_themes_deterministic_with_seed():
    a = assign_themes(random.Random(123))
    b = assign_themes(random.Random(123))
    assert a == b
    c = assign_themes(random.Random(124))

    assert a != c or len(a) == 0


@pytest.mark.parametrize("theme", ["action", "tension", "mystery", "social", "personal"])
@pytest.mark.parametrize("roll,expected_special", _SPECIAL_BOUNDARIES)
def test_plot_point_lookup_at_boundaries(theme: str, roll: int, expected_special: str | None):
    result = lookup_plot_point(theme, roll)
    assert isinstance(result, PlotPointResult)
    assert result.special_range == expected_special
    if expected_special == "conclusion":
        assert result.name == "Conclusion"
    elif expected_special == "none":
        assert result.name == "None"
    elif expected_special == "meta":
        assert result.name == "Meta"


@pytest.mark.parametrize("theme", ["action", "tension", "mystery", "social", "personal"])
def test_plot_point_lookup_covers_full_d100(theme: str):
    for roll in range(1, 101):
        result = lookup_plot_point(theme, roll)
        assert result.name


def test_plot_point_lookup_unknown_theme_raises():
    with pytest.raises(KeyError, match="unknown theme"):
        lookup_plot_point("horror", 50)


@pytest.mark.parametrize("bad_roll", [0, -1, 101, 200])
def test_plot_point_lookup_out_of_range_roll_raises(bad_roll: int):
    with pytest.raises(ValueError, match="outside 1..100"):
        lookup_plot_point("action", bad_roll)


def test_meta_handlers_match_json_names():
    data = _load_ac_data()
    json_names = {entry["name"] for entry in data["meta_plot_points"]}
    handler_names = set(get_meta_handler_names())
    assert json_names == handler_names, f"drift between JSON {json_names} and handlers {handler_names}"


def test_meta_lookup_covers_full_d100():
    for roll in range(1, 101):
        name = lookup_meta_plot_point(roll)
        assert name in _META_HANDLERS


@pytest.mark.parametrize(
    "roll,expected_name",
    [
        (1, "Character Exits The Adventure"),
        (18, "Character Exits The Adventure"),
        (19, "Character Returns"),
        (27, "Character Returns"),
        (28, "Character Steps Up"),
        (36, "Character Steps Up"),
        (37, "Character Steps Down"),
        (55, "Character Steps Down"),
        (56, "Character Downgrade"),
        (73, "Character Downgrade"),
        (74, "Character Upgrade"),
        (82, "Character Upgrade"),
        (83, "Plotline Combo"),
        (100, "Plotline Combo"),
    ],
)
def test_meta_lookup_at_boundaries(roll: int, expected_name: str):
    assert lookup_meta_plot_point(roll) == expected_name


@pytest.mark.parametrize("bad_roll", [0, -1, 101, 200])
def test_meta_lookup_out_of_range_roll_raises(bad_roll: int):
    with pytest.raises(ValueError, match="outside 1..100"):
        lookup_meta_plot_point(bad_roll)


def test_dispatch_meta_routes_to_handler_and_handler_raises_not_implemented():
    for roll in [1, 19, 28, 37, 56, 74, 83]:
        with pytest.raises(NotImplementedError, match="step 6"):
            dispatch_meta(roll, {})


def test_dispatch_meta_unknown_name_raises_keyerror(monkeypatch):
    def fake_lookup(_roll: int) -> str:
        return "Plot Twist"

    monkeypatch.setattr(
        "straightjacket.engine.mechanics.adventure_crafter.lookup_meta_plot_point",
        fake_lookup,
    )
    with pytest.raises(KeyError, match="drifted"):
        dispatch_meta(50, {})


def test_plot_points_data_has_186_entries():
    data = _load_ac_data()
    assert len(data["plot_points"]) == 186


def test_plot_points_round_trip_special_entries():
    data = _load_ac_data()
    by_name = {entry["name"]: entry for entry in data["plot_points"]}
    sr = eng().adventure_crafter.special_ranges
    for name, expected in [
        ("Conclusion", (sr.conclusion_min, sr.conclusion_max)),
        ("None", (sr.none_min, sr.none_max)),
        ("Meta", (sr.meta_min, sr.meta_max)),
    ]:
        assert name in by_name, f"{name} missing from plot_points"
        themes = by_name[name]["themes"]
        assert set(themes.keys()) == set(eng().adventure_crafter.themes), f"{name} missing a theme"
        for t, range_ in themes.items():
            assert (
                range_["min"],
                range_["max"],
            ) == expected, f"{name}.{t} has range ({range_['min']}, {range_['max']}) != yaml {expected}"
