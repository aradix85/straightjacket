from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
GAIN = re.compile(r"take \+(\d) momentum", re.I)
LOSS = re.compile(r"(?:suffer|lose) -(\d) momentum", re.I)
KNOWN_DIVERGENCES = {
    ("classic", "adventure/secure_an_advantage", "weak_hit"),
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

    outcomes = yaml.safe_load((REPO / "engine" / "move_outcomes.yaml").read_text(encoding="utf-8"))["move_outcomes"]
    found = set()
    for setting in ("starforged", "classic"):
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
                single = len(gains) == 1 and "choose" not in text.lower() and " or " not in text.lower()
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
