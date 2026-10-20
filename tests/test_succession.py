from __future__ import annotations

import random
from typing import Any

import pytest

from straightjacket.engine.game.succession import (
    END_REASONS,
    prepare_succession,
    start_succession_with_character,
)
from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.models import CampaignState, GameState
from straightjacket.engine.ruleset.meters import starting_resources
from straightjacket.engine.ruleset.progress import filled_boxes, new_track
from straightjacket.engine.ruleset.succession import (
    apply_npc_carryover,
    build_predecessor_record,
    run_inheritance_rolls,
    seed_successor_legacy,
    threads_for_successor,
)
from tests._creation import OPENING_TEXT, OpeningProvider, TurnProvider, create_game, creation_data
from tests._helpers import (
    make_character_entry,
    make_game_state,
    make_inheritance_roll,
    make_npc,
    make_predecessor,
    make_progress_track,
    make_thread,
    make_threat,
)


@pytest.fixture
def aria(load_engine: None) -> GameState:
    g = create_game(
        "starforged",
        location="Hearthwood",
        npcs=[("Kira", "A hunter.", "friendly")],
        stats=(2, 2, 1, 1, 3),
        player_name="Aria",
        background_vow="avenge sister",
    )
    g.campaign.legacy["quests"].ticks = 24
    g.campaign.legacy["bonds"].ticks = 8
    g.campaign.legacy["discoveries"].ticks = 16
    g.narrative.scene_count = 42
    g.campaign.chapter_number = 2
    return g


def test_build_predecessor_captures_pre_roll_state(aria: GameState) -> None:
    record = build_predecessor_record(aria, "death")
    assert record.player_name == "Aria"
    assert record.pronouns == "she/her"
    assert record.background_vow == "avenge sister"
    assert record.setting_id == "starforged"
    assert record.chapters_played == 2
    assert record.scenes_played == 42
    assert record.end_reason == "death"
    assert record.legacy_filled_boxes["quests"] == 6
    assert record.legacy_filled_boxes["bonds"] == 2
    assert record.legacy_filled_boxes["discoveries"] == 4
    assert record.inheritance_rolls == []


def test_run_inheritance_rolls_returns_one_per_legacy_track(aria: GameState) -> None:
    rolls = run_inheritance_rolls(aria)
    track_names = {r.track_name for r in rolls}
    assert track_names == {"quests", "bonds", "discoveries"}


def test_run_inheritance_rolls_does_not_mutate_predecessor(aria: GameState) -> None:
    pre_quests = filled_boxes(aria.campaign.legacy["quests"])
    pre_bonds = filled_boxes(aria.campaign.legacy["bonds"])
    pre_disc = filled_boxes(aria.campaign.legacy["discoveries"])
    run_inheritance_rolls(aria)
    assert filled_boxes(aria.campaign.legacy["quests"]) == pre_quests
    assert filled_boxes(aria.campaign.legacy["bonds"]) == pre_bonds
    assert filled_boxes(aria.campaign.legacy["discoveries"]) == pre_disc


@pytest.mark.parametrize(
    ("ticks", "dice_values", "expected_result", "expected_new_filled"),
    [
        (32, [1], "STRONG_HIT", 8),
        (8, [10], "MISS", 0),
        (24, [4, 8], "WEAK_HIT", 3),
    ],
)
def test_run_inheritance_rolls_outcomes(
    ticks: int,
    dice_values: list[int],
    expected_result: str,
    expected_new_filled: int,
) -> None:
    g = make_game_state()
    g.campaign.legacy["quests"].ticks = ticks
    random.seed(0)

    import straightjacket.engine.ruleset.rolls as rolls_mod

    class _Dice:
        def __init__(self, values: list[int]) -> None:
            self.values = iter(values * 20)

        def randint(self, a: int, b: int) -> int:
            return next(self.values)

    real = rolls_mod.random
    rolls_mod.random = _Dice(dice_values)
    try:
        rolls = run_inheritance_rolls(g)
    finally:
        rolls_mod.random = real
    quests = next(r for r in rolls if r.track_name == "quests")
    assert quests.result == expected_result
    assert quests.new_filled_boxes == expected_new_filled


def test_seed_successor_legacy_overwrites_tracks(aria: GameState) -> None:
    rolls = [
        make_inheritance_roll(track_name="quests", new_filled_boxes=3),
        make_inheritance_roll(track_name="bonds", new_filled_boxes=0),
        make_inheritance_roll(track_name="discoveries", new_filled_boxes=8),
    ]
    seed_successor_legacy(aria, rolls)
    assert filled_boxes(aria.campaign.legacy["quests"]) == 3
    assert filled_boxes(aria.campaign.legacy["bonds"]) == 0
    assert filled_boxes(aria.campaign.legacy["discoveries"]) == 8


def test_seed_successor_legacy_resets_status(aria: GameState) -> None:
    aria.campaign.legacy["quests"].status = "completed"
    rolls = [
        make_inheritance_roll(track_name="quests", new_filled_boxes=3),
        make_inheritance_roll(track_name="bonds", new_filled_boxes=0),
        make_inheritance_roll(track_name="discoveries", new_filled_boxes=0),
    ]
    seed_successor_legacy(aria, rolls)
    assert aria.campaign.legacy["quests"].status == "active"


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


@pytest.mark.parametrize(
    ("status", "ticks", "expected_filled_boxes"),
    [
        ("active", 24, 6),
        ("background", 24, 3),
        ("lore", 20, 2),
    ],
)
def test_carryover_track_filled_boxes_per_status(status: str, ticks: int, expected_filled_boxes: int) -> None:
    npc = make_npc(id="npc_1", name="NPC", status=status)
    track = make_progress_track(
        id="connection_npc_1", name="NPC", track_type="connection", rank="dangerous", ticks=ticks
    )
    kept_npcs, kept_tracks = apply_npc_carryover([npc], [track])
    assert len(kept_npcs) == 1
    assert filled_boxes(kept_tracks[0]) == expected_filled_boxes


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
    npc.status = "weird"
    with pytest.raises(ValueError, match=r"no succession\.npc_carryover rule"):
        apply_npc_carryover([npc], [])


def test_carryover_preserves_track_name_and_rank() -> None:
    npc = make_npc(id="npc_1", name="Mira", status="active")
    track = make_progress_track(
        id="connection_npc_1", name="Mira Whisperer", track_type="connection", rank="formidable", ticks=16
    )
    _, kept_tracks = apply_npc_carryover([npc], [track])
    assert kept_tracks[0].name == "Mira Whisperer"
    assert kept_tracks[0].rank == "formidable"


def test_carryover_keeps_only_the_connections_of_every_track_it_is_given() -> None:
    npc = make_npc(id="npc_1", name="Mira", status="active")
    connection = make_progress_track(
        id="connection_npc_1", name="Mira", track_type="connection", rank="dangerous", ticks=8
    )
    vow = make_progress_track(id="vow_find_mira", name="Find Mira", track_type="vow", rank="dangerous", ticks=8)
    _, kept_tracks = apply_npc_carryover([npc], [vow, connection])
    assert [t.id for t in kept_tracks] == ["connection_npc_1"]


def test_filter_drops_vow_threads() -> None:
    threads = [
        make_thread(id="t1", name="Avenge sister", thread_type="vow", source="creation"),
        make_thread(id="t2", name="Find ally", thread_type="vow", source="vow"),
    ]
    kept = threads_for_successor(threads)
    assert kept == []


def test_filter_drops_creation_threads_regardless_of_type() -> None:
    threads = [
        make_thread(id="t1", name="Old fear", thread_type="tension", source="creation"),
        make_thread(id="t2", name="Faction war", thread_type="subplot", source="director"),
        make_thread(id="t3", name="Rumor", thread_type="goal", source="event"),
    ]
    kept = threads_for_successor(threads)
    kept_ids = {t.id for t in kept}
    assert kept_ids == {"t2", "t3"}


def test_a_successor_starts_without_the_old_adventures_and_clocks_keyed_scenes(aria: GameState) -> None:
    from straightjacket.engine.gamemaster.keyed_scenes import add_keyed_scene

    aria.narrative.keyed_scenes = []
    for source in ("ac:Old Plot Point", "clock:The flood rises:2", "random_event:pc_negative:npc_1"):
        add_keyed_scene(
            aria.narrative, trigger_type="scene_count", trigger_value="99", priority=1, narrative_hint="", source=source
        )
    aria.end_reason = "death"
    prepare_succession(aria)
    successor = creation_data("starforged", stats=(3, 2, 2, 1, 1), player_name="Ayla", background_vow="Find Aria")

    start_succession_with_character(OpeningProvider([], "Ring Dock"), aria, successor)

    sources = {ks.source for ks in aria.narrative.keyed_scenes}
    assert not sources & {"ac:Old Plot Point", "clock:The flood rises:2"}
    assert "random_event:pc_negative:npc_1" in sources


def test_prepare_succession_archives_and_sets_flag(aria: GameState) -> None:
    aria.end_reason = "death"
    prepare_succession(aria)
    assert aria.campaign.pending_succession is True
    assert len(aria.campaign.predecessors[-1].inheritance_rolls) == 3


def test_prepare_succession_rejects_unknown_reason(aria: GameState) -> None:
    aria.end_reason = "exhaustion"
    with pytest.raises(ValueError, match="end_reason"):
        prepare_succession(aria)


def test_prepare_succession_rejects_double_call(aria: GameState) -> None:
    aria.end_reason = "death"
    prepare_succession(aria)
    with pytest.raises(ValueError, match="pending_succession"):
        prepare_succession(aria)


def test_prepare_succession_archives_the_recorded_reason(aria: GameState) -> None:
    for reason in END_REASONS:
        g = make_game_state(setting_id="starforged")
        g.campaign.legacy["quests"].ticks = 4
        g.end_reason = reason
        prepare_succession(g)
        assert g.campaign.predecessors[-1].end_reason == reason


@pytest.mark.parametrize(
    ("move", "reason"),
    [
        ("threshold/face_death", "death"),
        ("threshold/face_desolation", "despair"),
        ("suffer/face_death", "death"),
        ("suffer/face_desolation", "despair"),
    ],
)
def test_a_miss_at_the_threshold_records_why_the_game_ended(load_engine: None, move: str, reason: str) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome

    g = make_game_state(setting_id="classic" if move.startswith("suffer/") else "starforged")
    g.resources.meters["health"], g.resources.meters["spirit"] = 0, 0
    resolve_move_outcome(g, move, "MISS", target_npc_id=None, match=False)
    assert (g.game_over, g.end_reason) == (True, reason)


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


def _successor(**changes: Any) -> dict[str, Any]:
    return {
        **creation_data("classic", stats=(3, 2, 2, 1, 1), player_name="Bryn", background_vow="carry on the work"),
        **changes,
    }


def _succeed(game: GameState, creation: dict[str, Any]) -> str:
    game.end_reason = "death"
    prepare_succession(game)
    provider = OpeningProvider([("Mara Voss", "A ferrywoman.", "neutral")], "Memorial")
    return start_succession_with_character(provider, game, creation)


def test_a_successor_takes_up_a_fresh_character_in_the_same_world(aria: GameState) -> None:
    aria.impacts = ["wounded", "shaken"]
    aria.resources.meters["health"] = 1
    aria.resources.meters["spirit"] = 0
    aria.crisis_mode = True
    aria.threats = [make_threat(id="thr_1", name="Faction war")]
    aria.progress_tracks.append(new_track(id="combat_raid", name="Raid", track_type="combat", rank="dangerous"))
    aria.world.combat_position = "bad_spot"
    aria.last_turn_snapshot = aria.snapshot()
    old_clocks = {c.name for c in aria.world.clocks}

    assert _succeed(aria, _successor()) == OPENING_TEXT

    assert aria.player_name == "Bryn"
    assert aria.campaign.pending_succession is False
    assert (aria.impacts, aria.assets) == ([], [])
    assert aria.resources == starting_resources(aria.setting_id)
    assert not old_clocks & {c.name for c in aria.world.clocks}
    assert [t.id for t in aria.progress_tracks] == ["vow_background"]
    assert aria.world.combat_position == ""
    assert (aria.narrative.scene_count, aria.crisis_mode, aria.game_over) == (1, False, False)
    assert "thr_1" in [t.id for t in aria.threats]
    assert aria.last_turn_snapshot is None
    assert [e.result for e in aria.narrative.session_log] == ["opening"]


def test_a_successors_characters_list_holds_only_who_is_still_there(aria: GameState) -> None:
    aria.narrative.characters_list.append(
        make_character_entry(id="char_vow_subject", name="Sister", entry_type="abstract", weight=2)
    )
    _succeed(aria, _successor())
    npc_ids = {n.id for n in aria.npcs}
    assert all(entry.id in npc_ids for entry in aria.narrative.characters_list)


@pytest.mark.parametrize("missing", ["player_name", "pronouns", "background_vow", "paths", "backstory"])
def test_a_successor_without_a_field_of_its_creation_raises(aria: GameState, missing: str) -> None:
    creation = {k: v for k, v in _successor().items() if k != missing}
    with pytest.raises(KeyError, match=missing):
        _succeed(aria, creation)


@pytest.mark.parametrize("empty_field", ["background_vow", "player_name"])
def test_a_successor_with_an_empty_name_or_vow_raises(aria: GameState, empty_field: str) -> None:
    with pytest.raises(ValueError, match=empty_field):
        _succeed(aria, _successor(**{empty_field: ""}))


def test_start_succession_without_pending_raises(aria: GameState) -> None:
    provider = TurnProvider()
    with pytest.raises(ValueError, match="pending_succession"):
        start_succession_with_character(provider, aria, {})
    assert provider.calls == []


def test_start_succession_pending_without_predecessor_raises(aria: GameState) -> None:
    aria.campaign.pending_succession = True
    aria.campaign.predecessors = []

    provider = TurnProvider()
    with pytest.raises(ValueError, match="predecessors"):
        start_succession_with_character(provider, aria, {})
    assert provider.calls == []


def test_succession_summary_renders_narrative_text(aria: GameState) -> None:
    from straightjacket.web.serializers import build_succession_summary

    record = make_predecessor(
        player_name="Aria",
        end_reason="death",
        chapters_played=2,
        scenes_played=42,
        legacy_filled_boxes={"quests": 6, "bonds": 2, "discoveries": 0},
        inheritance_rolls=[
            make_inheritance_roll(track_name="quests", result="STRONG_HIT", new_filled_boxes=6),
            make_inheritance_roll(track_name="bonds", result="WEAK_HIT", new_filled_boxes=1),
            make_inheritance_roll(track_name="discoveries", result="MISS", new_filled_boxes=0),
        ],
    )
    aria.campaign.pending_succession = True
    aria.campaign.predecessors = [record]

    summary = build_succession_summary(aria)
    assert summary["title"]
    assert "Aria" in summary["headline"]
    assert "Aria" in summary["history"]
    quests, bonds, discoveries = summary["inheritance"]
    assert "live on in full" in quests
    assert "quests" in quests
    assert "carry forward in part" in bonds
    assert "fade" in discoveries
    assert set(summary) == {"title", "headline", "history", "inheritance"}


def test_a_successors_opening_registers_its_people_at_the_engines_time(aria: GameState) -> None:
    aria.npcs = []
    _succeed(aria, _successor())
    assert [n.name for n in aria.npcs] == ["Mara Voss"]
    assert aria.world.current_location == "Memorial"
    assert aria.world.time_of_day == gm().opening.time_of_day


def test_a_successors_opening_registers_its_people_and_place_beside_the_npcs_who_stay(aria: GameState) -> None:
    [kira] = aria.npcs
    assert kira.introduced
    _succeed(aria, _successor())
    assert [n.name for n in aria.npcs] == ["Kira", "Mara Voss"]
    assert aria.world.current_location == "Memorial"
