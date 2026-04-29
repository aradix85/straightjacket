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


def test_ac_meta_handlers_config_loads():
    cfg = eng().adventure_crafter.meta_handlers
    assert isinstance(cfg.weight_delta_step_up, int)
    assert isinstance(cfg.weight_delta_step_down, int)
    assert isinstance(cfg.weight_delta_upgrade, int)
    assert isinstance(cfg.weight_delta_downgrade, int)
    assert isinstance(cfg.weight_floor, int)
    assert cfg.weight_floor >= 1
    assert cfg.weight_delta_upgrade > cfg.weight_delta_step_up
    assert cfg.weight_delta_downgrade < cfg.weight_delta_step_down


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


def test_dispatch_meta_routes_to_handler_without_raising():
    from straightjacket.engine.models_story import NarrativeState

    narrative = NarrativeState()
    for roll in [1, 19, 28, 37, 56, 74, 83]:
        dispatch_meta(roll, narrative, None)


def test_dispatch_meta_unknown_name_raises_keyerror(monkeypatch):
    from straightjacket.engine.models_story import NarrativeState

    def fake_lookup(_roll: int) -> str:
        return "Plot Twist"

    monkeypatch.setattr(
        "straightjacket.engine.mechanics.adventure_crafter.lookup_meta_plot_point",
        fake_lookup,
    )
    narrative = NarrativeState()
    with pytest.raises(KeyError, match="drifted"):
        dispatch_meta(50, narrative, None)


from straightjacket.engine.mechanics.adventure_crafter import (
    PlotPointHit,
    ThemeAlternation,
    TurningPoint,
    _create_character,
    _create_plotline,
    lookup_characters_template,
    lookup_plotlines_template,
    lookup_theme_priority,
    roll_turning_point,
)
from straightjacket.engine.models_story import NarrativeState


def test_lookup_theme_priority_constant_for_first_three_buckets():
    alt = ThemeAlternation()
    assert lookup_theme_priority(1, alt) == 1
    assert lookup_theme_priority(4, alt) == 1
    assert lookup_theme_priority(5, alt) == 2
    assert lookup_theme_priority(7, alt) == 2
    assert lookup_theme_priority(8, alt) == 3
    assert lookup_theme_priority(9, alt) == 3


def test_lookup_theme_priority_alternates_on_ten():
    alt = ThemeAlternation()
    first = lookup_theme_priority(10, alt)
    second = lookup_theme_priority(10, alt)
    third = lookup_theme_priority(10, alt)
    assert {first, second, third} == {4, 5}
    assert first == 4
    assert second == 5
    assert third == 4


@pytest.mark.parametrize("bad_roll", [0, -1, 11, 100])
def test_lookup_theme_priority_out_of_range_raises(bad_roll: int):
    with pytest.raises(ValueError, match="outside 1..10"):
        lookup_theme_priority(bad_roll, ThemeAlternation())


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
    narrative = NarrativeState()
    rng = random.Random(7)
    themes = ["action", "tension", "mystery", "social", "personal"]
    for _ in range(20):
        tp = roll_turning_point(rng, themes, narrative)
        assert isinstance(tp, TurningPoint)
        assert 2 <= len(tp.plot_points) <= 5
        for hit in tp.plot_points:
            assert isinstance(hit, PlotPointHit)
            assert hit.theme in themes
            assert 1 <= hit.priority <= 5
            assert 1 <= hit.roll <= 100


def test_roll_turning_point_themes_length_must_match_theme_slots():
    narrative = NarrativeState()
    rng = random.Random(0)
    with pytest.raises(ValueError, match="theme_slots"):
        roll_turning_point(rng, ["action", "tension"], narrative)


def test_roll_turning_point_creates_plotline_on_empty_list():
    narrative = NarrativeState()
    rng = random.Random(1)
    themes = ["action", "tension", "mystery", "social", "personal"]
    assert narrative.plotlines_list == []
    tp = roll_turning_point(rng, themes, narrative)
    assert tp.plotline_was_new is True
    assert len(narrative.plotlines_list) == 1
    assert narrative.plotlines_list[0].id == tp.plotline_id


def test_roll_turning_point_reuses_advancing_plotline():
    narrative = NarrativeState()
    _create_plotline(narrative, "First")
    rng = random.Random(0)
    themes = ["action", "tension", "mystery", "social", "personal"]
    tp = roll_turning_point(rng, themes, narrative)
    assert len(narrative.plotlines_list) in (1, 2)
    if not tp.plotline_was_new:
        assert tp.plotline_id == "ac_plot_1"


def test_conclusion_plot_point_flips_plotline_to_conclusion(monkeypatch):
    narrative = NarrativeState()
    rng = random.Random(0)
    themes = ["action", "tension", "mystery", "social", "personal"]

    rolls = iter([10, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1])

    def fake_randint(a: int, b: int) -> int:
        return next(rolls)

    monkeypatch.setattr(rng, "randint", fake_randint)
    tp = roll_turning_point(rng, themes, narrative)
    assert tp.flips_to_conclusion is True
    plotline = narrative.plotlines_list[0]
    assert plotline.status == "conclusion"


def test_meta_character_exits_marks_active_character_exited():
    from straightjacket.engine.mechanics.adventure_crafter import _meta_character_exits

    narrative = NarrativeState()
    char = _create_character(narrative, "Alice")
    _meta_character_exits(narrative, None)
    assert char.ac_status == "exited"


def test_meta_character_returns_marks_exited_character_returned():
    from straightjacket.engine.mechanics.adventure_crafter import _meta_character_returns

    narrative = NarrativeState()
    char = _create_character(narrative, "Alice")
    char.ac_status = "exited"
    _meta_character_returns(narrative, None)
    assert char.ac_status == "returned"


def test_meta_character_returns_creates_new_when_no_exited():
    from straightjacket.engine.mechanics.adventure_crafter import _meta_character_returns

    narrative = NarrativeState()
    _meta_character_returns(narrative, None)
    assert len(narrative.characters_list) == 1
    assert narrative.characters_list[0].ac_status == "returned"


def test_meta_character_steps_up_increases_weight():
    from straightjacket.engine.mechanics.adventure_crafter import _meta_character_steps_up

    narrative = NarrativeState()
    char = _create_character(narrative, "Alice")
    initial = char.weight
    _meta_character_steps_up(narrative, None)
    expected = initial + eng().adventure_crafter.meta_handlers.weight_delta_step_up
    assert char.weight == expected


def test_meta_character_steps_down_decreases_weight_to_floor():
    from straightjacket.engine.mechanics.adventure_crafter import _meta_character_steps_down

    cfg = eng().adventure_crafter.meta_handlers
    narrative = NarrativeState()
    char = _create_character(narrative, "Alice")
    char.weight = 5
    _meta_character_steps_down(narrative, None)
    assert char.weight == 5 + cfg.weight_delta_step_down
    char.weight = cfg.weight_floor
    _meta_character_steps_down(narrative, None)
    assert char.weight == cfg.weight_floor


def test_meta_character_downgrade_marks_status_and_decreases_weight():
    from straightjacket.engine.mechanics.adventure_crafter import _meta_character_downgrade

    cfg = eng().adventure_crafter.meta_handlers
    narrative = NarrativeState()
    char = _create_character(narrative, "Alice")
    char.weight = 5
    _meta_character_downgrade(narrative, None)
    assert char.ac_status == "downgraded"
    assert char.weight == max(cfg.weight_floor, 5 + cfg.weight_delta_downgrade)


def test_meta_character_upgrade_marks_status_and_increases_weight():
    from straightjacket.engine.mechanics.adventure_crafter import _meta_character_upgrade

    cfg = eng().adventure_crafter.meta_handlers
    narrative = NarrativeState()
    char = _create_character(narrative, "Alice")
    initial = char.weight
    _meta_character_upgrade(narrative, None)
    assert char.ac_status == "upgraded"
    assert char.weight == initial + cfg.weight_delta_upgrade


def test_meta_plotline_combo_merges_two_advancing_plotlines():
    from straightjacket.engine.mechanics.adventure_crafter import _meta_plotline_combo

    narrative = NarrativeState()
    a = _create_plotline(narrative, "First")
    b = _create_plotline(narrative, "Second")
    _meta_plotline_combo(narrative, None)
    statuses = sorted([a.status, b.status])
    assert "merged" in statuses
    assert statuses.count("advancement") == 1


def test_meta_plotline_combo_skips_when_fewer_than_two_advancing():
    from straightjacket.engine.mechanics.adventure_crafter import _meta_plotline_combo

    narrative = NarrativeState()
    only = _create_plotline(narrative, "Only one")
    _meta_plotline_combo(narrative, None)
    assert only.status == "advancement"


def test_meta_plotline_combo_excludes_active_plotline_id():
    from straightjacket.engine.mechanics.adventure_crafter import _meta_plotline_combo

    narrative = NarrativeState()
    active = _create_plotline(narrative, "Active")
    _create_plotline(narrative, "Other")
    _meta_plotline_combo(narrative, active.id)
    assert active.status == "advancement"


def test_chapter_round_trip_preserves_characters_and_plotlines():
    from straightjacket.engine.models import ChapterSummary, CharacterListEntry, PlotlineEntry

    chars = [
        CharacterListEntry(
            id="ac_char_1",
            name="Alice",
            entry_type="ac",
            weight=2,
            active=True,
            ac_status="present",
            ac_turning_point_count=1,
        ),
    ]
    plots = [PlotlineEntry(id="ac_plot_1", name="Quest", status="advancement", turning_point_count=2)]
    summary = ChapterSummary(
        chapter=1,
        title="Ch 1",
        summary="",
        unresolved_threads=[],
        character_growth="",
        npc_evolutions=[],
        thematic_question="",
        post_story_location="",
        scenes=0,
        progress_tracks=[],
        threats=[],
        impacts=[],
        assets=[],
        threads=[],
        characters_list=chars,
        plotlines_list=plots,
    )
    restored = ChapterSummary.from_dict(summary.to_dict())
    assert len(restored.characters_list) == 1
    assert restored.characters_list[0].ac_status == "present"
    assert restored.characters_list[0].ac_turning_point_count == 1
    assert len(restored.plotlines_list) == 1
    assert restored.plotlines_list[0].status == "advancement"
    assert restored.plotlines_list[0].turning_point_count == 2


def test_narrative_state_snapshot_restore_round_trips_plotlines_list():
    narrative = NarrativeState()
    _create_plotline(narrative, "Original")
    snap = narrative.snapshot()
    _create_plotline(narrative, "Mid-turn add")
    assert len(narrative.plotlines_list) == 2
    narrative.restore(snap)
    assert len(narrative.plotlines_list) == 1
    assert narrative.plotlines_list[0].name == "Original"

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
