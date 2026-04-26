from straightjacket.engine.models import GameState, Resources, ThreatData
from tests._helpers import make_game_state, make_progress_track, make_threat, make_world_state


def _game_with_threat() -> GameState:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    g.resources = Resources(health=5, spirit=5, supply=5, momentum=2, max_momentum=10)
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
        assert t.menace_per_mark == 8

    def test_menace_per_mark_epic(self) -> None:
        t = make_threat(rank="epic")
        assert t.menace_per_mark == 1

    def test_advance_menace(self) -> None:
        t = make_threat(rank="dangerous", menace_ticks=0)
        added = t.advance_menace(1)
        assert added == 8
        assert t.menace_ticks == 8
        assert t.menace_filled_boxes == 2

    def test_advance_menace_clamped(self) -> None:
        t = make_threat(rank="dangerous", menace_ticks=36)
        added = t.advance_menace(1)
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
        assert t2.menace_per_mark == 4


class TestThreatSnapshotRestore:
    def test_threats_restored_on_snapshot(self) -> None:
        game = _game_with_threat()
        snap = game.snapshot()

        game.threats[0].advance_menace(2)
        game.threats.append(make_threat(id="t2", name="New Threat"))
        assert game.threats[0].menace_ticks == 16
        assert len(game.threats) == 2

        game.restore(snap)
        assert len(game.threats) == 1
        assert game.threats[0].menace_ticks == 0
        assert game.threats[0].name == "The Beast Awakens"

    def test_to_dict_from_dict_round_trip(self) -> None:
        game = _game_with_threat()
        game.threats[0].advance_menace(1)
        d = game.to_dict()
        game2 = GameState.from_dict(d)
        assert len(game2.threats) == 1
        assert game2.threats[0].menace_ticks == 8
        assert game2.threats[0].linked_vow_id == "vow_hunt"


class TestMenaceOnMiss:
    def test_advance_on_miss(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.threats import advance_menace_on_miss

        game = _game_with_threat()
        events = advance_menace_on_miss(game)
        assert len(events) == 1
        assert events[0].threat_name == "The Beast Awakens"
        assert events[0].ticks_added == 8
        assert game.threats[0].menace_ticks == 8

    def test_no_advance_when_vow_completed(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.threats import advance_menace_on_miss

        game = _game_with_threat()
        game.progress_tracks[0].status = "completed"
        events = advance_menace_on_miss(game)
        assert events == []
        assert game.threats[0].menace_ticks == 0

    def test_no_advance_when_threat_resolved(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.threats import advance_menace_on_miss

        game = _game_with_threat()
        game.threats[0].status = "resolved"
        events = advance_menace_on_miss(game)
        assert events == []

    def test_menace_full_event(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.threats import advance_menace_on_miss

        game = _game_with_threat()
        game.threats[0].menace_ticks = 36
        events = advance_menace_on_miss(game)
        assert len(events) == 1
        assert events[0].menace_full
        assert game.threats[0].menace_full


class TestAdvanceById:
    def test_advance_specific_threat(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.threats import advance_threat_by_id

        game = _game_with_threat()
        event = advance_threat_by_id(game, "threat_beast", marks=1, source="random_event")
        assert event is not None
        assert event.source == "random_event"
        assert game.threats[0].menace_ticks == 8

    def test_advance_nonexistent_returns_none(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.threats import advance_threat_by_id

        game = _game_with_threat()
        event = advance_threat_by_id(game, "nonexistent", marks=1, source="test")
        assert event is None


class TestThreatAdvanceValidator:
    def test_threat_name_in_narration_passes(self) -> None:
        from straightjacket.engine.ai.rule_validator import check_threat_advance

        result = check_threat_advance(
            "The Beast stirs in the distance, its presence growing heavier.",
            ["The Beast Awakens"],
        )
        assert result == []

    def test_threat_name_missing_fails(self) -> None:
        from straightjacket.engine.ai.rule_validator import check_threat_advance

        result = check_threat_advance(
            "You pick up your sword and continue walking.",
            ["The Beast Awakens"],
        )
        assert len(result) == 1
        assert "THREAT ADVANCE" in result[0]

    def test_empty_threat_names_passes(self) -> None:
        from straightjacket.engine.ai.rule_validator import check_threat_advance

        result = check_threat_advance("Anything here.", [])
        assert result == []


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
        from straightjacket.engine.mechanics.threats import resolve_full_menace

        game = _game_with_threat()
        game.threats[0].menace_ticks = 40
        events = resolve_full_menace(game)
        assert len(events) == 1
        assert events[0].source == "forsake_vow"
        assert game.progress_tracks[0].status == "failed"
        assert game.threats[0].status == "resolved"

    def test_menace_full_damages_spirit(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.threats import resolve_full_menace

        game = _game_with_threat()
        game.threats[0].menace_ticks = 40
        old_spirit = game.resources.spirit
        resolve_full_menace(game)
        assert game.resources.spirit == old_spirit - 2

    def test_menace_full_deactivates_thread(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.threats import resolve_full_menace
        from straightjacket.engine.models import ThreadEntry

        game = _game_with_threat()
        game.narrative.threads.append(
            ThreadEntry(
                id="thread_hunt",
                name="Hunt the beast",
                linked_track_id="vow_hunt",
                active=True,
                source="creation",
                thread_type="vow",
            )
        )
        game.threats[0].menace_ticks = 40
        resolve_full_menace(game)
        assert not game.narrative.threads[0].active

    def test_menace_not_full_no_effect(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.threats import resolve_full_menace

        game = _game_with_threat()
        game.threats[0].menace_ticks = 30
        events = resolve_full_menace(game)
        assert events == []
        assert game.progress_tracks[0].status == "active"
        assert game.threats[0].status == "active"

    def test_resolved_threat_skipped(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.threats import resolve_full_menace

        game = _game_with_threat()
        game.threats[0].menace_ticks = 40
        game.threats[0].status = "resolved"
        events = resolve_full_menace(game)
        assert events == []

    def test_menace_full_vow_already_gone(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.threats import resolve_full_menace

        game = _game_with_threat()
        game.threats[0].menace_ticks = 40
        game.progress_tracks[0].status = "completed"
        resolve_full_menace(game)
        assert game.threats[0].status == "resolved"

        assert game.resources.spirit == 5


class TestVowCompletionResolveThreat:
    def test_vow_completed_resolves_threat_as_overcome(self) -> None:
        from straightjacket.engine.game.tracks import complete_track

        game = _game_with_threat()
        game.threats[0].menace_ticks = 20
        complete_track(game, "vow_hunt", "completed")
        assert game.threats[0].status == "overcome"

    def test_vow_failed_resolves_threat_as_resolved(self) -> None:
        from straightjacket.engine.game.tracks import complete_track

        game = _game_with_threat()
        complete_track(game, "vow_hunt", "failed")
        assert game.threats[0].status == "resolved"

    def test_non_vow_track_does_not_touch_threats(self) -> None:
        from straightjacket.engine.game.tracks import complete_track

        game = _game_with_threat()
        game.progress_tracks.append(make_progress_track(id="combat_1", name="Fight", track_type="combat", ticks=20))
        complete_track(game, "combat_1", "completed")
        assert game.threats[0].status == "active"
