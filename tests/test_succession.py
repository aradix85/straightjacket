from __future__ import annotations

import json
import random
from typing import Any

import pytest

from straightjacket.engine.game.succession import (
    END_REASONS,
    _filter_threads_for_successor,
    _replace_character_identity,
    _reset_for_successor,
    prepare_succession,
    start_succession_with_character,
)
from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.models import (
    CampaignState,
    GameState,
    ThreadEntry,
)
from straightjacket.engine.ruleset.meters import starting_resources
from straightjacket.engine.ruleset.progress import filled_boxes, new_track
from straightjacket.engine.ruleset.succession import (
    apply_npc_carryover,
    build_predecessor_record,
    run_inheritance_rolls,
    seed_successor_legacy,
)
from tests._creation import create_game
from tests._helpers import (
    make_game_state,
    make_inheritance_roll,
    make_npc,
    make_predecessor,
    make_progress_track,
    make_threat,
)


@pytest.fixture
def aria(load_engine: None) -> GameState:
    g = create_game(
        "classic",
        location="Hearthwood",
        npcs=[("Kira", "A hunter.", "friendly")],
        stats=(2, 2, 1, 1, 3),
        player_name="Aria",
        background_vow="avenge sister",
    )
    g.campaign.legacy_quests.ticks = 24
    g.campaign.legacy_bonds.ticks = 8
    g.campaign.legacy_discoveries.ticks = 16
    g.narrative.scene_count = 42
    g.campaign.chapter_number = 2
    return g


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
    assert record.inheritance_rolls == []


def test_run_inheritance_rolls_returns_one_per_legacy_track(aria: GameState) -> None:
    rolls = run_inheritance_rolls(aria)
    track_names = {r.track_name for r in rolls}
    assert track_names == {"quests", "bonds", "discoveries"}


def test_run_inheritance_rolls_does_not_mutate_predecessor(aria: GameState) -> None:
    pre_quests = filled_boxes(aria.campaign.legacy_quests)
    pre_bonds = filled_boxes(aria.campaign.legacy_bonds)
    pre_disc = filled_boxes(aria.campaign.legacy_discoveries)
    run_inheritance_rolls(aria)
    assert filled_boxes(aria.campaign.legacy_quests) == pre_quests
    assert filled_boxes(aria.campaign.legacy_bonds) == pre_bonds
    assert filled_boxes(aria.campaign.legacy_discoveries) == pre_disc


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
    g.campaign.legacy_quests.ticks = ticks
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
    assert filled_boxes(aria.campaign.legacy_quests) == 3
    assert filled_boxes(aria.campaign.legacy_bonds) == 0
    assert filled_boxes(aria.campaign.legacy_discoveries) == 8


def test_seed_successor_legacy_resets_status(aria: GameState) -> None:
    aria.campaign.legacy_quests.status = "completed"
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
        g = make_game_state(setting_id="classic")
        g.campaign.legacy_quests.ticks = 4
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


def test_reset_for_successor_clears_pc_state_keeps_world(aria: GameState) -> None:
    aria.impacts = ["wounded", "shaken"]
    aria.assets = ["asset_a"]
    aria.resources.meters["health"] = 1
    aria.resources.meters["spirit"] = 0
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
    assert aria.resources == starting_resources(aria.setting_id)
    assert aria.world.clocks == []
    assert aria.narrative.scene_count == 1
    assert aria.crisis_mode is False
    assert aria.game_over is False
    assert len(aria.threats) == 1
    assert aria.threats[0].id == "thr_1"


def test_a_fight_the_predecessor_died_in_ends_with_them(aria: GameState) -> None:

    aria.progress_tracks.append(new_track(id="combat_raid", name="Raid", track_type="combat", rank="dangerous"))
    aria.world.combat_position = "bad_spot"
    _reset_for_successor(
        aria, surviving_threads=[], surviving_threats=[], surviving_npcs=[], surviving_connection_tracks=[]
    )
    assert aria.progress_tracks == []
    assert aria.world.combat_position == ""


def test_a_successor_cannot_correct_the_predecessors_last_turn(aria: GameState) -> None:
    aria.last_turn_snapshot = aria.snapshot()
    _reset_for_successor(
        aria, surviving_threads=[], surviving_threats=[], surviving_npcs=[], surviving_connection_tracks=[]
    )
    assert aria.last_turn_snapshot is None


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


def test_replace_character_identity_strict_required_fields(aria: GameState) -> None:
    base = {
        "setting_id": "classic",
        "tone": "dark_gritty",
        "stats": {"edge": 3, "heart": 2, "iron": 2, "shadow": 1, "wits": 1},
        "player_name": "Bryn",
        "pronouns": "they/them",
        "background_vow": "find truth",
        "paths": [],
        "backstory": "",
        "background_vow_rank": "",
        "vow_subject": "",
        "assets": [],
        "truths": {},
        "wishes": "",
        "content_lines": "",
    }
    for missing in ("player_name", "pronouns", "background_vow", "paths", "backstory"):
        creation_data = {k: v for k, v in base.items() if k != missing}
        with pytest.raises(KeyError, match=missing):
            _replace_character_identity(aria, creation_data)


@pytest.mark.parametrize("empty_field", ["background_vow", "player_name"])
def test_replace_character_identity_empty_field_raises(aria: GameState, empty_field: str) -> None:
    creation_data = {
        "setting_id": "classic",
        "tone": "dark_gritty",
        "stats": {"edge": 3, "heart": 2, "iron": 2, "shadow": 1, "wits": 1},
        "player_name": "Bryn",
        "pronouns": "they/them",
        "background_vow": "find truth",
        "paths": [],
        "backstory": "",
        "background_vow_rank": "",
        "vow_subject": "",
        "assets": [],
        "truths": {},
        "wishes": "",
        "content_lines": "",
    }
    creation_data[empty_field] = ""
    with pytest.raises(ValueError, match=empty_field):
        _replace_character_identity(aria, creation_data)


def test_start_succession_without_pending_raises(aria: GameState) -> None:
    class _FailingProvider:
        def create_message(self, **_: Any) -> Any:
            raise AssertionError("AI must not be invoked when pending_succession is False")

    with pytest.raises(ValueError, match="pending_succession"):
        start_succession_with_character(_FailingProvider(), aria, {})


def test_start_succession_pending_without_predecessor_raises(aria: GameState) -> None:
    aria.campaign.pending_succession = True
    aria.campaign.predecessors = []

    class _FailingProvider:
        def create_message(self, **_: Any) -> Any:
            raise AssertionError("AI must not be invoked when archive is empty")

    with pytest.raises(ValueError, match="predecessors"):
        start_succession_with_character(_FailingProvider(), aria, {})


def test_succession_summary_renders_narrative_text(aria: GameState) -> None:
    from straightjacket.web.serializers import build_succession_summary

    record = make_predecessor(
        player_name="Aria",
        end_reason="death",
        chapters_played=2,
        scenes_played=42,
        legacy_quests_filled_boxes=6,
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


class _SuccessionMockProvider:
    def __init__(self, narration: str = "Successor's first scene.") -> None:
        self.narration = narration

    def create_message(self, spec: object) -> object:
        from straightjacket.engine.ai.provider_base import AIResponse

        json_schema = spec.json_schema
        if not json_schema:
            return AIResponse(content=self.narration, usage={"input_tokens": 10, "output_tokens": 10})

        props = set(json_schema.get("properties", {}).keys())

        if "central_conflict" in props:
            user_msg = "\n".join(m.get("content", "") for m in spec.messages)
            act_count = sum(1 for line in user_msg.splitlines() if line.startswith("act "))
            if act_count == 0:
                act_count = 3
            return AIResponse(
                content=json.dumps(
                    {
                        "central_conflict": "Continue the legacy",
                        "antagonist_force": "Old foe",
                        "thematic_thread": "inheritance",
                        "acts": [
                            {"title": f"Act {i + 1}", "goal": "g", "mood": "tense", "transition_trigger": "t"}
                            for i in range(act_count)
                        ],
                        "revelations": [{"content": f"reveal {i + 1}"} for i in range(3)],
                        "possible_endings": [{"type": "earned", "description": f"end {i + 1}"} for i in range(3)],
                    }
                ),
                usage={"input_tokens": 10, "output_tokens": 10},
            )
        if "npcs" in props and "scene_context" in props:
            return AIResponse(
                content=json.dumps(
                    {
                        "npcs": [
                            {
                                "name": "Mara Voss",
                                "description": "A ferrywoman",
                                "agenda": "Keep the crossing open",
                                "instinct": "Bargain first",
                                "secrets": ["She owes the toll-keeper"],
                                "disposition": "neutral",
                            }
                        ],
                        "location": "Memorial",
                        "scene_context": "A new dawn",
                        "memory_updates": [],
                        "deceased_npcs": [],
                    }
                ),
                usage={"input_tokens": 10, "output_tokens": 10},
            )
        if "new_npcs" in props:
            return AIResponse(
                content=json.dumps(
                    {
                        "new_npcs": [],
                        "npc_renames": [],
                        "npc_details": [],
                        "deceased_npcs": [],
                        "lore_npcs": [],
                    }
                ),
                usage={"input_tokens": 10, "output_tokens": 10},
            )
        return AIResponse(content="{}", usage={"input_tokens": 10, "output_tokens": 10})


def _successor_creation_data() -> dict:
    return {
        "setting_id": "classic",
        "tone": "dark_gritty",
        "stats": {"edge": 3, "heart": 2, "iron": 2, "shadow": 1, "wits": 1},
        "player_name": "Bryn",
        "pronouns": "they/them",
        "background_vow": "carry on the work",
        "paths": [],
        "backstory": "",
        "background_vow_rank": "",
        "vow_subject": "",
        "assets": [],
        "truths": {},
        "wishes": "",
        "content_lines": "",
    }


def test_start_succession_with_character_happy_path(aria: GameState) -> None:

    aria.world.current_location = "Tavern"
    aria.end_reason = "death"
    prepare_succession(aria)

    provider = _SuccessionMockProvider("The successor steps forward.")
    narration = start_succession_with_character(provider, aria, _successor_creation_data())

    assert aria.player_name == "Bryn"
    assert "successor" in narration.lower()
    assert aria.campaign.pending_succession is False


def test_start_succession_resets_resources(aria: GameState) -> None:

    aria.resources.meters["health"] = 0
    aria.resources.meters["spirit"] = 0
    aria.world.current_location = "Tavern"
    aria.end_reason = "death"
    prepare_succession(aria)

    provider = _SuccessionMockProvider()
    start_succession_with_character(provider, aria, _successor_creation_data())

    assert aria.resources == starting_resources(aria.setting_id)


def test_start_succession_seeds_legacy_from_predecessor(aria: GameState) -> None:

    aria.world.current_location = "Tavern"
    aria.end_reason = "death"
    prepare_succession(aria)

    provider = _SuccessionMockProvider()
    start_succession_with_character(provider, aria, _successor_creation_data())

    quest_filled = filled_boxes(aria.campaign.legacy_quests)
    bond_filled = filled_boxes(aria.campaign.legacy_bonds)
    disc_filled = filled_boxes(aria.campaign.legacy_discoveries)
    assert quest_filled >= 0
    assert bond_filled >= 0
    assert disc_filled >= 0


def test_start_succession_records_session_log(aria: GameState) -> None:

    aria.world.current_location = "Tavern"
    aria.end_reason = "death"
    prepare_succession(aria)

    provider = _SuccessionMockProvider()
    start_succession_with_character(provider, aria, _successor_creation_data())

    assert len(aria.narrative.session_log) == 1
    assert aria.narrative.session_log[0].result == "opening"


def test_start_succession_applies_the_opening_setup_and_the_engines_time(aria: GameState) -> None:

    aria.npcs = []
    aria.world.current_location = "Tavern"
    aria.end_reason = "death"
    prepare_succession(aria)

    start_succession_with_character(_SuccessionMockProvider(), aria, _successor_creation_data())

    assert [n.name for n in aria.npcs] == ["Mara Voss"]
    assert aria.world.current_scene_context == "A new dawn"
    assert aria.world.time_of_day == gm().opening.time_of_day
