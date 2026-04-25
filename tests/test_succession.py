"""Tests for character succession (Continue a Legacy).

Covers the deterministic engine layer: inheritance rolls, NPC carryover,
thread filtering, predecessor archive, and the prepare/start lifecycle
pre- and post-AI. The full AI-coupled start_succession_with_character flow
is exercised by Elvira; here we mock the chapter-close + opening AI calls
to cover the orchestration surface.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from straightjacket.engine.engine_loader import eng
from straightjacket.engine.game.succession import (
    END_REASONS,
    _filter_threads_for_successor,
    _replace_character_identity,
    _reset_for_successor,
    determine_end_reason,
    prepare_succession,
    start_succession_with_character,
)
from straightjacket.engine.mechanics import (
    apply_npc_carryover,
    build_predecessor_record,
    run_inheritance_rolls,
    seed_successor_legacy,
)
from straightjacket.engine.models import (
    CampaignState,
    GameState,
    ThreadEntry,
)
from tests._helpers import (
    make_game_state,
    make_inheritance_roll,
    make_npc,
    make_predecessor,
    make_progress_track,
    make_threat,
)


# ── Fixtures ────────────────────────────────────────────────


@pytest.fixture
def aria(load_engine: None) -> GameState:
    """A predecessor character with some accumulated legacy and NPCs."""
    g = make_game_state(
        player_name="Aria",
        pronouns="she/her",
        character_concept="outlander, deepwoods",
        background_vow="avenge sister",
        setting_id="classic",
    )
    g.campaign.legacy_quests.ticks = 24  # 6 boxes
    g.campaign.legacy_bonds.ticks = 8  # 2 boxes
    g.campaign.legacy_discoveries.ticks = 16  # 4 boxes
    g.narrative.scene_count = 42
    g.campaign.chapter_number = 2
    return g


# ── Predecessor record ─────────────────────────────────────


def test_build_predecessor_captures_pre_roll_state(aria: GameState) -> None:
    record = build_predecessor_record(aria, "death")
    assert record.player_name == "Aria"
    assert record.pronouns == "she/her"
    assert record.background_vow == "avenge sister"
    assert record.setting_id == "classic"
    assert record.chapters_played == 2
    assert record.scenes_played == 42
    assert record.end_reason == "death"
    assert record.legacy_quests_filled_boxes == 6
    assert record.legacy_bonds_filled_boxes == 2
    assert record.legacy_discoveries_filled_boxes == 4
    assert record.inheritance_rolls == []  # filled in by caller


# ── Inheritance rolls ──────────────────────────────────────


def test_run_inheritance_rolls_returns_one_per_legacy_track(aria: GameState) -> None:
    rolls = run_inheritance_rolls(aria)
    track_names = {r.track_name for r in rolls}
    assert track_names == {"quests", "bonds", "discoveries"}


def test_run_inheritance_rolls_does_not_mutate_predecessor(aria: GameState) -> None:
    pre_quests = aria.campaign.legacy_quests.filled_boxes
    pre_bonds = aria.campaign.legacy_bonds.filled_boxes
    pre_disc = aria.campaign.legacy_discoveries.filled_boxes
    run_inheritance_rolls(aria)
    assert aria.campaign.legacy_quests.filled_boxes == pre_quests
    assert aria.campaign.legacy_bonds.filled_boxes == pre_bonds
    assert aria.campaign.legacy_discoveries.filled_boxes == pre_disc


def test_run_inheritance_rolls_uses_predecessor_filled_boxes(aria: GameState) -> None:
    rolls = run_inheritance_rolls(aria)
    by_name = {r.track_name: r for r in rolls}
    assert by_name["quests"].predecessor_filled_boxes == 6
    assert by_name["bonds"].predecessor_filled_boxes == 2
    assert by_name["discoveries"].predecessor_filled_boxes == 4


def test_run_inheritance_rolls_strong_hit_keeps_full_value() -> None:
    # A track at 8 filled boxes vs two low challenge dice forces STRONG_HIT.
    g = make_game_state()
    g.campaign.legacy_quests.ticks = 32  # 8 boxes
    random.seed(0)  # 0 → c1=4, c2=2 typically; keep low
    # Force outcome: monkeypatch random in the consequences module to return low rolls.
    import straightjacket.engine.mechanics.consequences as cons_mod

    class _Dice:
        def __init__(self) -> None:
            self.calls = 0

        def randint(self, a: int, b: int) -> int:
            self.calls += 1
            return 1  # always 1 → both challenge dice = 1, score=8 > 1+1 = STRONG

    dice = _Dice()
    real = cons_mod.random
    cons_mod.random = dice  # type: ignore[assignment]
    try:
        rolls = run_inheritance_rolls(g)
    finally:
        cons_mod.random = real  # type: ignore[assignment]
    quests = next(r for r in rolls if r.track_name == "quests")
    assert quests.result == "STRONG_HIT"
    assert quests.fraction == 1.0
    assert quests.new_filled_boxes == 8


def test_run_inheritance_rolls_miss_loses_everything() -> None:
    # Force MISS: high challenge dice vs low filled_boxes.
    g = make_game_state()
    g.campaign.legacy_quests.ticks = 8  # 2 boxes — very low

    import straightjacket.engine.mechanics.consequences as cons_mod

    class _Dice:
        def randint(self, a: int, b: int) -> int:
            return 10  # both challenge dice = 10 → MISS

    real = cons_mod.random
    cons_mod.random = _Dice()  # type: ignore[assignment]
    try:
        rolls = run_inheritance_rolls(g)
    finally:
        cons_mod.random = real  # type: ignore[assignment]
    quests = next(r for r in rolls if r.track_name == "quests")
    assert quests.result == "MISS"
    assert quests.fraction == 0.0
    assert quests.new_filled_boxes == 0


def test_run_inheritance_rolls_weak_hit_halves() -> None:
    # 6 filled boxes, c1=4 c2=8 → score 6 > 4 but not > 8 → WEAK_HIT
    g = make_game_state()
    g.campaign.legacy_quests.ticks = 24  # 6 boxes

    import straightjacket.engine.mechanics.consequences as cons_mod

    class _Dice:
        def __init__(self) -> None:
            self.values = iter([4, 8] * 10)  # alternating

        def randint(self, a: int, b: int) -> int:
            return next(self.values)

    real = cons_mod.random
    cons_mod.random = _Dice()  # type: ignore[assignment]
    try:
        rolls = run_inheritance_rolls(g)
    finally:
        cons_mod.random = real  # type: ignore[assignment]
    quests = next(r for r in rolls if r.track_name == "quests")
    assert quests.result == "WEAK_HIT"
    assert quests.fraction == 0.5
    assert quests.new_filled_boxes == 3


# ── Seed successor legacy ──────────────────────────────────


def test_seed_successor_legacy_overwrites_tracks(aria: GameState) -> None:
    rolls = [
        make_inheritance_roll(track_name="quests", new_filled_boxes=3),
        make_inheritance_roll(track_name="bonds", new_filled_boxes=0),
        make_inheritance_roll(track_name="discoveries", new_filled_boxes=8),
    ]
    seed_successor_legacy(aria, rolls)
    assert aria.campaign.legacy_quests.filled_boxes == 3
    assert aria.campaign.legacy_bonds.filled_boxes == 0
    assert aria.campaign.legacy_discoveries.filled_boxes == 8


def test_seed_successor_legacy_resets_status(aria: GameState) -> None:
    aria.campaign.legacy_quests.status = "completed"  # nonsense but possible
    rolls = [
        make_inheritance_roll(track_name="quests", new_filled_boxes=3),
        make_inheritance_roll(track_name="bonds", new_filled_boxes=0),
        make_inheritance_roll(track_name="discoveries", new_filled_boxes=0),
    ]
    seed_successor_legacy(aria, rolls)
    assert aria.campaign.legacy_quests.status == "active"


def test_seed_successor_legacy_preserves_xp(aria: GameState) -> None:
    aria.campaign.xp = 10
    aria.campaign.xp_spent = 4
    rolls = [
        make_inheritance_roll(track_name="quests", new_filled_boxes=0),
        make_inheritance_roll(track_name="bonds", new_filled_boxes=0),
        make_inheritance_roll(track_name="discoveries", new_filled_boxes=0),
    ]
    seed_successor_legacy(aria, rolls)
    assert aria.campaign.xp == 10
    assert aria.campaign.xp_spent == 4


# ── NPC carryover ──────────────────────────────────────────


def test_carryover_active_npc_full_track() -> None:
    npc = make_npc(id="npc_1", name="Mira", status="active")
    track = make_progress_track(
        id="connection_npc_1", name="Mira", track_type="connection", rank="dangerous", ticks=24
    )  # 6 boxes
    kept_npcs, kept_tracks = apply_npc_carryover([npc], [track])
    assert len(kept_npcs) == 1 and kept_npcs[0].id == "npc_1"
    assert len(kept_tracks) == 1
    assert kept_tracks[0].filled_boxes == 6


def test_carryover_background_npc_halves_track() -> None:
    npc = make_npc(id="npc_2", name="Talo", status="background")
    track = make_progress_track(
        id="connection_npc_2", name="Talo", track_type="connection", rank="dangerous", ticks=24
    )  # 6 boxes
    kept_npcs, kept_tracks = apply_npc_carryover([npc], [track])
    assert len(kept_npcs) == 1
    assert kept_tracks[0].filled_boxes == 3  # halved


def test_carryover_lore_npc_halves_track() -> None:
    npc = make_npc(id="npc_3", name="Arenmar the Lost", status="lore")
    track = make_progress_track(
        id="connection_npc_3", name="Arenmar", track_type="connection", rank="dangerous", ticks=20
    )  # 5 boxes
    kept_npcs, kept_tracks = apply_npc_carryover([npc], [track])
    assert len(kept_npcs) == 1
    assert kept_tracks[0].filled_boxes == 2  # round(5*0.5) = 2 (banker's rounding to even)


def test_carryover_deceased_npc_pruned_entirely() -> None:
    alive = make_npc(id="npc_a", name="Alive", status="active")
    dead = make_npc(id="npc_d", name="Dead", status="deceased")
    alive_track = make_progress_track(
        id="connection_npc_a", name="Alive", track_type="connection", rank="dangerous", ticks=8
    )
    dead_track = make_progress_track(
        id="connection_npc_d", name="Dead", track_type="connection", rank="dangerous", ticks=12
    )
    kept_npcs, kept_tracks = apply_npc_carryover([alive, dead], [alive_track, dead_track])
    kept_ids = {n.id for n in kept_npcs}
    assert kept_ids == {"npc_a"}
    kept_track_ids = {t.id for t in kept_tracks}
    assert kept_track_ids == {"connection_npc_a"}


def test_carryover_unknown_status_raises() -> None:
    npc = make_npc(id="npc_x", name="Strange", status="active")
    npc.status = "weird"  # bypass enum
    with pytest.raises(ValueError, match="no succession.npc_carryover rule"):
        apply_npc_carryover([npc], [])


def test_carryover_preserves_track_name_and_rank() -> None:
    npc = make_npc(id="npc_1", name="Mira", status="active")
    track = make_progress_track(
        id="connection_npc_1", name="Mira Whisperer", track_type="connection", rank="formidable", ticks=16
    )
    _, kept_tracks = apply_npc_carryover([npc], [track])
    assert kept_tracks[0].name == "Mira Whisperer"
    assert kept_tracks[0].rank == "formidable"


# ── Thread filtering ───────────────────────────────────────


def test_filter_drops_vow_threads() -> None:
    threads = [
        ThreadEntry(id="t1", name="Avenge sister", thread_type="vow", source="creation"),
        ThreadEntry(id="t2", name="Find ally", thread_type="vow", source="vow"),
    ]
    kept = _filter_threads_for_successor(threads)
    assert kept == []


def test_filter_drops_creation_threads_regardless_of_type() -> None:
    threads = [
        ThreadEntry(id="t1", name="Old fear", thread_type="tension", source="creation"),
        ThreadEntry(id="t2", name="Faction war", thread_type="subplot", source="director"),
        ThreadEntry(id="t3", name="Rumor", thread_type="goal", source="event"),
    ]
    kept = _filter_threads_for_successor(threads)
    kept_ids = {t.id for t in kept}
    assert kept_ids == {"t2", "t3"}


# ── prepare_succession ─────────────────────────────────────


def test_prepare_succession_archives_and_sets_flag(aria: GameState) -> None:
    record = prepare_succession(aria, "death")
    assert aria.campaign.pending_succession is True
    assert aria.campaign.predecessors[-1] is record
    assert len(record.inheritance_rolls) == 3


def test_prepare_succession_rejects_unknown_reason(aria: GameState) -> None:
    with pytest.raises(ValueError, match="end_reason"):
        prepare_succession(aria, "exhaustion")


def test_prepare_succession_rejects_double_call(aria: GameState) -> None:
    prepare_succession(aria, "death")
    with pytest.raises(ValueError, match="pending_succession"):
        prepare_succession(aria, "retire")


def test_prepare_succession_accepts_each_known_reason(aria: GameState) -> None:
    for reason in END_REASONS:
        g = make_game_state(setting_id="classic")
        g.campaign.legacy_quests.ticks = 4
        record = prepare_succession(g, reason)
        assert record.end_reason == reason


# ── determine_end_reason ───────────────────────────────────


def test_determine_end_reason_health_zero_only() -> None:
    g = make_game_state()
    g.resources.health = 0
    g.resources.spirit = 3
    assert determine_end_reason(g) == "death"


def test_determine_end_reason_spirit_zero_only() -> None:
    g = make_game_state()
    g.resources.health = 3
    g.resources.spirit = 0
    assert determine_end_reason(g) == "despair"


def test_determine_end_reason_both_zero() -> None:
    g = make_game_state()
    g.resources.health = 0
    g.resources.spirit = 0
    assert determine_end_reason(g) == "death"


def test_determine_end_reason_face_death_path() -> None:
    # face_death MISS sets game_over=True without zeroing resources.
    g = make_game_state()
    g.resources.health = 3
    g.resources.spirit = 3
    assert determine_end_reason(g) == "death"


# ── Pending succession survives snapshot/restore ───────────


def test_pending_succession_round_trips_through_campaign_snapshot(aria: GameState) -> None:
    aria.campaign.pending_succession = True
    snap = aria.campaign.snapshot()
    aria.campaign.pending_succession = False
    aria.campaign.restore(snap)
    assert aria.campaign.pending_succession is True


def test_pending_succession_serialises_through_to_dict(aria: GameState) -> None:
    aria.campaign.pending_succession = True
    data = aria.campaign.to_dict()
    fresh = CampaignState.from_dict(data)
    assert fresh.pending_succession is True


# ── _reset_for_successor ───────────────────────────────────


def test_reset_for_successor_clears_pc_state_keeps_world(aria: GameState) -> None:
    # Populate predecessor-specific PC state
    aria.impacts = ["wounded", "shaken"]
    aria.assets = ["asset_a"]
    aria.resources.health = 1
    aria.resources.spirit = 0
    aria.world.clocks = []
    aria.narrative.story_blueprint = None
    surviving_threats = [make_threat(id="thr_1", name="Faction war")]

    _reset_for_successor(
        aria,
        surviving_threads=[ThreadEntry(id="t1", name="Faction war", thread_type="subplot", source="director")],
        surviving_threats=surviving_threats,
        surviving_npcs=[],
        surviving_connection_tracks=[],
    )

    assert aria.impacts == []
    assert aria.assets == []
    assert aria.resources.health == eng().resources.health_start
    assert aria.resources.spirit == eng().resources.spirit_start
    assert aria.world.clocks == []
    assert aria.narrative.scene_count == 1
    assert aria.crisis_mode is False
    assert aria.game_over is False
    assert len(aria.threats) == 1  # surviving threat preserved
    assert aria.threats[0].id == "thr_1"


def test_reset_for_successor_filters_characters_list(aria: GameState) -> None:
    from straightjacket.engine.models import CharacterListEntry

    keeper_npc = make_npc(id="npc_keep", name="Keep", status="active")
    aria.narrative.characters_list = [
        CharacterListEntry(id="npc_keep", name="Keep", entry_type="npc", weight=1),
        CharacterListEntry(id="npc_dropped", name="Dropped", entry_type="npc", weight=1),
        CharacterListEntry(id="char_vow_subject", name="Sister", entry_type="abstract", weight=2),
    ]
    _reset_for_successor(
        aria,
        surviving_threads=[],
        surviving_threats=[],
        surviving_npcs=[keeper_npc],
        surviving_connection_tracks=[],
    )
    kept_ids = {c.id for c in aria.narrative.characters_list}
    assert kept_ids == {"npc_keep"}


# ── _replace_character_identity ────────────────────────────


def test_replace_character_identity_strict_required_fields(aria: GameState) -> None:
    # All-strict subscript order: setting_id, stats, player_name, pronouns,
    # background_vow, paths, backstory. Missing any one raises KeyError.
    base = {
        "setting_id": "classic",
        "stats": {"edge": 3, "heart": 2, "iron": 2, "shadow": 1, "wits": 1},
        "player_name": "Bryn",
        "pronouns": "they/them",
        "background_vow": "find truth",
        "paths": [],
        "backstory": "",
    }
    for missing in ("player_name", "pronouns", "background_vow", "paths", "backstory"):
        creation_data = {k: v for k, v in base.items() if k != missing}
        with pytest.raises(KeyError, match=missing):
            _replace_character_identity(aria, creation_data)


def test_replace_character_identity_empty_background_vow_raises(aria: GameState) -> None:
    creation_data = {
        "setting_id": "classic",
        "stats": {"edge": 3, "heart": 2, "iron": 2, "shadow": 1, "wits": 1},
        "player_name": "Bryn",
        "pronouns": "they/them",
        "background_vow": "",  # empty
        "paths": [],
        "backstory": "",
    }
    with pytest.raises(ValueError, match="background_vow"):
        _replace_character_identity(aria, creation_data)


def test_replace_character_identity_empty_player_name_raises(aria: GameState) -> None:
    creation_data = {
        "setting_id": "classic",
        "stats": {"edge": 3, "heart": 2, "iron": 2, "shadow": 1, "wits": 1},
        "player_name": "",
        "pronouns": "they/them",
        "background_vow": "find truth",
        "paths": [],
        "backstory": "",
    }
    with pytest.raises(ValueError, match="player_name"):
        _replace_character_identity(aria, creation_data)


# ── start_succession_with_character requires pending_succession ────


def test_start_succession_without_pending_raises(aria: GameState) -> None:
    # Use a stub provider — should never be called on this path
    class _FailingProvider:
        def create_message(self, **_: Any) -> Any:  # noqa: ANN001
            raise AssertionError("AI must not be invoked when pending_succession is False")

    with pytest.raises(ValueError, match="pending_succession"):
        start_succession_with_character(_FailingProvider(), aria, {}, None)


def test_start_succession_pending_without_predecessor_raises(aria: GameState) -> None:
    # Forge a corrupt state: pending=True but no predecessors archived
    aria.campaign.pending_succession = True
    aria.campaign.predecessors = []

    class _FailingProvider:
        def create_message(self, **_: Any) -> Any:  # noqa: ANN001
            raise AssertionError("AI must not be invoked when archive is empty")

    with pytest.raises(ValueError, match="predecessors"):
        start_succession_with_character(_FailingProvider(), aria, {}, None)


# ── Succession serializer ──────────────────────────────────


def test_succession_summary_when_no_pending() -> None:
    from straightjacket.web.serializers import build_succession_summary

    g = make_game_state()
    summary = build_succession_summary(g)
    assert summary == {"pending": False}


def test_succession_summary_renders_narrative_text(aria: GameState) -> None:
    from straightjacket.web.serializers import build_succession_summary

    record = make_predecessor(
        player_name="Aria",
        end_reason="death",
        chapters_played=2,
        scenes_played=42,
        legacy_quests_filled_boxes=6,
        inheritance_rolls=[
            make_inheritance_roll(track_name="quests", result="STRONG_HIT", fraction=1.0, new_filled_boxes=6),
            make_inheritance_roll(track_name="bonds", result="WEAK_HIT", fraction=0.5, new_filled_boxes=1),
            make_inheritance_roll(track_name="discoveries", result="MISS", fraction=0.0, new_filled_boxes=0),
        ],
    )
    aria.campaign.pending_succession = True
    aria.campaign.predecessors = [record]

    summary = build_succession_summary(aria)
    assert summary["pending"] is True
    assert summary["title"]  # i18n filled
    assert "Aria" in summary["headline"]
    assert summary["predecessor"]["name"] == "Aria"
    assert "Aria" in summary["predecessor"]["history"]
    inh = {line["track"]: line["text"] for line in summary["inheritance"]}
    assert "live on in full" in inh["quests"]
    assert "carry forward in part" in inh["bonds"]
    assert "fade" in inh["discoveries"]
