from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from straightjacket.engine.crafters.adventure_crafter import (
    PlotPointHit,
    PlotPointResult,
    ThemeAlternation,
    TurningPoint,
    assign_themes,
    load_ac_data,
    lookup_characters_template,
    lookup_meta_plot_point,
    lookup_plot_point,
    lookup_plotlines_template,
    lookup_theme_priority,
    roll_turning_point,
)
from straightjacket.engine.crafters.config import crafter
from straightjacket.engine.crafters.meta_plot_points import dispatch_meta
from straightjacket.engine.models import CharacterListEntry, NarrativeState, PlotlineEntry
from tests._helpers import make_character_entry, make_narrative, make_plotline

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


def _present(narrative: NarrativeState, name: str) -> CharacterListEntry:
    entry = make_character_entry(
        id=f"ac_char_{len(narrative.characters_list) + 1}", name=name, entry_type="ac", ac_status="present"
    )
    narrative.characters_list.append(entry)
    return entry


def _plotline(narrative: NarrativeState, name: str) -> PlotlineEntry:
    entry = make_plotline(id=f"ac_plot_{len(narrative.plotlines_list) + 1}", name=name)
    narrative.plotlines_list.append(entry)
    return entry


def _meta(name: str, narrative: NarrativeState, active_plotline_id: str | None = None) -> None:
    dispatch_meta(next(r for r in range(1, 101) if lookup_meta_plot_point(r) == name), narrative, active_plotline_id)


def test_data_whose_themes_disagree_with_the_theme_die_refuses_to_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.crafters import adventure_crafter

    data = json.loads(json.dumps(load_ac_data()))
    data["random_themes"][-1]["theme"] = "horror"
    bad = tmp_path / "adventure_crafter.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(adventure_crafter, "_AC_DATA_PATH", bad)
    monkeypatch.setattr(adventure_crafter, "_ac_data", None)
    with pytest.raises(ValueError, match="theme_die_table"):
        load_ac_data()


def test_assign_themes_returns_theme_slots_entries():
    rng = random.Random(0)
    out = assign_themes(rng)
    assert len(out) == crafter().adventure_crafter.theme_slots
    for theme in out:
        assert theme in crafter().adventure_crafter.themes


def test_assign_themes_deterministic_with_seed():
    a = assign_themes(random.Random(123))
    b = assign_themes(random.Random(123))
    assert a == b
    c = assign_themes(random.Random(124))

    assert a != c or len(a) == 0


@pytest.mark.parametrize("theme", ["action", "tension", "mystery", "social", "personal"])
@pytest.mark.parametrize(("roll", "expected_special"), _SPECIAL_BOUNDARIES)
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
    with pytest.raises(LookupError, match="covers theme='horror'"):
        lookup_plot_point("horror", 50)


@pytest.mark.parametrize("bad_roll", [0, -1, 101, 200])
def test_plot_point_lookup_out_of_range_roll_raises(bad_roll: int):
    with pytest.raises(LookupError, match="covers"):
        lookup_plot_point("action", bad_roll)


@pytest.mark.parametrize(
    ("roll", "expected_name"),
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
    with pytest.raises(LookupError, match="covers"):
        lookup_meta_plot_point(bad_roll)


def test_every_meta_roll_dispatches_to_a_handler():
    narrative = make_narrative()
    for roll in range(1, 101):
        dispatch_meta(roll, narrative, None)


def test_dispatch_meta_unknown_name_raises_keyerror(monkeypatch):
    def fake_lookup(_roll: int) -> str:
        return "Plot Twist"

    monkeypatch.setattr(
        "straightjacket.engine.crafters.meta_plot_points.lookup_meta_plot_point",
        fake_lookup,
    )
    narrative = make_narrative()
    with pytest.raises(KeyError, match="drifted"):
        dispatch_meta(50, narrative, None)


def test_lookup_theme_priority_constant_for_first_three_buckets():
    alt = ThemeAlternation(next_is_4=True)
    assert lookup_theme_priority(1, alt) == 1
    assert lookup_theme_priority(4, alt) == 1
    assert lookup_theme_priority(5, alt) == 2
    assert lookup_theme_priority(7, alt) == 2
    assert lookup_theme_priority(8, alt) == 3
    assert lookup_theme_priority(9, alt) == 3


def test_lookup_theme_priority_alternates_on_ten():
    alt = ThemeAlternation(next_is_4=True)
    first = lookup_theme_priority(10, alt)
    second = lookup_theme_priority(10, alt)
    third = lookup_theme_priority(10, alt)
    assert {first, second, third} == {4, 5}
    assert first == 4
    assert second == 5
    assert third == 4


@pytest.mark.parametrize("bad_roll", [0, -1, 11, 100])
def test_lookup_theme_priority_out_of_range_raises(bad_roll: int):
    with pytest.raises(LookupError, match="covers"):
        lookup_theme_priority(bad_roll, ThemeAlternation(next_is_4=True))


def test_lookup_characters_template_resolves_full_d100():
    seen = set()
    for roll in range(1, 101):
        result = lookup_characters_template(roll)
        assert result in {"new_character", "choose_most_logical"}
        seen.add(result)
    assert seen == {"new_character", "choose_most_logical"}


def test_lookup_plotlines_template_resolves_full_d100():
    seen = set()
    for roll in range(1, 101):
        result = lookup_plotlines_template(roll)
        assert result in {"new_plotline", "choose_most_logical"}
        seen.add(result)
    assert seen == {"new_plotline", "choose_most_logical"}


def test_plotlines_template_weighted_toward_choose_most_logical():
    counts = {"choose_most_logical": 0, "new_plotline": 0}
    for roll in range(1, 101):
        counts[lookup_plotlines_template(roll)] += 1
    assert counts["choose_most_logical"] > counts["new_plotline"]


def test_characters_template_weighted_toward_new_character():
    counts = {"new_character": 0, "choose_most_logical": 0}
    for roll in range(1, 101):
        counts[lookup_characters_template(roll)] += 1
    assert counts["new_character"] > counts["choose_most_logical"]


def test_roll_turning_point_produces_two_to_five_plot_points():
    narrative = make_narrative()
    rng = random.Random(7)
    themes = ["action", "tension", "mystery", "social", "personal"]
    for _ in range(20):
        tp = roll_turning_point(rng, themes, narrative)
        assert isinstance(tp, TurningPoint)
        assert 2 <= len(tp.plot_points) <= 5
        for hit in tp.plot_points:
            assert isinstance(hit, PlotPointHit)
            assert hit.theme in themes


def test_roll_turning_point_themes_length_must_match_theme_slots():
    narrative = make_narrative()
    rng = random.Random(0)
    with pytest.raises(ValueError, match="theme_slots"):
        roll_turning_point(rng, ["action", "tension"], narrative)


def test_roll_turning_point_creates_plotline_on_empty_list():
    narrative = make_narrative()
    rng = random.Random(1)
    themes = ["action", "tension", "mystery", "social", "personal"]
    assert narrative.plotlines_list == []
    roll_turning_point(rng, themes, narrative)
    assert len(narrative.plotlines_list) == 1
    assert narrative.plotlines_list[0].turning_point_count == 1


def test_a_turning_point_names_its_plotline_and_what_it_does_to_it():
    narrative = make_narrative()
    themes = ["action", "tension", "mystery", "social", "personal"]
    tp = roll_turning_point(random.Random(1), themes, narrative)
    assert (tp.plotline, tp.opens_plotline, tp.concludes_plotline) == (narrative.plotlines_list[0].name, True, False)


def test_roll_turning_point_reuses_advancing_plotline():
    narrative = make_narrative()
    _plotline(narrative, "First")
    rng = random.Random(0)
    themes = ["action", "tension", "mystery", "social", "personal"]
    roll_turning_point(rng, themes, narrative)
    assert len(narrative.plotlines_list) in (1, 2)
    if len(narrative.plotlines_list) == 1:
        assert narrative.plotlines_list[0].turning_point_count == 1


def test_conclusion_plot_point_flips_an_advancing_plotline_to_conclusion(monkeypatch):
    narrative = make_narrative()
    _plotline(narrative, "First")
    rng = random.Random(0)
    themes = ["action", "tension", "mystery", "social", "personal"]

    rolls = iter([1] + [1, 1] * 5)

    def fake_randint(a: int, b: int) -> int:
        return next(rolls)

    monkeypatch.setattr(rng, "randint", fake_randint)
    tp = roll_turning_point(rng, themes, narrative)
    assert len(narrative.plotlines_list) == 1
    plotline = narrative.plotlines_list[0]
    assert plotline.status == "conclusion"
    assert (tp.plotline, tp.opens_plotline, tp.concludes_plotline) == ("First", False, True)


def test_meta_character_exits_marks_active_character_exited():

    narrative = make_narrative()
    char = _present(narrative, "Alice")
    _meta("Character Exits The Adventure", narrative)
    assert char.ac_status == "exited"


def test_meta_character_returns_marks_exited_character_returned():

    narrative = make_narrative()
    char = _present(narrative, "Alice")
    char.ac_status = "exited"
    _meta("Character Returns", narrative)
    assert char.ac_status == "returned"


def test_meta_character_returns_creates_new_when_no_exited():

    narrative = make_narrative()
    _meta("Character Returns", narrative)
    assert len(narrative.characters_list) == 1
    assert narrative.characters_list[0].ac_status == "returned"


def test_meta_character_steps_up_increases_weight():

    narrative = make_narrative()
    char = _present(narrative, "Alice")
    initial = char.weight
    _meta("Character Steps Up", narrative)
    expected = initial + crafter().adventure_crafter.meta_handlers.weight_delta_step_up
    assert char.weight == expected


def test_meta_character_steps_down_decreases_weight_to_floor():

    cfg = crafter().adventure_crafter.meta_handlers
    narrative = make_narrative()
    char = _present(narrative, "Alice")
    char.weight = 5
    _meta("Character Steps Down", narrative)
    assert char.weight == 5 + cfg.weight_delta_step_down
    char.weight = cfg.weight_floor
    _meta("Character Steps Down", narrative)
    assert char.weight == cfg.weight_floor


def test_meta_character_downgrade_marks_status_and_decreases_weight():

    cfg = crafter().adventure_crafter.meta_handlers
    narrative = make_narrative()
    char = _present(narrative, "Alice")
    char.weight = 5
    _meta("Character Downgrade", narrative)
    assert char.ac_status == "downgraded"
    assert char.weight == max(cfg.weight_floor, 5 + cfg.weight_delta_downgrade)


def test_meta_character_upgrade_marks_status_and_increases_weight():

    cfg = crafter().adventure_crafter.meta_handlers
    narrative = make_narrative()
    char = _present(narrative, "Alice")
    initial = char.weight
    _meta("Character Upgrade", narrative)
    assert char.ac_status == "upgraded"
    assert char.weight == initial + cfg.weight_delta_upgrade


def test_meta_plotline_combo_merges_two_advancing_plotlines():

    narrative = make_narrative()
    a = _plotline(narrative, "First")
    b = _plotline(narrative, "Second")
    _meta("Plotline Combo", narrative)
    statuses = sorted([a.status, b.status])
    assert "merged" in statuses
    assert statuses.count("advancement") == 1


def test_meta_plotline_combo_skips_when_fewer_than_two_advancing():

    narrative = make_narrative()
    only = _plotline(narrative, "Only one")
    _meta("Plotline Combo", narrative)
    assert only.status == "advancement"


def test_meta_plotline_combo_excludes_active_plotline_id():

    narrative = make_narrative()
    active = _plotline(narrative, "Active")
    _plotline(narrative, "Other")
    _meta("Plotline Combo", narrative, active.id)
    assert active.status == "advancement"


def test_narrative_state_snapshot_restore_round_trips_plotlines_list():
    narrative = make_narrative()
    _plotline(narrative, "Original")
    snap = narrative.snapshot()
    _plotline(narrative, "Mid-turn add")
    assert len(narrative.plotlines_list) == 2
    narrative.restore(snap)
    assert len(narrative.plotlines_list) == 1
    assert narrative.plotlines_list[0].name == "Original"

    data = load_ac_data()
    assert len(data["plot_points"]) == 186


def test_plot_points_round_trip_special_entries():
    data = load_ac_data()
    by_name = {entry["name"]: entry for entry in data["plot_points"]}
    sr = crafter().adventure_crafter.special_ranges
    for name, expected in [
        ("Conclusion", (sr.conclusion_min, sr.conclusion_max)),
        ("None", (sr.none_min, sr.none_max)),
        ("Meta", (sr.meta_min, sr.meta_max)),
    ]:
        assert name in by_name, f"{name} missing from plot_points"
        themes = by_name[name]["themes"]
        assert set(themes.keys()) == set(crafter().adventure_crafter.themes), f"{name} missing a theme"
        for t, range_ in themes.items():
            assert (
                range_["min"],
                range_["max"],
            ) == expected, f"{name}.{t} has range ({range_['min']}, {range_['max']}) != yaml {expected}"
