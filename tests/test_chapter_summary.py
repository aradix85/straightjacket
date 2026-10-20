from __future__ import annotations

from straightjacket.engine.models import ChapterSummary, GameState
from tests._helpers import (
    make_blueprint,
    make_npc,
    make_plotline,
    make_progress_track,
    make_thread,
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
    def test_round_trip_preserves_scalar_fields(self, load_engine: None) -> None:
        original = _populated_summary()
        restored = ChapterSummary.from_dict(original.to_dict())
        assert restored.chapter == 3
        assert restored.title == "Title 3"
        assert restored.summary == "What happened."

    def test_round_trip_preserves_unresolved_threads(self, load_engine: None) -> None:
        original = _populated_summary()
        restored = ChapterSummary.from_dict(original.to_dict())
        assert restored.unresolved_threads == ["thread1", "thread2"]


def _closed(game: GameState) -> ChapterSummary:
    from straightjacket.engine.game.chapters import start_new_chapter
    from tests._creation import OpeningProvider

    start_new_chapter(OpeningProvider([], "Ring Dock"), game)
    return game.campaign.campaign_history[-1]


def _game() -> GameState:
    from tests._creation import create_game

    return create_game(
        "starforged",
        location="Old tollhouse",
        npcs=[],
        stats=(2, 2, 1, 1, 3),
        player_name="Hero",
        background_vow="Ring it",
    )


class TestChapterRecord:
    def test_the_record_is_built_from_the_game_state(self, load_engine: None) -> None:
        game = _game()
        game.narrative.story_blueprint = make_blueprint(central_conflict="The drowned bell")
        fulfilled = make_progress_track(id="v1", name="Ring the bell", track_type="vow")
        fulfilled.status = "completed"
        game.progress_tracks = [fulfilled, make_progress_track(id="v2", name="Find Kira", track_type="vow")]
        game.narrative.plotlines_list = [make_plotline(id="p1", name="The bell", status="conclusion")]
        game.narrative.threads = [
            make_thread(id="thr1", name="Who cast the bell", thread_type="plot", source="ac"),
            make_thread(id="thr2", name="Find Kira", thread_type="vow", source="vow"),
        ]
        game.npcs = [
            make_npc(id="npc_1", name="Mira", disposition="friendly"),
            make_npc(id="npc_2", name="Old Marda", status="deceased"),
        ]
        game.threats = [make_threat(id="th1", name="The tide cult")]

        summary = _closed(game)

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

    def test_a_chapter_without_a_blueprint_has_no_conflict_line(self, load_engine: None) -> None:
        game = _game()
        game.narrative.story_blueprint = None
        game.campaign.chapter_number = 2
        summary = _closed(game)
        assert summary.title == "Chapter 2"
        assert "The conflict" not in summary.summary
