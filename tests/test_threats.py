import pytest

from straightjacket.engine.ai.brain import call_brain
from straightjacket.engine.models import GameState, Resources, ThreatData, labels_of
from straightjacket.engine.ruleset import threats
from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.progress import advance_menace, menace_boxes, menace_per_mark
from straightjacket.engine.ruleset.threats import (
    advance_menace_on_miss,
    advance_threat_by_id,
    resolve_full_menace,
    take_pending_threat_events,
    vow_against,
)
from straightjacket.engine.ruleset.tracks import complete_track, start_track
from straightjacket.engine.setting.packages import load_package
from straightjacket.web.serializers import build_threats_status
from tests._creation import TurnProvider, brain_answer
from tests._helpers import (
    dialog_prompt,
    fix_dice,
    make_brain_result,
    make_game_state,
    make_outcome,
    make_progress_track,
    make_thread,
    make_threat,
    make_world_state,
    schema_of,
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
    @staticmethod
    def test_menace_per_mark_dangerous() -> None:
        t = make_threat(rank="dangerous")
        assert menace_per_mark(t) == 8

    @staticmethod
    def test_menace_per_mark_epic() -> None:
        t = make_threat(rank="epic")
        assert menace_per_mark(t) == 1

    @staticmethod
    def test_advance_menace() -> None:
        t = make_threat(rank="dangerous", menace_ticks=0)
        added = advance_menace(t, 1)
        assert added == 8
        assert t.menace_ticks == 8
        assert menace_boxes(t) == 2

    @staticmethod
    def test_advance_menace_clamped() -> None:
        t = make_threat(rank="dangerous", menace_ticks=36)
        added = advance_menace(t, 1)
        assert added == 4
        assert t.menace_ticks == 40
        assert t.menace_full

    @staticmethod
    def test_menace_full_property() -> None:
        t = make_threat(menace_ticks=40)
        assert t.menace_full
        t2 = make_threat(menace_ticks=39)
        assert not t2.menace_full

    @staticmethod
    def test_serialization_round_trip() -> None:
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
    @staticmethod
    def test_threats_restored_on_snapshot() -> None:
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

    @staticmethod
    def test_to_dict_from_dict_round_trip() -> None:
        game = _game_with_threat()
        advance_menace(game.threats[0], 1)
        d = game.to_dict()
        game2 = GameState.from_dict(d)
        assert len(game2.threats) == 1
        assert game2.threats[0].menace_ticks == 8
        assert game2.threats[0].linked_vow_id == "vow_hunt"


class TestMenaceOnMiss:
    @staticmethod
    def test_advance_on_miss() -> None:
        game = _game_with_threat()
        events = advance_menace_on_miss(game)
        assert len(events) == 1
        assert events[0].threat_name == "The Beast Awakens"
        assert game.threats[0].menace_ticks == 8

    @staticmethod
    def test_no_advance_when_vow_completed() -> None:
        game = _game_with_threat()
        game.progress_tracks[0].status = "completed"
        events = advance_menace_on_miss(game)
        assert events == []
        assert game.threats[0].menace_ticks == 0

    @staticmethod
    def test_no_advance_when_threat_resolved() -> None:
        game = _game_with_threat()
        game.threats[0].status = "resolved"
        events = advance_menace_on_miss(game)
        assert events == []

    @staticmethod
    def test_menace_full_event() -> None:
        game = _game_with_threat()
        game.threats[0].menace_ticks = 36
        events = advance_menace_on_miss(game)
        assert len(events) == 1
        assert events[0].menace_full
        assert game.threats[0].menace_full


class TestAdvanceById:
    @staticmethod
    def test_a_random_event_marks_the_configured_menace() -> None:
        game = _game_with_threat()
        advance_threat_by_id(game, "threat_beast")
        threat = game.threats[0]
        assert threat.menace_ticks == rules().threats.menace_on_random_event * menace_per_mark(threat)

    @staticmethod
    def test_advance_nonexistent_changes_nothing() -> None:
        game = _game_with_threat()
        advance_threat_by_id(game, "nonexistent")
        assert game.threats[0].menace_ticks == 0


class TestAdvancesReachTheNarrator:
    @staticmethod
    def test_an_autonomous_tick_waits_for_the_next_turn_as_off_screen(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("straightjacket.engine.ruleset.threats.random.random", lambda: 0.0)
        game = _game_with_threat()
        threats.tick_autonomous_threats(game)
        [event] = game.world.pending_threat_events
        assert (event.source, event.threat_name) == ("autonomous", "The Beast Awakens")
        assert threats.take_pending_threat_events(game) == [event]
        assert game.world.pending_threat_events == []
        assert '<threat_advance name="The Beast Awakens" menace_full="False" offscreen="true"/>' in dialog_prompt(
            game, threat_events=[event]
        )

    @staticmethod
    def test_a_random_event_advance_is_told_in_its_own_turn() -> None:
        game = _game_with_threat()
        advance_threat_by_id(game, "threat_beast")
        [event] = take_pending_threat_events(game)
        assert event.source == "random_event"
        assert "offscreen" not in dialog_prompt(game, threat_events=[event])

    @staticmethod
    def test_delve_tells_what_the_threat_does_from_its_category() -> None:
        rows = {row.text for row in load_package("delve").oracle_table("threat/rampaging_creature").rows}
        game = _game_with_threat()
        game.setting_id = "delve"
        [event] = advance_menace_on_miss(game)
        assert any(event.development.endswith(f". {row}") for row in rows)
        assert f">{event.development}</threat_advance>" in dialog_prompt(game, threat_events=[event])
        game.setting_id = "starforged"
        game.threats[0].menace_ticks = 0
        assert not advance_menace_on_miss(game)[0].development


class TestThreatsStatus:
    @staticmethod
    def test_active_threats_shown() -> None:
        game = _game_with_threat()
        text = build_threats_status(game)
        assert "Beast Awakens" in text
        assert "distant" in text

    @staticmethod
    def test_high_menace_shown() -> None:
        game = _game_with_threat()
        game.threats[0].menace_ticks = 36
        text = build_threats_status(game)
        assert "tipping point" in text

    @staticmethod
    def test_no_threats() -> None:
        game = make_game_state()
        text = build_threats_status(game)
        assert "No active threats" in text


class TestResolveForsakeVow:
    @staticmethod
    def test_menace_full_fails_vow() -> None:
        game = _game_with_threat()
        game.threats[0].menace_ticks = 40
        events = resolve_full_menace(game, make_outcome())
        assert len(events) == 1
        assert events[0].source == "forsake_vow"
        assert game.progress_tracks[0].status == "failed"
        assert game.threats[0].status == "resolved"

    @staticmethod
    def test_menace_full_damages_spirit() -> None:
        game = _game_with_threat()
        game.threats[0].menace_ticks = 40
        old_spirit = game.resources.meters["spirit"]
        result = make_outcome()
        resolve_full_menace(game, result)
        assert game.resources.meters["spirit"] == old_spirit - 2
        assert labels_of(result.consequences) == ['forsake the vow "Hunt the beast"', "spirit -2"]
        assert result.follow_up_moves == []

    @staticmethod
    def test_classic_forsakes_through_endure_stress() -> None:
        game = _game_with_threat()
        game.setting_id = "classic"
        game.progress_tracks[0].rank = "formidable"
        game.threats[0].menace_ticks = 40
        result = make_outcome()
        resolve_full_menace(game, result)
        assert result.follow_up_moves == ["suffer/endure_stress"]
        assert labels_of(result.consequences) == ['forsake the vow "Hunt the beast"', "spirit -3"]

    @staticmethod
    def test_menace_full_deactivates_thread() -> None:
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

    @staticmethod
    def test_menace_not_full_no_effect() -> None:
        game = _game_with_threat()
        game.threats[0].menace_ticks = 30
        events = resolve_full_menace(game, make_outcome())
        assert events == []
        assert game.progress_tracks[0].status == "active"
        assert game.threats[0].status == "active"

    @staticmethod
    def test_resolved_threat_skipped() -> None:
        game = _game_with_threat()
        game.threats[0].menace_ticks = 40
        game.threats[0].status = "resolved"
        events = resolve_full_menace(game, make_outcome())
        assert events == []

    @staticmethod
    def test_menace_full_vow_already_gone() -> None:
        game = _game_with_threat()
        game.threats[0].menace_ticks = 40
        game.progress_tracks[0].status = "completed"
        [event] = resolve_full_menace(game, make_outcome())
        assert game.threats[0].status == "resolved"
        assert (event.source, event.menace_full, event.development) == (
            "goal_achieved",
            True,
            rules().threats.goal_achieved,
        )
        assert rules().threats.goal_achieved in dialog_prompt(game, threat_events=[event])

        assert game.resources.meters["spirit"] == 5


class TestVowCompletionResolveThreat:
    @staticmethod
    def test_vow_completed_resolves_threat_as_overcome() -> None:
        game = _game_with_threat()
        game.threats[0].menace_ticks = 20
        complete_track(game, "vow_hunt", "completed")
        assert game.threats[0].status == "overcome"

    @staticmethod
    def test_vow_failed_resolves_threat_as_resolved() -> None:
        game = _game_with_threat()
        complete_track(game, "vow_hunt", "failed")
        assert game.threats[0].status == "resolved"

    @staticmethod
    def test_non_vow_track_does_not_touch_threats() -> None:
        game = _game_with_threat()
        game.progress_tracks.append(make_progress_track(id="combat_1", name="Fight", track_type="combat", ticks=20))
        complete_track(game, "combat_1", "completed")
        assert game.threats[0].status == "active"


class TestAVowSwornAgainstAThreat:
    @staticmethod
    def test_swearing_a_vow_against_a_threat_links_them() -> None:
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

    @staticmethod
    def test_a_vow_sworn_without_a_threat_links_none() -> None:
        game = make_game_state(player_name="Hero", setting_id="starforged")
        game.threats.append(make_threat(id="threat_ac_1"))
        brain = make_brain_result(
            move="quest/swear_an_iron_vow", stat="heart", track_name="Find my brother", track_rank="dangerous"
        )
        start_track(game, brain, "STRONG_HIT")
        assert vow_against(game, game.threats[0]) is None
        assert advance_menace_on_miss(game) == []

    @staticmethod
    def test_the_brain_sees_threats_and_may_name_one_without_a_vow() -> None:
        game = _game_with_threat()
        game.threats.append(make_threat(id="threat_ac_1", name="The Hollow Choir"))
        provider = TurnProvider(brain_answer(target_threat="threat_ac_1"))
        result = call_brain(provider, game, "I swear to silence the choir.")
        [call] = provider.calls
        message = call.messages[-1]["content"]
        assert "The Beast Awakens (id:threat_beast) menace 0/10, the vow Hunt the beast is sworn against it" in message
        assert "The Hollow Choir (id:threat_ac_1) menace 0/10" in message
        assert schema_of(call)["properties"]["target_threat"]["anyOf"][0]["enum"] == ["threat_ac_1"]
        assert result.target_threat == "threat_ac_1"


class TestAdvanceAThreatInClassic:
    @staticmethod
    @pytest.mark.parametrize(
        ("tens", "units", "marks", "told"),
        [
            (1, 2, 1, "The threat readies its next step, or a new danger looms."),
            (4, 5, 1, "The threat works subtly to advance toward its goal, or the danger escalates."),
            (8, 3, 2, "The threat makes a dramatic and immediate move, or a major event reveals new complications."),
        ],
    )
    def test_every_advance_rolls_delves_table(
        monkeypatch: pytest.MonkeyPatch, tens: int, units: int, marks: int, told: str
    ) -> None:
        game = _game_with_threat()
        game.setting_id = "classic"
        fix_dice(monkeypatch, tens, units)
        [event] = advance_menace_on_miss(game)
        assert game.threats[0].menace_ticks == marks * menace_per_mark(game.threats[0])
        assert event.development == told

    @staticmethod
    def test_a_match_exposes_a_surprising_aspect(monkeypatch: pytest.MonkeyPatch) -> None:
        game = _game_with_threat()
        game.setting_id = "classic"
        fix_dice(monkeypatch, 5, 5)
        advance_threat_by_id(game, "threat_beast")
        [event] = take_pending_threat_events(game)
        assert event.development.endswith(rules().threats.advance_a_threat["classic"].match)

    @staticmethod
    def test_starforged_keeps_its_one_mark_until_its_own_clocks() -> None:
        game = _game_with_threat()
        [event] = advance_menace_on_miss(game)
        assert game.threats[0].menace_ticks == rules().threats.menace_on_miss * menace_per_mark(game.threats[0])
        assert not event.development
