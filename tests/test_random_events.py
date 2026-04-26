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
from tests._helpers import make_fate_result, make_game_state, make_random_event


def test_event_focus_covers_full_range() -> None:
    seen: set[str] = set()
    for roll in range(1, 101):
        focus, actual_roll = roll_event_focus(roll)
        assert focus != "", f"roll {roll} produced empty focus"
        assert actual_roll == roll
        seen.add(focus)

    assert len(seen) == 12


def test_event_focus_boundary_values() -> None:
    assert roll_event_focus(1)[0] == "remote_event"
    assert roll_event_focus(5)[0] == "remote_event"
    assert roll_event_focus(6)[0] == "ambiguous_event"
    assert roll_event_focus(21)[0] == "npc_action"
    assert roll_event_focus(40)[0] == "npc_action"
    assert roll_event_focus(86)[0] == "current_context"
    assert roll_event_focus(100)[0] == "current_context"


def test_meaning_table_actions_returns_pair() -> None:
    w1, w2 = roll_meaning_table("actions")
    assert w1 and w2
    assert isinstance(w1, str)
    assert isinstance(w2, str)


def test_meaning_table_descriptions_returns_pair() -> None:
    w1, w2 = roll_meaning_table("descriptions")
    assert w1 and w2


def test_meaning_table_requires_table_name() -> None:
    import pytest

    with pytest.raises(TypeError):
        roll_meaning_table()


def test_target_npc_focus_selects_from_characters(load_engine: None) -> None:
    game = make_game_state()
    game.narrative.characters_list = [
        CharacterListEntry(id="c1", name="Kira", weight=1, active=True, entry_type="npc"),
    ]
    name, target_id = _select_target("npc_action", game)
    assert name == "Kira"
    assert target_id == "c1"


def test_target_thread_focus_selects_from_threads(load_engine: None) -> None:
    game = make_game_state()
    game.narrative.threads = [
        ThreadEntry(id="t1", name="Find the vault", weight=1, active=True, source="creation", thread_type="vow"),
    ]
    name, target_id = _select_target("move_toward_thread", game)
    assert name == "Find the vault"
    assert target_id == "t1"


def test_target_empty_list_returns_empty() -> None:
    game = make_game_state()
    name, target_id = _select_target("npc_action", game)
    assert name == ""
    assert target_id == ""


def test_target_pc_focus_no_target() -> None:
    game = make_game_state()
    game.narrative.characters_list = [
        CharacterListEntry(id="c1", name="Kira", weight=1, active=True, entry_type="npc"),
    ]
    name, _ = _select_target("pc_negative", game)
    assert name == ""
    name2, _ = _select_target("current_context", game)
    assert name2 == ""


def test_target_respects_weight() -> None:
    game = make_game_state()
    game.narrative.characters_list = [
        CharacterListEntry(id="c1", name="Rare", weight=1, active=True, entry_type="npc"),
        CharacterListEntry(id="c2", name="Common", weight=3, active=True, entry_type="npc"),
    ]
    counts: dict[str, int] = {"Rare": 0, "Common": 0}
    for _ in range(200):
        name, _ = _select_target("npc_action", game)
        if name in counts:
            counts[name] += 1

    assert counts["Common"] > counts["Rare"]


def test_target_skips_inactive() -> None:
    game = make_game_state()
    game.narrative.threads = [
        ThreadEntry(id="t1", name="Closed", weight=3, active=False, source="creation", thread_type="vow"),
        ThreadEntry(id="t2", name="Open", weight=1, active=True, source="creation", thread_type="vow"),
    ]
    name, _ = _select_target("move_toward_thread", game)
    assert name == "Open"


def test_generate_random_event_produces_complete_event() -> None:
    game = make_game_state()
    game.narrative.threads = [
        ThreadEntry(id="t1", name="Main quest", weight=2, active=True, source="creation", thread_type="vow"),
    ]
    game.narrative.characters_list = [
        CharacterListEntry(id="c1", name="Kira", weight=1, active=True, entry_type="npc"),
    ]
    event = generate_random_event(game, source="test")
    assert isinstance(event, RandomEvent)
    assert event.focus != ""
    assert event.meaning_action != ""
    assert event.meaning_subject != ""
    assert event.source == "test"


def test_generate_random_event_empty_lists() -> None:
    game = make_game_state()
    event = generate_random_event(game, source="test")
    assert event.focus != ""
    assert event.meaning_action != ""


def test_fate_doublet_generates_random_event(load_engine: None) -> None:
    from straightjacket.engine.mechanics.fate import resolve_fate_chart
    from straightjacket.engine.mechanics.random_events import generate_random_event

    game = make_game_state()
    game.world.chaos_factor = 5
    game.narrative.characters_list = [
        CharacterListEntry(id="c1", name="Kira", weight=1, active=True, entry_type="npc"),
    ]

    chart_result = resolve_fate_chart("fifty_fifty", chaos_factor=5, roll=33, question="")
    assert chart_result.random_event_triggered is True

    event = generate_random_event(game, source="fate_doublet")
    assert event.source == "fate_doublet"
    assert event.focus != ""


def test_fate_no_doublet_no_event(load_engine: None) -> None:
    from straightjacket.engine.mechanics.fate import resolve_fate_chart

    result = resolve_fate_chart("fifty_fifty", chaos_factor=5, roll=34, question="")
    assert result.random_event_triggered is False
    assert result.random_event is None


def test_add_thread_weight_increments() -> None:
    game = make_game_state()
    game.narrative.threads = [
        ThreadEntry(id="t1", name="Quest", weight=1, active=True, source="creation", thread_type="vow")
    ]
    add_thread_weight(game, "t1")
    assert game.narrative.threads[0].weight == 2


def test_add_thread_weight_caps_at_3() -> None:
    game = make_game_state()
    game.narrative.threads = [
        ThreadEntry(id="t1", name="Quest", weight=3, active=True, source="creation", thread_type="vow")
    ]
    add_thread_weight(game, "t1")
    assert game.narrative.threads[0].weight == 3


def test_add_character_weight_increments() -> None:
    game = make_game_state()
    game.narrative.characters_list = [CharacterListEntry(id="c1", name="Kira", weight=1, active=True, entry_type="npc")]
    add_character_weight(game, "c1")
    assert game.narrative.characters_list[0].weight == 2


def test_consolidate_threads_at_threshold() -> None:
    game = make_game_state()
    for i in range(25):
        w = 3 if i < 5 else 1
        game.narrative.threads.append(
            ThreadEntry(id=f"t{i}", name=f"Thread {i}", weight=w, active=True, source="creation", thread_type="vow")
        )
    consolidate_threads(game)
    heavy = [t for t in game.narrative.threads if t.weight == 2]
    light = [t for t in game.narrative.threads if t.weight == 1]
    assert len(heavy) == 5
    assert len(light) == 20


def test_consolidate_threads_under_threshold_noop() -> None:
    game = make_game_state()
    game.narrative.threads = [
        ThreadEntry(id="t1", name="Quest", weight=3, active=True, source="creation", thread_type="vow")
    ]
    consolidate_threads(game)
    assert game.narrative.threads[0].weight == 3


def test_deactivate_thread() -> None:
    game = make_game_state()
    game.narrative.threads = [
        ThreadEntry(id="t1", name="Quest", weight=2, active=True, source="creation", thread_type="vow")
    ]
    deactivate_thread(game, "t1")
    assert game.narrative.threads[0].active is False


def test_random_event_roundtrip() -> None:
    event = make_random_event(
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
    from straightjacket.engine.models import FateResult

    event = make_random_event(focus="pc_negative", meaning_action="Betray", meaning_subject="Hope")
    result = make_fate_result(
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
