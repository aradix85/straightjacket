from __future__ import annotations


import pytest

from straightjacket.engine.game.chapters import _close_previous_chapter, _reset_chapter_mechanics
from straightjacket.engine.models import (
    ChapterSummary,
    GameState,
    ThreadEntry,
)
from tests._helpers import (
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
    )


class TestChapterSummaryRoundTrip:
    def test_round_trip_preserves_scalar_fields(self, stub_engine: None) -> None:
        original = _populated_summary()
        restored = ChapterSummary.from_dict(original.to_dict())
        assert restored.chapter == 3
        assert restored.title == "Title 3"
        assert restored.summary == "What happened."

    def test_round_trip_preserves_unresolved_threads(self, stub_engine: None) -> None:
        original = _populated_summary()
        restored = ChapterSummary.from_dict(original.to_dict())
        assert restored.unresolved_threads == ["thread1", "thread2"]


class TestChapterSummaryRequiredFields:
    def test_missing_field_raises(self, stub_engine: None) -> None:
        with pytest.raises(TypeError):
            ChapterSummary(
                chapter=1,
                title="t",
                summary="s",
            )


class TestChapterTransitionCarriesStateOver:
    def _populated_game(self) -> GameState:
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
        return game

    def test_close_and_reset_keep_what_carries_over(self, load_engine: None) -> None:
        game = self._populated_game()
        track_ids_before = {t.id for t in game.progress_tracks}
        threat_ids_before = {t.id for t in game.threats}
        thread_ids_before = {t.id for t in game.narrative.threads}

        _close_previous_chapter(game)
        _reset_chapter_mechanics(game)

        assert {t.id for t in game.progress_tracks} == track_ids_before
        assert {t.id for t in game.threats} == threat_ids_before
        assert game.impacts == ["wounded"]
        assert game.assets == ["asset_compass"]
        assert {t.id for t in game.narrative.threads} == thread_ids_before

    def test_reset_starts_the_chapter_state_fresh(self, load_engine: None) -> None:
        game = self._populated_game()
        game.narrative.scene_count = 17
        game.world.location_history = ["Old dock"]
        _reset_chapter_mechanics(game)
        assert game.narrative.scene_count == 1
        assert game.world.location_history == []
        assert game.narrative.story_blueprint is None


class TestChapterRecord:
    def test_the_record_is_built_from_the_game_state(self, load_engine: None) -> None:
        from straightjacket.engine.models import PlotlineEntry
        from straightjacket.engine.models_story import StoryBlueprint
        from tests._helpers import make_npc

        game = make_game_state(player_name="Hero", setting_id="starforged")
        game.world.current_location = "Old tollhouse"
        game.narrative.story_blueprint = StoryBlueprint(
            central_conflict="The drowned bell", antagonist_force="", thematic_thread="", structure_type="3act"
        )
        fulfilled = make_progress_track(id="v1", name="Ring the bell", track_type="vow")
        fulfilled.status = "completed"
        game.progress_tracks = [fulfilled, make_progress_track(id="v2", name="Find Kira", track_type="vow")]
        game.narrative.plotlines_list = [PlotlineEntry(id="p1", name="The bell", status="conclusion")]
        game.narrative.threads = [
            ThreadEntry(id="thr1", name="Who cast the bell", thread_type="plot", source="ac"),
            ThreadEntry(id="thr2", name="Find Kira", thread_type="vow", source="vow"),
        ]
        game.npcs = [
            make_npc(id="npc_1", name="Mira", disposition="friendly"),
            make_npc(id="npc_2", name="Old Marda", status="deceased"),
        ]
        game.threats = [make_threat(id="th1", name="The tide cult")]

        summary = _close_previous_chapter(game)

        assert summary.title == "Chapter 1"
        assert summary.summary.startswith("The conflict: The drowned bell")
        for part in (
            "Ring the bell",
            "Find Kira",
            "The bell",
            "Who cast the bell",
            "Mira (friendly",
            "Old Marda",
            "The tide cult",
            "Old tollhouse",
        ):
            assert part in summary.summary
        assert summary.unresolved_threads == ["Who cast the bell", "Find Kira"]
        assert summary.summary.count("Find Kira") == 1
        assert game.campaign.campaign_history[-1] is summary

    def test_a_chapter_without_a_blueprint_has_no_conflict_line(self, load_engine: None) -> None:
        game = make_game_state(player_name="Hero", setting_id="starforged")
        game.narrative.story_blueprint = None
        game.campaign.chapter_number = 2
        summary = _close_previous_chapter(game)
        assert summary.title == "Chapter 2"
        assert "The conflict" not in summary.summary
