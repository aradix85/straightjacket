from __future__ import annotations

import json
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


@pytest.fixture
def aria(load_engine: None) -> GameState:
    g = make_game_state(
        player_name="Aria",
        pronouns="she/her",
        character_concept="outlander, deepwoods",
        background_vow="avenge sister",
        setting_id="classic",
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


@pytest.mark.parametrize(
    "ticks, dice_values, expected_result, expected_fraction, expected_new_filled",
    [
        (32, [1], "STRONG_HIT", 1.0, 8),
        (8, [10], "MISS", 0.0, 0),
        (24, [4, 8], "WEAK_HIT", 0.5, 3),
    ],
)
def test_run_inheritance_rolls_outcomes(
    ticks: int,
    dice_values: list[int],
    expected_result: str,
    expected_fraction: float,
    expected_new_filled: int,
) -> None:
    g = make_game_state()
    g.campaign.legacy_quests.ticks = ticks
    random.seed(0)

    import straightjacket.engine.mechanics.consequences as cons_mod

    class _Dice:
        def __init__(self, values: list[int]) -> None:
            self.values = iter(values * 20)

        def randint(self, a: int, b: int) -> int:
            return next(self.values)

    real = cons_mod.random
    cons_mod.random = _Dice(dice_values)
    try:
        rolls = run_inheritance_rolls(g)
    finally:
        cons_mod.random = real
    quests = next(r for r in rolls if r.track_name == "quests")
    assert quests.result == expected_result
    assert quests.fraction == expected_fraction
    assert quests.new_filled_boxes == expected_new_filled


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
    "status, ticks, expected_filled_boxes",
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
    assert kept_tracks[0].filled_boxes == expected_filled_boxes


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


@pytest.mark.parametrize(
    "health, spirit, expected_reason",
    [
        (0, 3, "death"),
        (3, 0, "despair"),
        (0, 0, "death"),
        (3, 3, "death"),
    ],
)
def test_determine_end_reason(health: int, spirit: int, expected_reason: str) -> None:
    g = make_game_state()
    g.resources.health = health
    g.resources.spirit = spirit
    assert determine_end_reason(g) == expected_reason


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
    assert len(aria.threats) == 1
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


def test_replace_character_identity_strict_required_fields(aria: GameState) -> None:
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


@pytest.mark.parametrize("empty_field", ["background_vow", "player_name"])
def test_replace_character_identity_empty_field_raises(aria: GameState, empty_field: str) -> None:
    creation_data = {
        "setting_id": "classic",
        "stats": {"edge": 3, "heart": 2, "iron": 2, "shadow": 1, "wits": 1},
        "player_name": "Bryn",
        "pronouns": "they/them",
        "background_vow": "find truth",
        "paths": [],
        "backstory": "",
    }
    creation_data[empty_field] = ""
    with pytest.raises(ValueError, match=empty_field):
        _replace_character_identity(aria, creation_data)


def test_start_succession_without_pending_raises(aria: GameState) -> None:
    class _FailingProvider:
        def create_message(self, **_: Any) -> Any:
            raise AssertionError("AI must not be invoked when pending_succession is False")

    with pytest.raises(ValueError, match="pending_succession"):
        start_succession_with_character(_FailingProvider(), aria, {}, None)


def test_start_succession_pending_without_predecessor_raises(aria: GameState) -> None:
    aria.campaign.pending_succession = True
    aria.campaign.predecessors = []

    class _FailingProvider:
        def create_message(self, **_: Any) -> Any:
            raise AssertionError("AI must not be invoked when archive is empty")

    with pytest.raises(ValueError, match="predecessors"):
        start_succession_with_character(_FailingProvider(), aria, {}, None)


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
    assert summary["title"]
    assert "Aria" in summary["headline"]
    assert summary["predecessor"]["name"] == "Aria"
    assert "Aria" in summary["predecessor"]["history"]
    inh = {line["track"]: line["text"] for line in summary["inheritance"]}
    assert "live on in full" in inh["quests"]
    assert "carry forward in part" in inh["bonds"]
    assert "fade" in inh["discoveries"]


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
            return AIResponse(
                content=json.dumps(
                    {
                        "central_conflict": "Continue the legacy",
                        "antagonist_force": "Old foe",
                        "thematic_thread": "inheritance",
                        "acts": [
                            {"phase": "setup", "title": "Begin", "goal": "g", "mood": "tense", "scene_range": [1, 5]}
                        ],
                        "revelations": [],
                        "possible_endings": [],
                    }
                ),
                usage={"input_tokens": 10, "output_tokens": 10},
            )
        if "fixed_conflict" in props:
            return AIResponse(
                content=json.dumps({"pass": True, "violations": [], "fixed_conflict": "", "fixed_antagonist": ""}),
                usage={"input_tokens": 10, "output_tokens": 10},
            )
        if "pass" in props and "violations" in props:
            return AIResponse(
                content=json.dumps({"pass": True, "violations": [], "correction": ""}),
                usage={"input_tokens": 10, "output_tokens": 10},
            )
        if "title" in props and "summary" in props and "unresolved_threads" in props:
            return AIResponse(
                content=json.dumps(
                    {
                        "title": "Last Chapter",
                        "summary": "End of Aria's journey",
                        "unresolved_threads": ["the relic"],
                        "character_growth": "endured",
                        "npc_evolutions": [],
                        "thematic_question": "?",
                        "post_story_location": "Memorial",
                    }
                ),
                usage={"input_tokens": 10, "output_tokens": 10},
            )
        if "npcs" in props and "clocks" in props:
            return AIResponse(
                content=json.dumps(
                    {
                        "npcs": [],
                        "clocks": [],
                        "location": "Memorial",
                        "scene_context": "A new dawn",
                        "time_of_day": "morning",
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
        "stats": {"edge": 3, "heart": 2, "iron": 2, "shadow": 1, "wits": 1},
        "player_name": "Bryn",
        "pronouns": "they/them",
        "background_vow": "carry on the work",
        "paths": [],
        "backstory": "",
    }


def test_start_succession_with_character_happy_path(aria: GameState) -> None:
    from straightjacket.engine.db.connection import close_db, reset_db

    aria.world.current_location = "Tavern"
    prepare_succession(aria, "death")

    reset_db()
    provider = _SuccessionMockProvider("The successor steps forward.")
    try:
        game, narration = start_succession_with_character(provider, aria, _successor_creation_data())
    finally:
        close_db()

    assert game.player_name == "Bryn"
    assert "successor" in narration.lower()
    assert game.campaign.pending_succession is False


def test_start_succession_resets_resources(aria: GameState) -> None:
    from straightjacket.engine.db.connection import close_db, reset_db
    from straightjacket.engine.engine_loader import eng

    aria.resources.health = 0
    aria.resources.spirit = 0
    aria.world.current_location = "Tavern"
    prepare_succession(aria, "death")

    reset_db()
    provider = _SuccessionMockProvider()
    try:
        game, _ = start_succession_with_character(provider, aria, _successor_creation_data())
    finally:
        close_db()

    assert game.resources.health == eng().resources.health_start
    assert game.resources.spirit == eng().resources.spirit_start


def test_start_succession_seeds_legacy_from_predecessor(aria: GameState) -> None:
    from straightjacket.engine.db.connection import close_db, reset_db

    aria.world.current_location = "Tavern"
    prepare_succession(aria, "death")

    reset_db()
    provider = _SuccessionMockProvider()
    try:
        game, _ = start_succession_with_character(provider, aria, _successor_creation_data())
    finally:
        close_db()

    quest_filled = game.campaign.legacy_quests.filled_boxes
    bond_filled = game.campaign.legacy_bonds.filled_boxes
    disc_filled = game.campaign.legacy_discoveries.filled_boxes
    assert quest_filled >= 0
    assert bond_filled >= 0
    assert disc_filled >= 0


def test_start_succession_records_session_log(aria: GameState) -> None:
    from straightjacket.engine.db.connection import close_db, reset_db

    aria.world.current_location = "Tavern"
    prepare_succession(aria, "death")

    reset_db()
    provider = _SuccessionMockProvider()
    try:
        game, _ = start_succession_with_character(provider, aria, _successor_creation_data())
    finally:
        close_db()

    assert len(game.narrative.session_log) == 1
    assert game.narrative.session_log[0].result == "opening"
