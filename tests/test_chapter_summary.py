from __future__ import annotations

from typing import Any

import pytest

from straightjacket.engine.game.chapters import (
    _reset_chapter_mechanics,
    _restore_chapter_mechanics,
)
from straightjacket.engine.models import (
    ChapterSummary,
    GameState,
    NpcEvolution,
    ProgressTrack,
    ThreadEntry,
    ThreatData,
)
from tests._helpers import (
    make_chapter_summary,
    make_game_state,
    make_progress_track,
    make_threat,
)


def _populated_summary() -> ChapterSummary:
    return ChapterSummary(
        chapter=3,
        title="Title 3",
        summary="What happened.",
        unresolved_threads=["thread1", "thread2"],
        character_growth="grew",
        npc_evolutions=[NpcEvolution(name="Alice", projection="bitter")],
        thematic_question="why?",
        post_story_location="Citadel",
        scenes=42,
        progress_tracks=[make_progress_track(id="t1", name="Vow", track_type="vow")],
        threats=[make_threat(id="th1", name="Boss")],
        impacts=["wounded", "shaken"],
        assets=["asset_compass", "asset_companion"],
        threads=[ThreadEntry(id="thr1", name="Find the truth", thread_type="vow", weight=2, source="creation")],
        characters_list=[],
        plotlines_list=[],
    )


class TestChapterSummaryRoundTrip:
    def test_round_trip_preserves_scalar_fields(self, stub_engine: None) -> None:
        original = _populated_summary()
        restored = ChapterSummary.from_dict(original.to_dict())
        assert restored.chapter == 3
        assert restored.title == "Title 3"
        assert restored.summary == "What happened."
        assert restored.character_growth == "grew"
        assert restored.thematic_question == "why?"
        assert restored.post_story_location == "Citadel"
        assert restored.scenes == 42

    def test_round_trip_preserves_list_fields(self, stub_engine: None) -> None:
        original = _populated_summary()
        restored = ChapterSummary.from_dict(original.to_dict())
        assert restored.unresolved_threads == ["thread1", "thread2"]
        assert restored.impacts == ["wounded", "shaken"]
        assert restored.assets == ["asset_compass", "asset_companion"]

    def test_round_trip_preserves_npc_evolutions(self, stub_engine: None) -> None:
        original = _populated_summary()
        restored = ChapterSummary.from_dict(original.to_dict())
        assert len(restored.npc_evolutions) == 1
        assert restored.npc_evolutions[0].name == "Alice"
        assert restored.npc_evolutions[0].projection == "bitter"
        assert isinstance(restored.npc_evolutions[0], NpcEvolution)

    def test_round_trip_preserves_progress_tracks(self, stub_engine: None) -> None:
        original = _populated_summary()
        restored = ChapterSummary.from_dict(original.to_dict())
        assert len(restored.progress_tracks) == 1
        assert restored.progress_tracks[0].id == "t1"
        assert restored.progress_tracks[0].name == "Vow"
        assert isinstance(restored.progress_tracks[0], ProgressTrack)

    def test_round_trip_preserves_threats(self, stub_engine: None) -> None:
        original = _populated_summary()
        restored = ChapterSummary.from_dict(original.to_dict())
        assert len(restored.threats) == 1
        assert restored.threats[0].id == "th1"
        assert restored.threats[0].name == "Boss"
        assert isinstance(restored.threats[0], ThreatData)

    def test_round_trip_preserves_threads(self, stub_engine: None) -> None:
        original = _populated_summary()
        restored = ChapterSummary.from_dict(original.to_dict())
        assert len(restored.threads) == 1
        assert restored.threads[0].id == "thr1"
        assert restored.threads[0].name == "Find the truth"
        assert restored.threads[0].thread_type == "vow"
        assert isinstance(restored.threads[0], ThreadEntry)


class TestChapterSummaryRequiredFields:
    def test_missing_field_raises(self, stub_engine: None) -> None:
        with pytest.raises(TypeError):
            ChapterSummary(
                chapter=1,
                title="t",
                summary="s",
            )

    def test_npc_evolution_missing_field_raises(self, stub_engine: None) -> None:
        with pytest.raises(TypeError):
            NpcEvolution(name="Alice")


class TestResetChapterMechanics:
    def _populated_game(self) -> GameState:
        game = make_game_state(player_name="Hero", setting_id="starforged")
        game.progress_tracks = [make_progress_track(id="t1", name="Vow", track_type="vow")]
        game.threats = [make_threat(id="th1", name="Boss")]
        game.impacts = ["wounded"]
        game.assets = ["asset_compass"]
        game.narrative.threads = [
            ThreadEntry(id="thr1", name="The truth", thread_type="vow", weight=2, source="creation")
        ]
        return game

    def test_reset_clears_progress_tracks(self, stub_engine: None) -> None:
        game = self._populated_game()
        _reset_chapter_mechanics(game)
        assert game.progress_tracks == []

    def test_reset_clears_threats(self, stub_engine: None) -> None:
        game = self._populated_game()
        _reset_chapter_mechanics(game)
        assert game.threats == []

    def test_reset_clears_impacts(self, stub_engine: None) -> None:
        game = self._populated_game()
        _reset_chapter_mechanics(game)
        assert game.impacts == []

    def test_reset_clears_assets(self, stub_engine: None) -> None:
        game = self._populated_game()
        _reset_chapter_mechanics(game)
        assert game.assets == []

    def test_reset_clears_threads(self, stub_engine: None) -> None:
        game = self._populated_game()
        _reset_chapter_mechanics(game)
        assert game.narrative.threads == []


class TestRestoreChapterMechanics:
    def test_restore_replays_progress_tracks(self, stub_engine: None) -> None:
        game = make_game_state(player_name="Hero", setting_id="starforged")
        summary = _populated_summary()
        _reset_chapter_mechanics(game)
        _restore_chapter_mechanics(game, summary)
        assert len(game.progress_tracks) == 1
        assert game.progress_tracks[0].id == "t1"

    def test_restore_replays_threats(self, stub_engine: None) -> None:
        game = make_game_state(player_name="Hero", setting_id="starforged")
        summary = _populated_summary()
        _reset_chapter_mechanics(game)
        _restore_chapter_mechanics(game, summary)
        assert len(game.threats) == 1
        assert game.threats[0].id == "th1"

    def test_restore_replays_impacts(self, stub_engine: None) -> None:
        game = make_game_state(player_name="Hero", setting_id="starforged")
        summary = _populated_summary()
        _reset_chapter_mechanics(game)
        _restore_chapter_mechanics(game, summary)
        assert game.impacts == ["wounded", "shaken"]

    def test_restore_replays_assets(self, stub_engine: None) -> None:
        game = make_game_state(player_name="Hero", setting_id="starforged")
        summary = _populated_summary()
        _reset_chapter_mechanics(game)
        _restore_chapter_mechanics(game, summary)
        assert game.assets == ["asset_compass", "asset_companion"]

    def test_restore_replays_threads(self, stub_engine: None) -> None:
        game = make_game_state(player_name="Hero", setting_id="starforged")
        summary = _populated_summary()
        _reset_chapter_mechanics(game)
        _restore_chapter_mechanics(game, summary)
        assert len(game.narrative.threads) == 1
        assert game.narrative.threads[0].id == "thr1"

    def test_mutating_live_state_does_not_corrupt_snapshot(self, stub_engine: None) -> None:
        game = make_game_state(player_name="Hero", setting_id="starforged")
        summary = _populated_summary()
        _reset_chapter_mechanics(game)
        _restore_chapter_mechanics(game, summary)

        game.progress_tracks.append(make_progress_track(id="leaked"))
        game.impacts.append("leaked_impact")

        assert len(summary.progress_tracks) == 1
        assert summary.progress_tracks[0].id == "t1"
        assert summary.impacts == ["wounded", "shaken"]


class TestChapterTransitionPreservesState:
    def test_no_silent_loss_after_close_reset_restore(self, stub_engine: None) -> None:
        game = make_game_state(player_name="Hero", setting_id="starforged")
        game.progress_tracks = [
            make_progress_track(id="vow_main", name="Find the truth", track_type="vow"),
            make_progress_track(id="vow_side", name="Help Alice", track_type="vow"),
        ]
        game.threats = [make_threat(id="cult", name="The Cult")]
        game.impacts = ["wounded"]
        game.assets = ["asset_compass"]
        game.narrative.threads = [
            ThreadEntry(id="thr1", name="Truth", thread_type="vow", weight=2, source="creation"),
        ]

        track_ids_before = {t.id for t in game.progress_tracks}
        threat_ids_before = {t.id for t in game.threats}
        impacts_before = list(game.impacts)
        assets_before = list(game.assets)
        thread_ids_before = {t.id for t in game.narrative.threads}

        summary = make_chapter_summary(
            chapter=game.campaign.chapter_number,
            scenes=game.narrative.scene_count,
            progress_tracks=[ProgressTrack.from_dict(p.to_dict()) for p in game.progress_tracks],
            threats=[ThreatData.from_dict(t.to_dict()) for t in game.threats],
            impacts=list(game.impacts),
            assets=list(game.assets),
            threads=[ThreadEntry.from_dict(th.to_dict()) for th in game.narrative.threads],
        )

        _reset_chapter_mechanics(game)
        _restore_chapter_mechanics(game, summary)

        assert {t.id for t in game.progress_tracks} == track_ids_before
        assert {t.id for t in game.threats} == threat_ids_before
        assert list(game.impacts) == impacts_before
        assert list(game.assets) == assets_before
        assert {t.id for t in game.narrative.threads} == thread_ids_before


class TestCallChapterSummaryFallback:
    def test_fallback_returns_complete_narrative_dict(self, stub_engine: None) -> None:
        from straightjacket.engine.ai.architect import call_chapter_summary

        game = make_game_state(player_name="Hero", setting_id="starforged")
        game.world.current_location = "TestLocation"

        class _FailingProvider:
            def create_message(self, **kwargs: Any) -> Any:
                raise RuntimeError("simulated AI failure")

        narrative = call_chapter_summary(_FailingProvider(), game, config=None)

        for key in (
            "title",
            "summary",
            "unresolved_threads",
            "character_growth",
            "npc_evolutions",
            "thematic_question",
            "post_story_location",
        ):
            assert key in narrative, f"fallback missing {key!r}"

        assert isinstance(narrative["title"], str)
        assert isinstance(narrative["unresolved_threads"], list)
        assert isinstance(narrative["npc_evolutions"], list)
        assert narrative["post_story_location"] == "TestLocation"

    def test_fallback_dict_constructs_chaptersummary(self, stub_engine: None) -> None:
        from straightjacket.engine.ai.architect import call_chapter_summary

        game = make_game_state(player_name="Hero", setting_id="starforged")

        class _FailingProvider:
            def create_message(self, **kwargs: Any) -> Any:
                raise RuntimeError("simulated AI failure")

        narrative = call_chapter_summary(_FailingProvider(), game, config=None)

        summary = ChapterSummary(
            chapter=game.campaign.chapter_number,
            title=narrative["title"],
            summary=narrative["summary"],
            unresolved_threads=list(narrative["unresolved_threads"]),
            character_growth=narrative["character_growth"],
            npc_evolutions=[NpcEvolution(**e) for e in narrative["npc_evolutions"]],
            thematic_question=narrative["thematic_question"],
            post_story_location=narrative["post_story_location"],
            scenes=game.narrative.scene_count,
            progress_tracks=list(game.progress_tracks),
            threats=list(game.threats),
            impacts=list(game.impacts),
            assets=list(game.assets),
            threads=list(game.narrative.threads),
            characters_list=list(game.narrative.characters_list),
            plotlines_list=list(game.narrative.plotlines_list),
        )

        ChapterSummary.from_dict(summary.to_dict())
