from __future__ import annotations

import random
import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
GAIN = re.compile(r"take \+(\d) momentum", re.I)
LOSS = re.compile(r"(?:suffer|lose) -(\d) momentum", re.I)
KNOWN_DIVERGENCES = {
    ("classic", "relationship/draw_the_circle", "weak_hit"),
}
MYTHIC_2E_EVENT_FOCUS = [
    (1, 5, "remote_event"),
    (6, 10, "ambiguous_event"),
    (11, 20, "new_npc"),
    (21, 40, "npc_action"),
    (41, 45, "npc_negative"),
    (46, 50, "npc_positive"),
    (51, 55, "move_toward_thread"),
    (56, 65, "move_away_from_thread"),
    (66, 70, "close_thread"),
    (71, 80, "pc_negative"),
    (81, 85, "pc_positive"),
    (86, 100, "current_context"),
]


def _yaml_momentum(effects: list[str]) -> int | None:
    total = None
    for effect in effects:
        match = re.fullmatch(r"momentum ([+-]\d+)", effect.strip())
        if match:
            total = (total or 0) + int(match.group(1))
    return total


def test_unconditional_momentum_matches_the_rulebooks(load_engine: None) -> None:
    from straightjacket.engine.datasworn.moves import get_moves

    table = yaml.safe_load((REPO / "engine" / "move_outcomes.yaml").read_text(encoding="utf-8"))
    found = set()
    for setting in ("starforged", "classic"):
        overrides = table["move_outcome_overrides"][setting] if setting in table["move_outcome_overrides"] else {}
        outcomes = {**table["move_outcomes"], **overrides}
        for key, move in get_moves(setting).items():
            if key not in outcomes:
                continue
            for result, outcome in move.outcomes.items():
                if result not in ("strong_hit", "weak_hit", "miss"):
                    continue
                text = outcome.text
                gains = [int(x) for x in GAIN.findall(text)]
                losses = LOSS.findall(text)
                engine = _yaml_momentum(outcomes[key][result]) if result in outcomes[key] else None
                lowered = text.lower()
                single = (
                    len(gains) == 1 and "choose" not in lowered and " or " not in lowered and "whenever" not in lowered
                )
                if (single and engine != gains[0]) or (not gains and not losses and engine not in (None, 0)):
                    found.add((setting, key, result))
    assert found == KNOWN_DIVERGENCES


@pytest.mark.parametrize(
    ("dice", "odds", "chaos", "expected"),
    [
        ((5, 5), "fifty_fifty", 5, "no"),
        ((6, 5), "fifty_fifty", 5, "yes"),
        ((9, 9), "fifty_fifty", 5, "exceptional_yes"),
        ((1, 2), "fifty_fifty", 5, "exceptional_no"),
        ((5, 5), "likely", 6, "yes"),
        ((5, 4), "unlikely", 4, "no"),
    ],
)
def test_fate_check_follows_mythic_2e(
    load_engine: None, dice: tuple[int, int], odds: str, chaos: int, expected: str
) -> None:
    from straightjacket.engine.mechanics.fate import resolve_fate_check_with_dice

    assert resolve_fate_check_with_dice(odds, chaos, "q", dice).answer == expected


def test_fate_check_random_event_needs_doubles_within_chaos(load_engine: None) -> None:
    from straightjacket.engine.mechanics.fate import resolve_fate_check_with_dice

    assert resolve_fate_check_with_dice("fifty_fifty", 5, "q", (4, 4)).random_event_triggered
    assert not resolve_fate_check_with_dice("fifty_fifty", 5, "q", (6, 6)).random_event_triggered
    assert not resolve_fate_check_with_dice("fifty_fifty", 5, "q", (4, 3)).random_event_triggered


def test_fate_chart_has_the_mythic_2e_shape(load_engine: None) -> None:
    from straightjacket.engine.mechanics.fate import _load_mythic

    chart = _load_mythic()["fate_chart"]
    rows = [[cell["yes"] for cell in chart[odds]] for odds in chart]
    assert chart["fifty_fifty"][4]["yes"] == 50
    assert all(row == sorted(row) for row in rows)
    assert all([row[cf] for row in rows] == sorted((row[cf] for row in rows), reverse=True) for cf in range(9))


def test_event_focus_table_is_mythic_2e(load_engine: None) -> None:
    from straightjacket.engine.mechanics.fate import _load_mythic

    table = [(row["min"], row["max"], row["focus"]) for row in _load_mythic()["event_focus"]]
    assert table == MYTHIC_2E_EVENT_FOCUS


@pytest.mark.parametrize(("roll", "expected"), [(10, "expected"), (6, "expected"), (3, "altered"), (4, "interrupt")])
def test_scene_test_follows_mythic_2e(load_engine: None, roll: int, expected: str) -> None:
    from straightjacket.engine.mechanics.scene import check_scene
    from tests._helpers import make_game_state

    game = make_game_state()
    game.world.chaos_factor = 5
    game.narrative.keyed_scenes = []
    assert check_scene(game, roll=roll).scene_type.startswith(expected)


@pytest.mark.parametrize(("setting", "expected"), [("classic", 1), ("starforged", 2)])
def test_secure_an_advantage_weak_hit_follows_each_rulebook(load_engine: None, setting: str, expected: int) -> None:
    from straightjacket.engine.mechanics.move_outcome import resolve_move_outcome
    from tests._helpers import make_game_state

    game = make_game_state(setting_id=setting)
    game.resources.momentum = 0
    resolve_move_outcome(game, "adventure/secure_an_advantage", "WEAK_HIT")
    assert game.resources.momentum == expected


@pytest.mark.parametrize(
    ("setting", "health", "result", "expected"),
    [
        ("starforged", 3, "STRONG_HIT", (4, 2)),
        ("starforged", 5, "STRONG_HIT", (5, 3)),
        ("starforged", 3, "WEAK_HIT", (4, 1)),
        ("starforged", 5, "WEAK_HIT", (5, 2)),
        ("starforged", 3, "MISS", (2, 2)),
        ("classic", 3, "STRONG_HIT", (4, 1)),
        ("classic", 0, "STRONG_HIT", (0, 3)),
        ("classic", 3, "WEAK_HIT", (3, 2)),
        ("classic", 3, "MISS", (3, 1)),
    ],
)
def test_endure_harm_follows_each_rulebook(
    load_engine: None, setting: str, health: int, result: str, expected: tuple[int, int]
) -> None:
    from straightjacket.engine.mechanics.move_outcome import resolve_move_outcome
    from tests._helpers import make_game_state

    game = make_game_state(setting_id=setting)
    game.resources.health = health
    game.resources.momentum = 2
    game.impacts = []
    resolve_move_outcome(game, "suffer/endure_harm", result)
    assert (game.resources.health, game.resources.momentum) == expected


@pytest.mark.parametrize(("vow_rank", "expected_ticks"), [("formidable", 2), ("dangerous", 1), ("troublesome", 0)])
def test_fulfill_your_vow_weak_hit_rewards_one_rank_lower(
    load_engine: None, vow_rank: str, expected_ticks: int
) -> None:
    from straightjacket.engine.game.finalization import apply_progress_and_legacy
    from straightjacket.engine.mechanics.legacy import get_legacy_track
    from straightjacket.engine.mechanics.move_outcome import resolve_move_outcome
    from tests._helpers import make_brain_result, make_game_state

    game = make_game_state(setting_id="starforged")
    outcome = resolve_move_outcome(game, "quest/fulfill_your_vow", "WEAK_HIT")
    apply_progress_and_legacy(game, outcome, make_brain_result(), source_track_rank=vow_rank)
    assert get_legacy_track(game, "quests").ticks == expected_ticks


def test_develop_your_relationship_marks_two_bonds_ticks(load_engine: None) -> None:
    from straightjacket.engine.game.finalization import apply_progress_and_legacy
    from straightjacket.engine.mechanics.legacy import get_legacy_track
    from straightjacket.engine.mechanics.move_outcome import resolve_move_outcome
    from tests._helpers import make_brain_result, make_game_state

    game = make_game_state(setting_id="starforged")
    outcome = resolve_move_outcome(game, "connection/develop_your_relationship", "STRONG_HIT")
    apply_progress_and_legacy(game, outcome, make_brain_result(), source_track_rank="epic")
    assert get_legacy_track(game, "bonds").ticks == 2


def test_make_a_connection_gives_no_momentum(load_engine: None) -> None:
    from straightjacket.engine.mechanics.move_outcome import resolve_move_outcome
    from tests._helpers import make_game_state

    game = make_game_state(setting_id="starforged")
    game.resources.momentum = 2
    resolve_move_outcome(game, "connection/make_a_connection", "WEAK_HIT")
    assert game.resources.momentum == 2


def test_a_full_legacy_track_clears_and_then_earns_one_experience_per_box(load_engine: None) -> None:
    from straightjacket.engine.mechanics.legacy import get_legacy_track, mark_legacy_ticks
    from tests._helpers import make_game_state

    game = make_game_state(setting_id="starforged")
    game.campaign.xp = 0
    track = get_legacy_track(game, "quests")
    track.ticks = track.max_ticks - 2
    assert mark_legacy_ticks(game, "quests", 4) == 2
    assert (track.ticks, track.completions) == (2, 1)
    assert mark_legacy_ticks(game, "quests", 2) == 1
    assert game.campaign.xp == 3


@pytest.mark.parametrize(("requested", "expected"), [(3, 4), (4, 4), (5, 6), (6, 6), (7, 8), (10, 8)])
def test_clocks_use_blades_sizes(load_engine: None, requested: int, expected: int) -> None:
    from straightjacket.engine.game.setup_common import conform_clock_segments

    assert conform_clock_segments(requested) == expected


def test_mythic_lists_hold_an_entry_at_most_three_times(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng

    assert eng().random_events.list_weight_max == 3


def test_meaning_tables_have_the_mythic_2e_shape(load_engine: None) -> None:
    from straightjacket.engine.mechanics.fate import _load_mythic

    tables = _load_mythic()["meaning_tables"]
    pairs = [
        tables["actions"]["verbs"],
        tables["actions"]["subjects"],
        tables["descriptions"]["adverbs"],
        tables["descriptions"]["adjectives"],
    ]
    assert all(len(words) == 100 for words in pairs)
    assert len(tables["elements"]) == 45
    assert all(len(words) == 100 for words in tables["elements"].values())


@pytest.mark.parametrize(("roll", "expected"), [(1, 1), (4, 1), (5, 2), (7, 2), (8, 3), (9, 3)])
def test_adventure_crafter_theme_priority(load_engine: None, roll: int, expected: int) -> None:
    from straightjacket.engine.mechanics.adventure_crafter import ThemeAlternation, lookup_theme_priority

    assert lookup_theme_priority(roll, ThemeAlternation()) == expected


def test_adventure_crafter_theme_priority_ten_alternates_between_four_and_five(load_engine: None) -> None:
    from straightjacket.engine.mechanics.adventure_crafter import ThemeAlternation, lookup_theme_priority

    alternation = ThemeAlternation()
    assert {lookup_theme_priority(10, alternation) for _ in range(2)} == {4, 5}


def _covers_one_to_hundred(ranges: list[tuple[int, int]]) -> bool:
    cells = sorted(v for low, high in ranges for v in range(low, high + 1))
    return cells == list(range(1, 101))


def test_adventure_crafter_tables_are_complete(load_engine: None) -> None:
    from straightjacket.engine.mechanics.adventure_crafter import _load_ac_data

    data = _load_ac_data()
    themes = {theme for point in data["plot_points"] for theme in point["themes"]}
    assert themes == {"action", "tension", "mystery", "social", "personal"}
    for theme in themes:
        ranges = [
            (p["themes"][theme]["min"], p["themes"][theme]["max"]) for p in data["plot_points"] if theme in p["themes"]
        ]
        assert _covers_one_to_hundred(ranges), theme
    assert _covers_one_to_hundred([(m["min"], m["max"]) for m in data["meta_plot_points"]])
    for name in ("characters_list_template", "plotlines_list_template"):
        rows = data[name]
        assert len(rows) == 25
        assert all(r["max"] - r["min"] == 3 for r in rows)
        assert _covers_one_to_hundred([(r["min"], r["max"]) for r in rows])


def test_adventure_crafter_conclusion_and_none_ranges(load_engine: None) -> None:
    from straightjacket.engine.mechanics.adventure_crafter import _load_ac_data

    points = {p["name"]: p["themes"] for p in _load_ac_data()["plot_points"]}
    assert all((r["min"], r["max"]) == (1, 8) for r in points["Conclusion"].values())
    assert all((r["min"], r["max"]) == (9, 24) for r in points["None"].values())


class _ScriptedRng(random.Random):
    def __init__(self, *values: int) -> None:
        super().__init__(0)
        self.values = list(values)

    def randint(self, low: int, high: int) -> int:
        return self.values.pop(0)


THEMES = ["action", "tension", "mystery", "social", "personal"]


def test_turning_point_always_has_five_slots_and_at_most_three_none(load_engine: None) -> None:
    from straightjacket.engine.mechanics.adventure_crafter import roll_turning_point
    from tests._helpers import make_game_state

    for seed in range(200):
        narrative = make_game_state().narrative
        points = roll_turning_point(random.Random(seed), THEMES, narrative).plot_points
        assert len(points) == 5
        assert sum(1 for p in points if p.special_range == "none") <= 3


def test_a_fourth_none_is_rerolled(load_engine: None) -> None:
    from straightjacket.engine.mechanics.adventure_crafter import roll_turning_point
    from tests._helpers import make_game_state

    rolls = [5] + [1, 10] * 4 + [1, 50, 1, 60]
    points = roll_turning_point(_ScriptedRng(*rolls), THEMES, make_game_state().narrative).plot_points
    assert [p.special_range for p in points].count("none") == 3
    assert [p.roll for p in points[-2:]] == [50, 60]


def test_conclusion_on_a_new_plotline_counts_as_none(load_engine: None) -> None:
    from straightjacket.engine.mechanics.adventure_crafter import roll_turning_point
    from tests._helpers import make_game_state

    rolls = [5, 1, 1] + [1, 50] * 4
    narrative = make_game_state().narrative
    turning_point = roll_turning_point(_ScriptedRng(*rolls), THEMES, narrative)
    assert turning_point.plotline_was_new
    assert turning_point.plot_points[0].special_range == "none"
    assert all(p.status != "conclusion" for p in narrative.plotlines_list)
