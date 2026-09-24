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


class _FakeOracle:
    def __init__(self, *values: str) -> None:
        self.values = list(values)

    def oracle_data_for(self, path: str) -> _FakeOracle:
        return self

    def oracle(self, path: str) -> _FakeOracle:
        return self

    def roll(self) -> object:
        from types import SimpleNamespace

        return SimpleNamespace(value=self.values.pop(0))


@pytest.mark.parametrize("setting", ["starforged", "classic"])
def test_pay_the_price_rolls_the_official_table(load_engine: None, setting: str) -> None:
    import json

    from straightjacket.engine.mechanics.move_effects import OutcomeResult, pay_the_price
    from tests._helpers import make_game_state

    data = json.loads((REPO / "data" / f"{setting}.json").read_text(encoding="utf-8"))
    rows = [
        re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", r["text"]).strip()
        for r in data["oracles"]["moves"]["contents"]["pay_the_price"]["rows"]
    ]
    game = make_game_state(setting_id=setting)
    for _ in range(30):
        result = OutcomeResult()
        pay_the_price(game, result)
        assert all(part in rows for part in result.consequences[0].split("; "))


def test_pay_the_price_harm_costs_health(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.mechanics import move_effects
    from tests._helpers import make_game_state

    monkeypatch.setattr(move_effects, "load_package", lambda setting: _FakeOracle("You are harmed"))
    game = make_game_state(setting_id="starforged")
    game.resources.health = 4
    move_effects.pay_the_price(game, move_effects.OutcomeResult())
    assert game.resources.health == 3


def test_pay_the_price_roll_twice_adds_two_results(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.mechanics import move_effects
    from tests._helpers import make_game_state

    fake = _FakeOracle("Roll twice", "You are stressed", "A new enemy is revealed")
    monkeypatch.setattr(move_effects, "load_package", lambda setting: fake)
    game = make_game_state(setting_id="starforged")
    game.resources.spirit = 4
    result = move_effects.OutcomeResult()
    move_effects.pay_the_price(game, result)
    assert result.consequences[0].split("; ") == ["Roll twice", "You are stressed", "A new enemy is revealed"]
    assert game.resources.spirit == 3


@pytest.mark.parametrize(("setting", "pays"), [("classic", True), ("starforged", False)])
def test_enter_the_fray_miss_pays_the_price_only_in_classic(load_engine: None, setting: str, pays: bool) -> None:
    from straightjacket.engine.mechanics.move_outcome import resolve_move_outcome
    from tests._helpers import make_game_state

    outcome = resolve_move_outcome(make_game_state(setting_id=setting), "combat/enter_the_fray", "MISS")
    assert outcome.pay_the_price is pays


KNOWN_MATCH_GAPS: set[tuple[str, str, str]] = set()


def test_every_match_clause_is_modelled_or_known(load_engine: None) -> None:
    from straightjacket.engine.datasworn.moves import get_moves

    table = yaml.safe_load((REPO / "engine" / "move_outcomes.yaml").read_text(encoding="utf-8"))
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
    from straightjacket.engine.mechanics.move_outcome import resolve_move_outcome
    from tests._helpers import make_game_state

    outcome = resolve_move_outcome(make_game_state(setting_id="starforged"), move, result, match=match)
    assert (outcome.progress_marks, outcome.clock_fills) == (progress, clock)


def test_test_your_relationship_chains_develop_your_relationship(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.game.finalization import resolve_action_consequences
    from straightjacket.engine.mechanics import consequences
    from straightjacket.engine.models import RollResult
    from tests._helpers import make_brain_result, make_game_state, make_npc, make_progress_track

    game = make_game_state(setting_id="starforged")
    game.npcs = [make_npc(id="npc_1", name="Mira", status="active")]
    game.progress_tracks.append(
        make_progress_track(id="connection_npc_1", name="Mira", track_type="connection", rank="dangerous", ticks=0)
    )
    dice = [6, 1, 2]
    monkeypatch.setattr(consequences.random, "randint", lambda low, high: dice.pop(0))
    roll = RollResult(4, 0, 1, 2, "heart", 2, 6, "STRONG_HIT", "connection/test_your_relationship", match=False)
    brain = make_brain_result(move="connection/test_your_relationship", target_npc="npc_1")
    action = resolve_action_consequences(game, brain, roll, "risky")
    assert any(c.startswith("follow-up move") and c.endswith("STRONG_HIT") for c in action.consequences)
    assert action.outcome is not None
    assert action.outcome.legacy_fixed_ticks == 2


def test_a_chain_without_a_connection_is_skipped(load_engine: None) -> None:
    from straightjacket.engine.game.finalization import resolve_action_consequences
    from straightjacket.engine.models import RollResult
    from tests._helpers import make_brain_result, make_game_state, make_npc

    game = make_game_state(setting_id="starforged")
    game.npcs = [make_npc(id="npc_1", name="Mira", status="active")]
    roll = RollResult(4, 0, 1, 2, "heart", 2, 6, "STRONG_HIT", "connection/test_your_relationship", match=False)
    brain = make_brain_result(move="connection/test_your_relationship", target_npc="npc_1")
    action = resolve_action_consequences(game, brain, roll, "risky")
    assert not any(c.startswith("follow-up move") for c in action.consequences)


@pytest.mark.parametrize(
    ("result", "move_name", "ticks", "pays"),
    [("STRONG_HIT", "Make a Discovery", 2, False), ("MISS", "Confront Chaos", 1, False)],
)
def test_explore_a_waypoint_match_chains_an_oracle_move(
    load_engine: None, result: str, move_name: str, ticks: int, pays: bool
) -> None:
    from straightjacket.engine.game.finalization import resolve_action_consequences
    from straightjacket.engine.mechanics.legacy import get_legacy_track
    from straightjacket.engine.models import RollResult
    from tests._helpers import make_brain_result, make_game_state

    game = make_game_state(setting_id="starforged")
    roll = RollResult(3, 0, 3, 3, "wits", 2, 5, result, "exploration/explore_a_waypoint", match=True)
    action = resolve_action_consequences(game, make_brain_result(move="exploration/explore_a_waypoint"), roll, "risky")
    assert any(c.startswith(f"follow-up move {move_name}: ") for c in action.consequences)
    assert get_legacy_track(game, "discoveries").ticks == ticks
    assert action.outcome is not None
    assert action.outcome.pay_the_price is pays


@pytest.mark.parametrize(("rank", "expected"), [("dangerous", "formidable"), ("epic", "epic")])
def test_develop_your_relationship_match_raises_the_connection_rank(
    load_engine: None, rank: str, expected: str
) -> None:
    from straightjacket.engine.mechanics.move_outcome import resolve_move_outcome
    from tests._helpers import make_game_state, make_npc, make_progress_track

    game = make_game_state(setting_id="starforged")
    game.npcs = [make_npc(id="npc_1", name="Mira", status="active")]
    track = make_progress_track(id="connection_npc_1", name="Mira", track_type="connection", rank=rank, ticks=0)
    game.progress_tracks.append(track)
    resolve_move_outcome(game, "connection/develop_your_relationship", "STRONG_HIT", target_npc_id="npc_1", match=True)
    assert track.rank == expected


@pytest.mark.parametrize(
    ("setting", "move", "first", "lasting"),
    [
        ("classic", "suffer/endure_harm", "wounded", "maimed"),
        ("classic", "suffer/endure_stress", "shaken", "corrupted"),
        ("starforged", "suffer/endure_harm", "wounded", "permanently_harmed"),
        ("starforged", "suffer/endure_stress", "shaken", "traumatized"),
    ],
)
def test_lasting_harm_uses_each_rulebooks_names(
    load_engine: None, setting: str, move: str, first: str, lasting: str
) -> None:
    from straightjacket.engine.mechanics.move_outcome import resolve_move_outcome
    from tests._helpers import make_game_state

    game = make_game_state(setting_id=setting)
    track = "health" if move.endswith("harm") else "spirit"
    setattr(game.resources, track, 0)
    game.impacts = [first]
    resolve_move_outcome(game, move, "MISS")
    assert lasting in game.impacts
