from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.models import labels_of
from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.progress import ticks_per_mark
from tests._helpers import fix_dice

REPO = Path(__file__).resolve().parent.parent
GAIN = re.compile(r"take \+(\d) momentum", re.I)
LOSS = re.compile(r"(?:suffer|lose) -(\d) momentum", re.I)
KNOWN_DIVERGENCES: set[tuple[str, str, str]] = set()
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
    from straightjacket.engine.ruleset.moves import get_moves

    table = yaml.safe_load((REPO / "ruleset" / "move_outcomes.yaml").read_text(encoding="utf-8"))
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
    load_engine: None, dice: tuple[int, int], odds: str, chaos: int, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.gamemaster.fate import resolve_fate_check

    fix_dice(monkeypatch, *dice)
    assert resolve_fate_check(odds, chaos).answer == expected


def test_fate_check_random_event_needs_doubles_within_chaos(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.gamemaster.fate import resolve_fate_check

    fix_dice(monkeypatch, *(4, 4))
    assert resolve_fate_check("fifty_fifty", 5).random_event_triggered
    fix_dice(monkeypatch, *(6, 6))
    assert not resolve_fate_check("fifty_fifty", 5).random_event_triggered
    fix_dice(monkeypatch, *(4, 3))
    assert not resolve_fate_check("fifty_fifty", 5).random_event_triggered


def test_fate_chart_has_the_mythic_2e_shape(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.mythic_data import load_mythic

    chart = load_mythic()["fate_chart"]
    rows = [[cell["yes"] for cell in chart[odds]] for odds in chart]
    assert chart["fifty_fifty"][4]["yes"] == 50
    assert all(row == sorted(row) for row in rows)
    assert all([row[cf] for row in rows] == sorted((row[cf] for row in rows), reverse=True) for cf in range(9))


def test_event_focus_table_is_mythic_2e(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.mythic_data import load_mythic

    table = [(row["min"], row["max"], row["focus"]) for row in load_mythic()["event_focus"]]
    assert table == MYTHIC_2E_EVENT_FOCUS


@pytest.mark.parametrize(("roll", "expected"), [(10, "expected"), (6, "expected"), (3, "altered"), (4, "interrupt")])
def test_scene_test_follows_mythic_2e(
    load_engine: None, roll: int, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.gamemaster.scene import check_scene
    from tests._helpers import make_game_state

    game = make_game_state()
    game.world.chaos_factor = 5
    game.narrative.keyed_scenes = []
    fix_dice(monkeypatch, roll)
    assert check_scene(game).scene_type.startswith(expected)


@pytest.mark.parametrize(("setting", "expected"), [("classic", 1), ("starforged", 2)])
def test_secure_an_advantage_weak_hit_follows_each_rulebook(load_engine: None, setting: str, expected: int) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
    from tests._helpers import make_game_state

    game = make_game_state(setting_id=setting)
    game.resources.meters["momentum"] = 0
    resolve_move_outcome(game, "adventure/secure_an_advantage", "WEAK_HIT", target_npc_id=None, match=False)
    assert game.resources.meters["momentum"] == expected


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
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
    from tests._helpers import make_game_state

    game = make_game_state(setting_id=setting)
    game.resources.meters["health"] = health
    game.resources.meters["momentum"] = 2
    game.impacts = []
    resolve_move_outcome(game, "suffer/endure_harm", result, target_npc_id=None, match=False)
    assert (game.resources.meters["health"], game.resources.meters["momentum"]) == expected


@pytest.mark.parametrize(("vow_rank", "expected_ticks"), [("formidable", 2), ("dangerous", 1), ("troublesome", 0)])
def test_fulfill_your_vow_weak_hit_rewards_one_rank_lower(
    load_engine: None, vow_rank: str, expected_ticks: int
) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
    from straightjacket.engine.ruleset.tracks import apply_progress_and_legacy
    from tests._helpers import make_brain_result, make_game_state, make_progress_track

    game = make_game_state(setting_id="starforged")
    outcome = resolve_move_outcome(game, "quest/fulfill_your_vow", "WEAK_HIT", target_npc_id=None, match=False)
    apply_progress_and_legacy(game, outcome, make_brain_result(), make_progress_track(rank=vow_rank))
    assert game.campaign.legacy["quests"].ticks == expected_ticks


@pytest.mark.parametrize(
    ("result", "vow_rank", "expected_xp"),
    [
        ("STRONG_HIT", "troublesome", 1),
        ("STRONG_HIT", "epic", 5),
        ("WEAK_HIT", "dangerous", 1),
        ("WEAK_HIT", "troublesome", 0),
    ],
)
def test_classic_fulfill_your_vow_marks_experience_by_rank(
    load_engine: None, result: str, vow_rank: str, expected_xp: int
) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
    from straightjacket.engine.ruleset.tracks import apply_progress_and_legacy
    from tests._helpers import make_brain_result, make_game_state, make_progress_track

    game = make_game_state(setting_id="classic")
    outcome = resolve_move_outcome(game, "quest/fulfill_your_vow", result, target_npc_id=None, match=False)
    apply_progress_and_legacy(game, outcome, make_brain_result(), make_progress_track(rank=vow_rank))
    assert game.campaign.xp == expected_xp
    assert all(track.ticks == 0 for track in game.campaign.legacy.values())


def test_develop_your_relationship_marks_two_bonds_ticks(load_engine: None) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
    from straightjacket.engine.ruleset.tracks import apply_progress_and_legacy
    from tests._helpers import make_brain_result, make_game_state

    game = make_game_state(setting_id="starforged")
    outcome = resolve_move_outcome(
        game, "connection/develop_your_relationship", "STRONG_HIT", target_npc_id=None, match=False
    )
    apply_progress_and_legacy(game, outcome, make_brain_result(), None)
    assert game.campaign.legacy["bonds"].ticks == 2


@pytest.mark.parametrize("setting_id", ["classic", "starforged"])
def test_a_strike_marks_progress_on_the_open_fight(load_engine: None, setting_id: str) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
    from straightjacket.engine.ruleset.tracks import apply_progress_and_legacy
    from tests._helpers import make_brain_result, make_game_state, make_progress_track

    game = make_game_state(setting_id=setting_id)
    game.progress_tracks.append(make_progress_track(id="combat_raider", name="Raider", track_type="combat"))
    outcome = resolve_move_outcome(game, "combat/strike", "STRONG_HIT", target_npc_id=None, match=False)
    apply_progress_and_legacy(game, outcome, make_brain_result(move="combat/strike"), None)
    assert game.progress_tracks[-1].ticks > 0


def test_every_move_that_marks_progress_names_its_track_category(load_engine: None) -> None:
    import yaml

    outcomes = yaml.safe_load((REPO / "ruleset" / "move_outcomes.yaml").read_text(encoding="utf-8"))["move_outcomes"]
    marking = sorted(move for move, results in outcomes.items() if "mark_progress" in str(results))
    categories = rules().get_raw("progress_mark_categories")
    assert sorted(categories) == marking
    assert set(categories.values()) <= set(rules().get_raw("track_types_by_category"))


def test_make_a_connection_gives_no_momentum(load_engine: None) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
    from tests._helpers import make_game_state

    game = make_game_state(setting_id="starforged")
    game.resources.meters["momentum"] = 2
    resolve_move_outcome(game, "connection/make_a_connection", "WEAK_HIT", target_npc_id=None, match=False)
    assert game.resources.meters["momentum"] == 2


def test_a_full_legacy_track_clears_and_then_earns_one_experience_per_box(load_engine: None) -> None:
    from straightjacket.engine.ruleset.legacy import mark_legacy_ticks
    from tests._helpers import make_game_state

    game = make_game_state(setting_id="starforged")
    game.campaign.xp = 0
    track = game.campaign.legacy["quests"]
    track.ticks = track.max_ticks - 2
    mark_legacy_ticks(game, "quests", 4)
    assert game.campaign.xp == 2
    assert (track.ticks, track.completions) == (2, 1)
    mark_legacy_ticks(game, "quests", 2)
    assert game.campaign.xp == 3


def test_clocks_use_blades_sizes(load_engine: None) -> None:

    assert gm().clocks.default_segments in (4, 6, 8)
    assert gm().opening.clock_segments in (4, 6, 8)


def test_mythic_lists_hold_an_entry_at_most_three_times(load_engine: None) -> None:

    assert gm().random_events.list_weight_max == 3


def test_meaning_tables_have_the_mythic_2e_shape(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.mythic_data import load_mythic

    tables = load_mythic()["meaning_tables"]
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
    from straightjacket.engine.crafters.adventure_crafter import ThemeAlternation, lookup_theme_priority

    assert lookup_theme_priority(roll, ThemeAlternation()) == expected


def test_adventure_crafter_theme_priority_ten_alternates_between_four_and_five(load_engine: None) -> None:
    from straightjacket.engine.crafters.adventure_crafter import ThemeAlternation, lookup_theme_priority

    alternation = ThemeAlternation()
    assert {lookup_theme_priority(10, alternation) for _ in range(2)} == {4, 5}


def _covers_one_to_hundred(ranges: list[tuple[int, int]]) -> bool:
    cells = sorted(v for low, high in ranges for v in range(low, high + 1))
    return cells == list(range(1, 101))


def test_adventure_crafter_tables_are_complete(load_engine: None) -> None:
    from straightjacket.engine.crafters.adventure_crafter import _load_ac_data

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
    from straightjacket.engine.crafters.adventure_crafter import _load_ac_data

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
    from straightjacket.engine.crafters.adventure_crafter import roll_turning_point
    from tests._helpers import make_game_state

    for seed in range(200):
        narrative = make_game_state().narrative
        points = roll_turning_point(random.Random(seed), THEMES, narrative).plot_points
        assert len(points) == 5
        assert sum(1 for p in points if p.special_range == "none") <= 3


def test_a_fourth_none_is_rerolled(load_engine: None) -> None:
    from straightjacket.engine.crafters.adventure_crafter import lookup_plot_point, roll_turning_point
    from tests._helpers import make_game_state

    rolls = [5] + [1, 10] * 4 + [1, 50, 1, 60]
    points = roll_turning_point(_ScriptedRng(*rolls), THEMES, make_game_state().narrative).plot_points
    assert [p.special_range for p in points].count("none") == 3
    assert [p.name for p in points[-2:]] == [lookup_plot_point(THEMES[0], roll).name for roll in (50, 60)]


def test_conclusion_on_a_new_plotline_counts_as_none(load_engine: None) -> None:
    from straightjacket.engine.crafters.adventure_crafter import roll_turning_point
    from tests._helpers import make_game_state

    rolls = [5, 1, 1] + [1, 50] * 4
    narrative = make_game_state().narrative
    turning_point = roll_turning_point(_ScriptedRng(*rolls), THEMES, narrative)
    assert len(narrative.plotlines_list) == 1
    assert turning_point.plot_points[0].special_range == "none"
    assert all(p.status != "conclusion" for p in narrative.plotlines_list)


_ROLL_TWICE = {"oracle": None, "auto": True, "number_of_rolls": 2, "dice": None}


class _FakePriceMove:
    def __init__(self, *rows: Any) -> None:
        from straightjacket.engine.setting.loader import OracleTable

        self.order = list(rows)
        self.table = OracleTable(id="moves/pay_the_price", title="Pay the Price", rows=list(rows))
        self.table.roll = lambda: self.order.pop(0)
        self.tables = {"pay_the_price": self.table}


def _price_row(text: str, duplicates: str | None = None) -> Any:
    from straightjacket.engine.setting.loader import OracleRow

    rolls = [{**_ROLL_TWICE, "duplicates": duplicates}] if duplicates else None
    return OracleRow(min=1, max=1, text=text, oracle_rolls=rolls)


@pytest.mark.parametrize("setting", ["starforged", "classic"])
def test_pay_the_price_rolls_the_official_table(load_engine: None, setting: str) -> None:
    import json

    from straightjacket.engine.ruleset.move_effects import pay_the_price
    from straightjacket.engine.ruleset.outcome_result import OutcomeResult
    from tests._helpers import make_game_state

    data = json.loads((REPO / "data" / f"{setting}.json").read_text(encoding="utf-8"))
    rows = [
        re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", r["text"]).strip()
        for r in data["moves"]["fate"]["contents"]["pay_the_price"]["oracles"]["pay_the_price"]["rows"]
    ]
    game = make_game_state(setting_id=setting)
    for _ in range(30):
        result = OutcomeResult()
        pay_the_price(game, result)
        told = labels_of(result.consequences)[0]
        assert told.startswith("Pay the Price: ")
        assert "Roll twice" not in told
        assert all(any(part.startswith(row) for row in rows) for part in told.split(": ", 1)[1].split("; "))


def test_pay_the_price_harm_costs_health(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.ruleset import move_effects
    from straightjacket.engine.ruleset.outcome_result import OutcomeResult
    from tests._helpers import make_game_state

    monkeypatch.setattr(move_effects, "_pay_the_price_move", lambda game: _FakePriceMove(_price_row("You are harmed")))
    game = make_game_state(setting_id="starforged")
    game.resources.meters["health"] = 4
    move_effects.pay_the_price(game, OutcomeResult())
    assert game.resources.meters["health"] == 3


def test_pay_the_price_roll_twice_tells_both_results_and_not_the_instruction(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.ruleset import move_effects
    from straightjacket.engine.ruleset.outcome_result import OutcomeResult
    from tests._helpers import make_game_state

    rows = (_price_row("Roll twice", "reroll"), _price_row("You are stressed"), _price_row("A new enemy is revealed"))
    monkeypatch.setattr(move_effects, "_pay_the_price_move", lambda game: _FakePriceMove(*rows))
    game = make_game_state(setting_id="starforged")
    game.resources.meters["spirit"] = 4
    result = OutcomeResult()
    move_effects.pay_the_price(game, result)
    assert labels_of(result.consequences)[0] == "Pay the Price: You are stressed; A new enemy is revealed"
    assert game.resources.meters["spirit"] == 3


def test_classic_pay_the_price_makes_a_twice_rolled_result_worse(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.ruleset import move_effects
    from straightjacket.engine.ruleset.outcome_result import OutcomeResult
    from tests._helpers import make_game_state

    enemy = _price_row("A new enemy is revealed")
    rows = (_price_row("Roll twice more on this table.", "make_it_worse"), enemy, enemy)
    monkeypatch.setattr(move_effects, "_pay_the_price_move", lambda game: _FakePriceMove(*rows))
    result = OutcomeResult()
    move_effects.pay_the_price(make_game_state(setting_id="classic"), result)
    assert labels_of(result.consequences) == ["Pay the Price: A new enemy is revealed, made worse"]


def test_classic_roll_again_tells_the_next_result_made_worse(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.ruleset import move_effects
    from straightjacket.engine.ruleset.outcome_result import OutcomeResult
    from tests._helpers import make_game_state

    again = _price_row("Roll again and apply that result but make it worse. If you roll this result yet again, ...")
    rows = (again, _price_row("You are harmed"))
    monkeypatch.setattr(move_effects, "_pay_the_price_move", lambda game: _FakePriceMove(*rows))
    game = make_game_state(setting_id="classic")
    game.resources.meters["health"] = 4
    result = OutcomeResult()
    move_effects.pay_the_price(game, result)
    assert labels_of(result.consequences)[0] == "Pay the Price: You are harmed, made worse"
    assert game.resources.meters["health"] == 3


@pytest.mark.parametrize(("setting", "pays"), [("classic", True), ("starforged", False)])
def test_enter_the_fray_miss_pays_the_price_only_in_classic(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, setting: str, pays: bool
) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
    from tests._helpers import make_game_state, record_price_tables

    rolled = record_price_tables(monkeypatch)
    resolve_move_outcome(
        make_game_state(setting_id=setting), "combat/enter_the_fray", "MISS", target_npc_id=None, match=False
    )
    assert bool(rolled) is pays


@pytest.mark.parametrize("setting", ["classic", "starforged"])
@pytest.mark.parametrize(
    ("result", "position"), [("STRONG_HIT", "in_control"), ("WEAK_HIT", "bad_spot"), ("MISS", "bad_spot")]
)
def test_every_enter_the_fray_result_sets_who_is_in_control(
    load_engine: None, setting: str, result: str, position: str
) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
    from tests._helpers import make_game_state

    outcome = resolve_move_outcome(
        make_game_state(setting_id=setting), "combat/enter_the_fray", result, target_npc_id=None, match=False
    )
    assert outcome.combat_position == position


KNOWN_MATCH_GAPS: set[tuple[str, str, str]] = set()


def test_every_match_clause_is_modelled_or_known(load_engine: None) -> None:
    from straightjacket.engine.ruleset.moves import get_moves

    table = yaml.safe_load((REPO / "ruleset" / "move_outcomes.yaml").read_text(encoding="utf-8"))
    unmodelled = set()
    for setting in ("starforged", "classic"):
        overrides = table["move_outcome_overrides"][setting] if setting in table["move_outcome_overrides"] else {}
        outcomes = {**table["move_outcomes"], **overrides}
        for key, move in get_moves(setting).items():
            for outcome in move.outcomes.values():
                for kind in re.findall(r"On a __(strong hit|miss) with a match__", outcome.text):
                    result = kind.replace(" ", "_")
                    if f"{result}_match" not in outcomes.get(key, {}):
                        unmodelled.add((setting, key, result))
    assert unmodelled == KNOWN_MATCH_GAPS


@pytest.mark.parametrize(
    ("move", "result", "match", "progress", "clock"),
    [
        ("scene_challenge/face_danger", "STRONG_HIT", False, 1, 0),
        ("scene_challenge/face_danger", "STRONG_HIT", True, 2, 0),
        ("scene_challenge/face_danger", "MISS", False, 0, 1),
        ("scene_challenge/face_danger", "MISS", True, 0, 2),
        ("scene_challenge/secure_an_advantage", "STRONG_HIT", True, 1, 0),
        ("scene_challenge/secure_an_advantage", "MISS", True, 0, 2),
    ],
)
def test_scene_challenge_match_outcomes(
    load_engine: None, move: str, result: str, match: bool, progress: int, clock: int
) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
    from tests._helpers import make_game_state

    outcome = resolve_move_outcome(
        make_game_state(setting_id="starforged"), move, result, match=match, target_npc_id=None
    )
    assert (outcome.progress_marks, outcome.clock_fills) == (progress, clock)


def test_test_your_relationship_marks_progress_on_a_connection_without_a_bond(load_engine: None) -> None:
    from straightjacket.engine.game.finalization import resolve_action_consequences
    from straightjacket.engine.models import RollResult
    from tests._helpers import make_brain_result, make_game_state, make_npc, make_progress_track

    game = make_game_state(setting_id="starforged")
    game.npcs = [make_npc(id="npc_1", name="Mira", status="active")]
    track = make_progress_track(id="connection_npc_1", name="Mira", track_type="connection", rank="dangerous")
    game.progress_tracks.append(track)
    roll = RollResult(4, 1, 2, "heart", 2, 6, "STRONG_HIT", "connection/test_your_relationship", match=False)
    brain = make_brain_result(move="connection/test_your_relationship", target_npc="npc_1")
    action = resolve_action_consequences(game, brain, roll, "risky")
    assert track.ticks == ticks_per_mark(track)
    assert not any(c.startswith("follow-up move") for c in labels_of(action.consequences))
    assert action.outcome.legacy_fixed_ticks == 0


def test_test_your_relationship_chains_develop_your_relationship_with_a_bond(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.game.finalization import resolve_action_consequences
    from straightjacket.engine.models import RollResult
    from straightjacket.engine.ruleset import rolls
    from tests._helpers import make_brain_result, make_game_state, make_npc, make_progress_track

    game = make_game_state(setting_id="starforged")
    game.npcs = [make_npc(id="npc_1", name="Mira", status="active")]
    game.progress_tracks.append(
        make_progress_track(
            id="connection_npc_1", name="Mira", track_type="connection", rank="dangerous", ticks=12, status="bonded"
        )
    )
    dice = [6, 1, 2]
    monkeypatch.setattr(rolls.random, "randint", lambda low, high: dice.pop(0))
    roll = RollResult(4, 1, 2, "heart", 2, 6, "STRONG_HIT", "connection/test_your_relationship", match=False)
    brain = make_brain_result(move="connection/test_your_relationship", target_npc="npc_1")
    action = resolve_action_consequences(game, brain, roll, "risky")
    assert any(c.startswith("follow-up move") and c.endswith("STRONG_HIT") for c in labels_of(action.consequences))
    assert action.outcome is not None
    assert action.outcome.legacy_fixed_ticks == 2


def test_a_chain_without_a_connection_is_skipped(load_engine: None) -> None:
    from straightjacket.engine.game.finalization import resolve_action_consequences
    from straightjacket.engine.models import RollResult
    from tests._helpers import make_brain_result, make_game_state, make_npc

    game = make_game_state(setting_id="starforged")
    game.npcs = [make_npc(id="npc_1", name="Mira", status="active")]
    roll = RollResult(4, 1, 2, "heart", 2, 6, "STRONG_HIT", "connection/test_your_relationship", match=False)
    brain = make_brain_result(move="connection/test_your_relationship", target_npc="npc_1")
    action = resolve_action_consequences(game, brain, roll, "risky")
    assert not any(c.startswith("follow-up move") for c in labels_of(action.consequences))


@pytest.mark.parametrize(
    ("result", "move_name", "ticks", "pays"),
    [("STRONG_HIT", "Make a Discovery", 2, False), ("MISS", "Confront Chaos", 1, False)],
)
def test_explore_a_waypoint_match_chains_an_oracle_move(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, result: str, move_name: str, ticks: int, pays: bool
) -> None:
    from straightjacket.engine.game.finalization import resolve_action_consequences
    from straightjacket.engine.models import RollResult
    from tests._helpers import make_brain_result, make_game_state, record_price_tables

    rolled = record_price_tables(monkeypatch)
    game = make_game_state(setting_id="starforged")
    roll = RollResult(3, 3, 3, "wits", 2, 5, result, "exploration/explore_a_waypoint", match=True)
    action = resolve_action_consequences(game, make_brain_result(move="exploration/explore_a_waypoint"), roll, "risky")
    assert any(c.startswith(f"follow-up move {move_name}: ") for c in labels_of(action.consequences))
    assert game.campaign.legacy["discoveries"].ticks == ticks
    assert bool(rolled) is pays


@pytest.mark.parametrize(("rank", "expected"), [("dangerous", "formidable"), ("epic", "epic")])
def test_develop_your_relationship_match_raises_the_connection_rank(
    load_engine: None, rank: str, expected: str
) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
    from tests._helpers import make_game_state, make_npc, make_progress_track

    game = make_game_state(setting_id="starforged")
    game.npcs = [make_npc(id="npc_1", name="Mira", status="active")]
    track = make_progress_track(id="connection_npc_1", name="Mira", track_type="connection", rank=rank, ticks=0)
    game.progress_tracks.append(track)
    resolve_move_outcome(game, "connection/develop_your_relationship", "STRONG_HIT", target_npc_id="npc_1", match=True)
    assert track.rank == expected


@pytest.mark.parametrize(
    ("effect", "message"),
    [
        ("disposition_shift", "needs a target NPC"),
        ("bond +1", "needs a target NPC"),
        ("raise_connection_rank", "needs a target NPC"),
    ],
)
def test_an_npc_effect_without_a_target_raises(load_engine: None, effect: str, message: str) -> None:
    from straightjacket.engine.ruleset.move_effects import apply_effects, parse_effects
    from tests._helpers import make_game_state

    with pytest.raises(ValueError, match=message):
        apply_effects(make_game_state(setting_id="starforged"), parse_effects([effect]), target_npc_id=None)


@pytest.mark.parametrize("effect", ["bond +1", "raise_connection_rank"])
def test_a_connection_effect_on_an_npc_without_a_connection_raises(load_engine: None, effect: str) -> None:
    from straightjacket.engine.ruleset.move_effects import apply_effects, parse_effects
    from tests._helpers import make_game_state, make_npc

    game = make_game_state(setting_id="starforged")
    game.npcs = [make_npc(id="npc_1", name="Mira")]
    with pytest.raises(ValueError, match="needs a connection with Mira"):
        apply_effects(game, parse_effects([effect]), target_npc_id="npc_1")


@pytest.mark.parametrize(
    ("setting", "move", "acts"),
    [
        ("starforged", "connection/make_a_connection", True),
        ("starforged", "connection/test_your_relationship", True),
        ("starforged", "connection/develop_your_relationship", True),
        ("starforged", "connection/forge_a_bond", False),
        ("starforged", "adventure/face_danger", False),
        ("classic", "relationship/forge_a_bond", False),
    ],
)
def test_which_moves_act_on_an_npc(load_engine: None, setting: str, move: str, acts: bool) -> None:
    from straightjacket.engine.ruleset.move_outcome import acts_on_an_npc
    from tests._helpers import make_game_state

    assert acts_on_an_npc(make_game_state(setting_id=setting), move) is acts


@pytest.mark.parametrize(
    ("setting", "move", "first", "lasting"),
    [
        ("classic", "suffer/endure_harm", "wounded", "maimed"),
        ("classic", "suffer/endure_stress", "shaken", "corrupted"),
        ("starforged", "suffer/endure_harm", "wounded", "permanently_harmed"),
        ("starforged", "suffer/endure_stress", "shaken", "traumatized"),
        ("delve", "suffer/endure_harm", "wounded", "maimed"),
        ("delve", "suffer/endure_stress", "shaken", "corrupted"),
    ],
)
def test_lasting_harm_uses_each_rulebooks_names(
    load_engine: None, setting: str, move: str, first: str, lasting: str
) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
    from tests._helpers import make_game_state

    game = make_game_state(setting_id=setting)
    track = "health" if move.endswith("harm") else "spirit"
    game.resources.meters[track] = 0
    game.impacts = [first]
    resolve_move_outcome(game, move, "MISS", target_npc_id=None, match=False)
    assert lasting in game.impacts


def test_delve_faces_death_with_the_classic_move(load_engine: None) -> None:
    from straightjacket.engine.ruleset.outcome_result import move_outcome_config
    from tests._helpers import make_game_state

    params = move_outcome_config(make_game_state(setting_id="delve"), "suffer/endure_harm")["params"]
    assert params["threshold_move"] == "suffer/face_death"


def test_sundered_isles_discovers_from_its_own_table(load_engine: None) -> None:
    from straightjacket.engine.game.finalization import resolve_action_consequences
    from straightjacket.engine.models import RollResult
    from straightjacket.engine.ruleset.moves import get_moves
    from tests._helpers import make_brain_result, make_game_state

    table = get_moves("sundered_isles")["exploration/make_a_discovery"].tables["make_a_discovery"]
    own = {row.text for row in table.rows}
    game = make_game_state(setting_id="sundered_isles")
    brain = make_brain_result(move="exploration/explore_a_waypoint")
    for _ in range(20):
        roll = RollResult(3, 3, 3, "wits", 2, 5, "STRONG_HIT", "exploration/explore_a_waypoint", match=True)
        action = resolve_action_consequences(game, brain, roll, "risky")
        found = next(c for c in labels_of(action.consequences) if c.startswith("follow-up move Make a Discovery: "))
        assert set(found.split(": ", 1)[1].removesuffix(", made worse").split("; ")) <= own


def test_take_decisive_action_weak_hit_rolls_its_own_table_and_its_cost(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
    from straightjacket.engine.ruleset.moves import get_moves
    from tests._helpers import make_game_state, record_price_tables

    worse = get_moves("starforged")["combat/take_decisive_action"].tables["take_decisive_action"].rows[0].text
    rolled = record_price_tables(monkeypatch)
    fix_dice(monkeypatch, 10)
    game = make_game_state(setting_id="starforged")
    game.resources.meters["spirit"] = 3
    game.resources.meters["supply"] = 3
    outcome = resolve_move_outcome(game, "combat/take_decisive_action", "WEAK_HIT", target_npc_id=None, match=False)
    assert labels_of(outcome.consequences)[0] == f"Take Decisive Action: {worse}"
    assert game.resources.meters["health"] == 3
    assert rolled == []


@pytest.mark.parametrize(("setting", "clue"), [("starforged", True), ("sundered_isles", True), ("classic", False)])
def test_gather_information_rolls_a_story_clue_where_the_move_has_one(
    load_engine: None, setting: str, clue: bool
) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
    from tests._helpers import make_game_state

    for result in ("STRONG_HIT", "WEAK_HIT"):
        game = make_game_state(setting_id=setting)
        outcome = resolve_move_outcome(game, "adventure/gather_information", result, target_npc_id=None, match=False)
        assert any(c.startswith("Story Clue: ") for c in labels_of(outcome.consequences)) is clue


def test_escape_the_depths_miss_reveals_a_danger_that_needs_no_site(load_engine: None) -> None:
    from straightjacket.engine.game.finalization import resolve_action_consequences
    from straightjacket.engine.models import RollResult
    from tests._helpers import make_brain_result, make_game_state

    game = make_game_state(setting_id="delve")
    brain = make_brain_result(move="delve/escape_the_depths")
    for _ in range(30):
        roll = RollResult(1, 9, 9, "edge", 2, 3, "MISS", "delve/escape_the_depths", match=False)
        action = resolve_action_consequences(game, brain, roll, "risky")
        danger = next(c for c in labels_of(action.consequences) if c.startswith("follow-up move Reveal a Danger: "))
        assert "theme card" not in danger
        assert "domain card" not in danger


@pytest.mark.parametrize(("iron", "wits", "rolled"), [(3, 1, ("wits", 1)), (1, 2, ("iron", 1))])
def test_mending_your_own_wounds_rolls_the_lower_stat(
    load_engine: None, iron: int, wits: int, rolled: tuple[str, int]
) -> None:
    from straightjacket.engine.ruleset.make_move import _roll_source
    from straightjacket.engine.ruleset.moves import get_moves
    from tests._helpers import make_brain_result, make_game_state

    game = make_game_state(setting_id="starforged")
    game.stats.update(iron=iron, wits=wits)
    brain = make_brain_result(move="recover/heal", stat="lowest")
    assert _roll_source(game, brain, get_moves("starforged")["recover/heal"]) == rolled


def test_an_engine_chosen_roll_keeps_a_lowest_way_low(load_engine: None) -> None:
    from straightjacket.engine.ruleset.moves import get_moves
    from straightjacket.engine.ruleset.roll_sources import best_roll_option
    from tests._helpers import make_game_state

    game = make_game_state(setting_id="classic")
    game.stats.update(iron=3, wits=1)
    assert best_roll_option(game, get_moves("classic")["adventure/heal"]) == ("wits", 1)
    game.resources.meters["health"] = 2
    assert best_roll_option(game, get_moves("classic")["suffer/endure_harm"]) == ("iron", 3)
