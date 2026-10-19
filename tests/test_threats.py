import pytest

from straightjacket.engine.models import GameState, Resources, ThreatData, labels_of
from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.progress import advance_menace, menace_boxes, menace_per_mark
from tests._helpers import (
    make_game_state,
    make_outcome,
    make_progress_track,
    make_thread,
    make_threat,
    make_world_state,
)


def _game_with_threat() -> GameState:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    g.resources = Resources(meters={"health": 5, "spirit": 5, "supply": 5, "momentum": 2}, next_move_bonus=0)
    g.world = make_world_state(current_location="Iron Hold")
    vow = make_progress_track(id="vow_hunt", name="Hunt the beast", track_type="vow", rank="dangerous", ticks=8)
    g.progress_tracks.append(vow)
    threat = make_threat(
        id="threat_beast",
        name="The Beast Awakens",
        category="rampaging_creature",
        description="A massive predator stalking the region",
        linked_vow_id="vow_hunt",
        rank="dangerous",
    )
    g.threats.append(threat)
    return g


class TestThreatData:
    def test_menace_per_mark_dangerous(self) -> None:
        t = make_threat(rank="dangerous")
        assert menace_per_mark(t) == 8

    def test_menace_per_mark_epic(self) -> None:
        t = make_threat(rank="epic")
        assert menace_per_mark(t) == 1

    def test_advance_menace(self) -> None:
        t = make_threat(rank="dangerous", menace_ticks=0)
        added = advance_menace(t, 1)
        assert added == 8
        assert t.menace_ticks == 8
        assert menace_boxes(t) == 2

    def test_advance_menace_clamped(self) -> None:
        t = make_threat(rank="dangerous", menace_ticks=36)
        added = advance_menace(t, 1)
        assert added == 4
        assert t.menace_ticks == 40
        assert t.menace_full

    def test_menace_full_property(self) -> None:
        t = make_threat(menace_ticks=40)
        assert t.menace_full
        t2 = make_threat(menace_ticks=39)
        assert not t2.menace_full

    def test_serialization_round_trip(self) -> None:
        t = make_threat(
            id="t1",
            name="Plague",
            category="malignant_plague",
            linked_vow_id="v1",
            rank="formidable",
            menace_ticks=12,
        )
        d = t.to_dict()
        t2 = ThreatData.from_dict(d)
        assert t2.id == "t1"
        assert t2.menace_ticks == 12
        assert t2.rank == "formidable"
        assert menace_per_mark(t2) == 4


class TestThreatSnapshotRestore:
    def test_threats_restored_on_snapshot(self) -> None:
        game = _game_with_threat()
        snap = game.snapshot()

        advance_menace(game.threats[0], 2)
        game.threats.append(make_threat(id="t2", name="New Threat"))
        assert game.threats[0].menace_ticks == 16
        assert len(game.threats) == 2

        game.restore(snap)
        assert len(game.threats) == 1
        assert game.threats[0].menace_ticks == 0
        assert game.threats[0].name == "The Beast Awakens"

    def test_to_dict_from_dict_round_trip(self) -> None:
        game = _game_with_threat()
        advance_menace(game.threats[0], 1)
        d = game.to_dict()
        game2 = GameState.from_dict(d)
        assert len(game2.threats) == 1
        assert game2.threats[0].menace_ticks == 8
        assert game2.threats[0].linked_vow_id == "vow_hunt"


class TestMenaceOnMiss:
    def test_advance_on_miss(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.threats import advance_menace_on_miss

        game = _game_with_threat()
        events = advance_menace_on_miss(game)
        assert len(events) == 1
        assert events[0].threat_name == "The Beast Awakens"
        assert game.threats[0].menace_ticks == 8

    def test_no_advance_when_vow_completed(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.threats import advance_menace_on_miss

        game = _game_with_threat()
        game.progress_tracks[0].status = "completed"
        events = advance_menace_on_miss(game)
        assert events == []
        assert game.threats[0].menace_ticks == 0

    def test_no_advance_when_threat_resolved(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.threats import advance_menace_on_miss

        game = _game_with_threat()
        game.threats[0].status = "resolved"
        events = advance_menace_on_miss(game)
        assert events == []

    def test_menace_full_event(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.threats import advance_menace_on_miss

        game = _game_with_threat()
        game.threats[0].menace_ticks = 36
        events = advance_menace_on_miss(game)
        assert len(events) == 1
        assert events[0].menace_full
        assert game.threats[0].menace_full


class TestAdvanceById:
    def test_advance_specific_threat(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.threats import advance_threat_by_id

        game = _game_with_threat()
        advance_threat_by_id(game, "threat_beast")
        assert game.threats[0].menace_ticks == 8

    def test_a_random_event_marks_the_configured_menace(
        self, stub_engine: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from straightjacket.engine.ruleset.threats import advance_threat_by_id

        monkeypatch.setattr(rules().threats, "menace_on_random_event", 2)
        game = _game_with_threat()
        advance_threat_by_id(game, "threat_beast")
        assert game.threats[0].menace_ticks == 16

    def test_advance_nonexistent_changes_nothing(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.threats import advance_threat_by_id

        game = _game_with_threat()
        advance_threat_by_id(game, "nonexistent")
        assert game.threats[0].menace_ticks == 0


class TestAdvancesReachTheNarrator:
    def test_an_autonomous_tick_waits_for_the_next_turn_as_off_screen(
        self, load_engine: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from straightjacket.engine.prompt_shared import _threat_events_block
        from straightjacket.engine.ruleset import threats

        monkeypatch.setattr(threats.random, "random", lambda: 0.0)
        game = _game_with_threat()
        threats.tick_autonomous_threats(game)
        [event] = game.world.pending_threat_events
        assert (event.source, event.threat_name) == ("autonomous", "The Beast Awakens")
        assert threats.take_pending_threat_events(game) == [event]
        assert game.world.pending_threat_events == []
        assert '<threat_advance name="The Beast Awakens" menace_full="False" offscreen="true"/>' in (
            _threat_events_block([event])
        )

    def test_a_random_event_advance_is_told_in_its_own_turn(self, load_engine: None) -> None:
        from straightjacket.engine.prompt_shared import _threat_events_block
        from straightjacket.engine.ruleset.threats import advance_threat_by_id, take_pending_threat_events

        game = _game_with_threat()
        advance_threat_by_id(game, "threat_beast")
        [event] = take_pending_threat_events(game)
        assert event.source == "random_event"
        assert "offscreen" not in _threat_events_block([event])

    def test_delve_tells_what_the_threat_does_from_its_category(self, load_engine: None) -> None:
        from straightjacket.engine.prompt_shared import _threat_events_block
        from straightjacket.engine.ruleset.threats import advance_menace_on_miss
        from straightjacket.engine.setting.packages import load_package

        rows = {row.text for row in load_package("delve").oracle_table("threat/rampaging_creature").rows}
        game = _game_with_threat()
        game.setting_id = "delve"
        [event] = advance_menace_on_miss(game)
        assert event.development in rows
        assert f">{event.development}</threat_advance>" in _threat_events_block([event])
        game.setting_id = "starforged"
        game.threats[0].menace_ticks = 0
        assert advance_menace_on_miss(game)[0].development == ""


class TestThreatsStatus:
    def test_active_threats_shown(self, load_engine: None) -> None:
        from straightjacket.web.serializers import build_threats_status

        game = _game_with_threat()
        text = build_threats_status(game)
        assert "Beast Awakens" in text
        assert "distant" in text

    def test_high_menace_shown(self, load_engine: None) -> None:
        from straightjacket.web.serializers import build_threats_status

        game = _game_with_threat()
        game.threats[0].menace_ticks = 36
        text = build_threats_status(game)
        assert "tipping point" in text

    def test_no_threats(self, load_engine: None) -> None:
        from straightjacket.web.serializers import build_threats_status

        game = make_game_state()
        text = build_threats_status(game)
        assert "No active threats" in text


class TestResolveForsakeVow:
    def test_menace_full_fails_vow(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.threats import resolve_full_menace

        game = _game_with_threat()
        game.threats[0].menace_ticks = 40
        events = resolve_full_menace(game, make_outcome())
        assert len(events) == 1
        assert events[0].source == "forsake_vow"
        assert game.progress_tracks[0].status == "failed"
        assert game.threats[0].status == "resolved"

    def test_menace_full_damages_spirit(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.threats import resolve_full_menace

        game = _game_with_threat()
        game.threats[0].menace_ticks = 40
        old_spirit = game.resources.meters["spirit"]
        result = make_outcome()
        resolve_full_menace(game, result)
        assert game.resources.meters["spirit"] == old_spirit - 2
        assert labels_of(result.consequences) == ['forsake the vow "Hunt the beast"', "spirit -2"]
        assert result.follow_up_moves == []

    def test_classic_forsakes_through_endure_stress(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.threats import resolve_full_menace

        game = _game_with_threat()
        game.setting_id = "classic"
        game.threats[0].menace_ticks = 40
        result = make_outcome()
        resolve_full_menace(game, result)
        assert result.follow_up_moves == ["suffer/endure_stress"]

    def test_menace_full_deactivates_thread(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.threats import resolve_full_menace

        game = _game_with_threat()
        game.narrative.threads.append(
            make_thread(
                id="thread_hunt",
                name="Hunt the beast",
                linked_track_id="vow_hunt",
                active=True,
                source="creation",
                thread_type="vow",
            )
        )
        game.threats[0].menace_ticks = 40
        resolve_full_menace(game, make_outcome())
        assert not game.narrative.threads[0].active

    def test_menace_not_full_no_effect(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.threats import resolve_full_menace

        game = _game_with_threat()
        game.threats[0].menace_ticks = 30
        events = resolve_full_menace(game, make_outcome())
        assert events == []
        assert game.progress_tracks[0].status == "active"
        assert game.threats[0].status == "active"

    def test_resolved_threat_skipped(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.threats import resolve_full_menace

        game = _game_with_threat()
        game.threats[0].menace_ticks = 40
        game.threats[0].status = "resolved"
        events = resolve_full_menace(game, make_outcome())
        assert events == []

    def test_menace_full_vow_already_gone(self, stub_engine: None) -> None:
        from straightjacket.engine.ruleset.threats import resolve_full_menace

        game = _game_with_threat()
        game.threats[0].menace_ticks = 40
        game.progress_tracks[0].status = "completed"
        resolve_full_menace(game, make_outcome())
        assert game.threats[0].status == "resolved"

        assert game.resources.meters["spirit"] == 5


class TestVowCompletionResolveThreat:
    def test_vow_completed_resolves_threat_as_overcome(self) -> None:
        from straightjacket.engine.ruleset.tracks import complete_track

        game = _game_with_threat()
        game.threats[0].menace_ticks = 20
        complete_track(game, "vow_hunt", "completed")
        assert game.threats[0].status == "overcome"

    def test_vow_failed_resolves_threat_as_resolved(self) -> None:
        from straightjacket.engine.ruleset.tracks import complete_track

        game = _game_with_threat()
        complete_track(game, "vow_hunt", "failed")
        assert game.threats[0].status == "resolved"

    def test_non_vow_track_does_not_touch_threats(self) -> None:
        from straightjacket.engine.ruleset.tracks import complete_track

        game = _game_with_threat()
        game.progress_tracks.append(make_progress_track(id="combat_1", name="Fight", track_type="combat", ticks=20))
        complete_track(game, "combat_1", "completed")
        assert game.threats[0].status == "active"


class TestAVowSwornAgainstAThreat:
    def test_swearing_a_vow_against_a_threat_links_them(self, load_engine: None) -> None:
        from straightjacket.engine.ruleset.threats import advance_menace_on_miss, vow_against
        from straightjacket.engine.ruleset.tracks import start_track
        from tests._helpers import make_brain_result

        game = make_game_state(player_name="Hero", setting_id="starforged")
        game.threats.append(make_threat(id="threat_ac_1", name="The Hollow Choir"))
        brain = make_brain_result(
            move="quest/swear_an_iron_vow",
            stat="heart",
            track_name="Silence the Hollow Choir",
            track_rank="dangerous",
            target_threat="threat_ac_1",
        )
        start_track(game, brain, "STRONG_HIT")
        vow = vow_against(game, game.threats[0])
        assert vow is not None
        assert vow.name == "Silence the Hollow Choir"
        assert [e.threat_id for e in advance_menace_on_miss(game)] == ["threat_ac_1"]

    def test_a_vow_sworn_without_a_threat_links_none(self, load_engine: None) -> None:
        from straightjacket.engine.ruleset.threats import advance_menace_on_miss, vow_against
        from straightjacket.engine.ruleset.tracks import start_track
        from tests._helpers import make_brain_result

        game = make_game_state(player_name="Hero", setting_id="starforged")
        game.threats.append(make_threat(id="threat_ac_1"))
        brain = make_brain_result(
            move="quest/swear_an_iron_vow", stat="heart", track_name="Find my brother", track_rank="dangerous"
        )
        start_track(game, brain, "STRONG_HIT")
        assert vow_against(game, game.threats[0]) is None
        assert advance_menace_on_miss(game) == []

    def test_the_brain_sees_threats_and_may_name_one_without_a_vow(self, load_engine: None) -> None:
        from straightjacket.engine.ai.brain import call_brain
        from tests.test_brain_move_availability import _BrainAnswers

        game = _game_with_threat()
        game.threats.append(make_threat(id="threat_ac_1", name="The Hollow Choir"))
        provider = _BrainAnswers("adventure/face_danger", target_threat="threat_ac_1")
        result = call_brain(provider, game, "I swear to silence the choir.")
        message = provider.user_messages[0]
        assert "The Beast Awakens (id:threat_beast) menace 0/10, the vow Hunt the beast is sworn against it" in message
        assert "The Hollow Choir (id:threat_ac_1) menace 0/10" in message
        assert provider.schemas[0]["properties"]["target_threat"]["anyOf"][0]["enum"] == ["threat_ac_1"]
        assert result.target_threat == "threat_ac_1"
