#!/usr/bin/env python3
"""Tests for Mythic GME 2e random events: focus, meaning tables, pipeline, lists.

Run: python -m pytest tests/test_random_events.py -v
"""

# Stubs are set up in conftest.py

from straightjacket.engine.mechanics.random_events import (
    _select_target,
    add_character_weight,
    add_thread_weight,
    consolidate_threads,
    deactivate_thread,
    generate_random_event,
    roll_event_focus,
    roll_meaning_table,
)
from straightjacket.engine.models import (
    CharacterListEntry,
    RandomEvent,
    ThreadEntry,
)
from tests._helpers import make_game_state


# ── Event focus ──────────────────────────────────────────────


def test_event_focus_covers_full_range() -> None:
    """Every d100 value maps to a valid focus category."""
    seen: set[str] = set()
    for roll in range(1, 101):
        focus, actual_roll = roll_event_focus(roll)
        assert focus != "", f"roll {roll} produced empty focus"
        assert actual_roll == roll
        seen.add(focus)
    # All 12 categories should appear
    assert len(seen) == 12


def test_event_focus_boundary_values() -> None:
    """Boundary rolls map to correct categories."""
    assert roll_event_focus(1)[0] == "remote_event"
    assert roll_event_focus(5)[0] == "remote_event"
    assert roll_event_focus(6)[0] == "ambiguous_event"
    assert roll_event_focus(21)[0] == "npc_action"
    assert roll_event_focus(40)[0] == "npc_action"
    assert roll_event_focus(86)[0] == "current_context"
    assert roll_event_focus(100)[0] == "current_context"


# ── Meaning tables ───────────────────────────────────────────


def test_meaning_table_actions_returns_pair() -> None:
    """Actions table returns two non-empty strings."""
    w1, w2 = roll_meaning_table("actions")
    assert w1 and w2
    assert isinstance(w1, str)
    assert isinstance(w2, str)


def test_meaning_table_descriptions_returns_pair() -> None:
    """Descriptions table returns two non-empty strings."""
    w1, w2 = roll_meaning_table("descriptions")
    assert w1 and w2


def test_meaning_table_default_is_actions() -> None:
    """No argument defaults to actions table."""
    w1, w2 = roll_meaning_table()
    assert w1 and w2


# ── Target selection ─────────────────────────────────────────


def test_target_npc_focus_selects_from_characters(load_engine: None) -> None:
    """NPC-focus categories select from characters list."""
    game = make_game_state()
    game.narrative.characters_list = [
        CharacterListEntry(id="c1", name="Kira", weight=1, active=True),
    ]
    name, target_id = _select_target("npc_action", game)
    assert name == "Kira"
    assert target_id == "c1"


def test_target_thread_focus_selects_from_threads(load_engine: None) -> None:
    """Thread-focus categories select from threads list."""
    game = make_game_state()
    game.narrative.threads = [
        ThreadEntry(id="t1", name="Find the vault", weight=1, active=True),
    ]
    name, target_id = _select_target("move_toward_thread", game)
    assert name == "Find the vault"
    assert target_id == "t1"


def test_target_empty_list_returns_empty() -> None:
    """Empty list returns empty target (falls back to current_context)."""
    game = make_game_state()
    name, target_id = _select_target("npc_action", game)
    assert name == ""
    assert target_id == ""


def test_target_pc_focus_no_target() -> None:
    """PC-focus and current_context don't select targets."""
    game = make_game_state()
    game.narrative.characters_list = [
        CharacterListEntry(id="c1", name="Kira", weight=1, active=True),
    ]
    name, _ = _select_target("pc_negative", game)
    assert name == ""
    name2, _ = _select_target("current_context", game)
    assert name2 == ""


def test_target_respects_weight() -> None:
    """Higher-weight entries are more likely to be selected."""
    game = make_game_state()
    game.narrative.characters_list = [
        CharacterListEntry(id="c1", name="Rare", weight=1, active=True),
        CharacterListEntry(id="c2", name="Common", weight=3, active=True),
    ]
    counts: dict[str, int] = {"Rare": 0, "Common": 0}
    for _ in range(200):
        name, _ = _select_target("npc_action", game)
        if name in counts:
            counts[name] += 1
    # Common (weight 3) should appear roughly 3x as often as Rare (weight 1)
    assert counts["Common"] > counts["Rare"]


def test_target_skips_inactive() -> None:
    """Inactive entries are not selected."""
    game = make_game_state()
    game.narrative.threads = [
        ThreadEntry(id="t1", name="Closed", weight=3, active=False),
        ThreadEntry(id="t2", name="Open", weight=1, active=True),
    ]
    name, _ = _select_target("move_toward_thread", game)
    assert name == "Open"


# ── Random event pipeline ────────────────────────────────────


def test_generate_random_event_produces_complete_event() -> None:
    """Pipeline produces a RandomEvent with all fields populated."""
    game = make_game_state()
    game.narrative.threads = [
        ThreadEntry(id="t1", name="Main quest", weight=2, active=True),
    ]
    game.narrative.characters_list = [
        CharacterListEntry(id="c1", name="Kira", weight=1, active=True),
    ]
    event = generate_random_event(game, source="test")
    assert isinstance(event, RandomEvent)
    assert event.focus != ""
    assert event.meaning_action != ""
    assert event.meaning_subject != ""
    assert event.source == "test"


def test_generate_random_event_empty_lists() -> None:
    """Pipeline works with empty NPC/thread lists (falls back to no target)."""
    game = make_game_state()
    event = generate_random_event(game, source="test")
    assert event.focus != ""
    assert event.meaning_action != ""


# ── Fate doublet → random event integration ──────────────────


def test_fate_doublet_generates_random_event(load_engine: None) -> None:
    """Fate doublet with game available triggers random event generation."""
    from straightjacket.engine.mechanics.fate import resolve_fate_chart
    from straightjacket.engine.mechanics.random_events import generate_random_event

    game = make_game_state()
    game.world.chaos_factor = 5
    game.narrative.characters_list = [
        CharacterListEntry(id="c1", name="Kira", weight=1, active=True),
    ]

    # Verify doublet detection works
    chart_result = resolve_fate_chart("fifty_fifty", chaos_factor=5, roll=33)
    assert chart_result.random_event_triggered is True

    # Verify pipeline produces event from game state
    event = generate_random_event(game, source="fate_doublet")
    assert event.source == "fate_doublet"
    assert event.focus != ""


def test_fate_no_doublet_no_event(load_engine: None) -> None:
    """Non-doublet fate roll produces no random event."""
    from straightjacket.engine.mechanics.fate import resolve_fate_chart

    result = resolve_fate_chart("fifty_fifty", chaos_factor=5, roll=34)
    assert result.random_event_triggered is False
    assert result.random_event is None


# ── List maintenance ─────────────────────────────────────────


def test_add_thread_weight_increments() -> None:
    """Thread weight increases by 1 when invoked."""
    game = make_game_state()
    game.narrative.threads = [ThreadEntry(id="t1", name="Quest", weight=1, active=True)]
    add_thread_weight(game, "t1")
    assert game.narrative.threads[0].weight == 2


def test_add_thread_weight_caps_at_3() -> None:
    """Thread weight cannot exceed 3."""
    game = make_game_state()
    game.narrative.threads = [ThreadEntry(id="t1", name="Quest", weight=3, active=True)]
    add_thread_weight(game, "t1")
    assert game.narrative.threads[0].weight == 3


def test_add_character_weight_increments() -> None:
    """Character weight increases by 1 when invoked."""
    game = make_game_state()
    game.narrative.characters_list = [CharacterListEntry(id="c1", name="Kira", weight=1, active=True)]
    add_character_weight(game, "c1")
    assert game.narrative.characters_list[0].weight == 2


def test_consolidate_threads_at_threshold() -> None:
    """Consolidation at 25 entries: weight 3 → 2, others → 1."""
    game = make_game_state()
    for i in range(25):
        w = 3 if i < 5 else 1
        game.narrative.threads.append(ThreadEntry(id=f"t{i}", name=f"Thread {i}", weight=w, active=True))
    consolidate_threads(game)
    heavy = [t for t in game.narrative.threads if t.weight == 2]
    light = [t for t in game.narrative.threads if t.weight == 1]
    assert len(heavy) == 5
    assert len(light) == 20


def test_consolidate_threads_under_threshold_noop() -> None:
    """Consolidation does nothing below 25 entries."""
    game = make_game_state()
    game.narrative.threads = [ThreadEntry(id="t1", name="Quest", weight=3, active=True)]
    consolidate_threads(game)
    assert game.narrative.threads[0].weight == 3


def test_deactivate_thread() -> None:
    """Deactivated thread is marked inactive."""
    game = make_game_state()
    game.narrative.threads = [ThreadEntry(id="t1", name="Quest", weight=2, active=True)]
    deactivate_thread(game, "t1")
    assert game.narrative.threads[0].active is False


# ── RandomEvent serialization ────────────────────────────────


def test_random_event_roundtrip() -> None:
    """RandomEvent round-trips through to_dict/from_dict."""
    event = RandomEvent(
        focus="npc_action",
        focus_roll=25,
        target="Kira",
        target_id="c1",
        meaning_action="Abandon",
        meaning_subject="Advantage",
        meaning_table="actions",
        source="fate_doublet",
    )
    d = event.to_dict()
    restored = RandomEvent.from_dict(d)
    assert restored.focus == "npc_action"
    assert restored.target == "Kira"
    assert restored.meaning_action == "Abandon"
    assert restored.source == "fate_doublet"


def test_fate_result_with_random_event_roundtrip() -> None:
    """FateResult with attached RandomEvent survives serialization."""
    from straightjacket.engine.models import FateResult

    event = RandomEvent(focus="pc_negative", meaning_action="Betray", meaning_subject="Hope")
    result = FateResult(
        answer="yes",
        random_event_triggered=True,
        random_event=event,
    )
    d = result.to_dict()
    restored = FateResult.from_dict(d)
    assert restored.random_event_triggered is True
    assert restored.random_event is not None
    assert restored.random_event.focus == "pc_negative"
    assert restored.random_event.meaning_action == "Betray"
