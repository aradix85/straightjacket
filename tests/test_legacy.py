"""Tests for step 12: legacy tracks and XP."""

from __future__ import annotations

from straightjacket.engine.models import GameState
from tests._helpers import make_brain_result, make_game_state, make_progress_track, make_threat


def _game() -> GameState:
    return make_game_state(player_name="Hero", setting_id="starforged")


class TestMarkLegacy:
    def test_mark_dangerous_adds_2_ticks(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.legacy import mark_legacy

        game = _game()
        mark_legacy(game, "quests", "dangerous")
        assert game.campaign.legacy_quests.ticks == 2

    def test_mark_formidable_adds_4_ticks(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.legacy import mark_legacy

        game = _game()
        mark_legacy(game, "quests", "formidable")
        assert game.campaign.legacy_quests.ticks == 4

    def test_mark_unknown_rank_raises(self, stub_engine: None) -> None:
        import pytest

        from straightjacket.engine.mechanics.legacy import mark_legacy

        game = _game()
        with pytest.raises(KeyError):
            mark_legacy(game, "quests", "bogus")

    def test_mark_unknown_track_raises(self, stub_engine: None) -> None:
        import pytest

        from straightjacket.engine.mechanics.legacy import mark_legacy

        game = _game()
        with pytest.raises(ValueError):
            mark_legacy(game, "bogus", "dangerous")

    def test_no_xp_before_box_fills(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.legacy import mark_legacy

        game = _game()
        xp = mark_legacy(game, "quests", "dangerous")  # 2 ticks, box not crossed
        assert xp == 0
        assert game.campaign.xp == 0

    def test_xp_on_box_cross(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.legacy import mark_legacy

        game = _game()
        mark_legacy(game, "quests", "dangerous")  # 2 ticks
        xp = mark_legacy(game, "quests", "dangerous")  # 4 ticks → 1 box filled
        assert xp == 2
        assert game.campaign.xp == 2
        assert game.campaign.legacy_quests.filled_boxes == 1

    def test_epic_rank_fills_3_boxes_at_once(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.legacy import mark_legacy

        game = _game()
        xp = mark_legacy(game, "quests", "epic")  # 12 ticks → 3 boxes
        assert xp == 6  # 3 boxes × 2 xp
        assert game.campaign.legacy_quests.filled_boxes == 3

    def test_mark_caps_at_max(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.legacy import mark_legacy

        game = _game()
        game.campaign.legacy_quests.ticks = 38  # 9 boxes, 2 ticks into 10th
        xp = mark_legacy(game, "quests", "epic")  # would add 12 ticks but caps at 40
        assert game.campaign.legacy_quests.ticks == 40
        assert game.campaign.legacy_quests.filled_boxes == 10
        assert xp == 2  # one more box crossed (9→10)

    def test_separate_tracks_independent(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.legacy import mark_legacy

        game = _game()
        mark_legacy(game, "quests", "formidable")  # 4 ticks = 1 box
        mark_legacy(game, "bonds", "dangerous")  # 2 ticks = 0 boxes
        assert game.campaign.legacy_quests.filled_boxes == 1
        assert game.campaign.legacy_bonds.filled_boxes == 0
        assert game.campaign.legacy_discoveries.filled_boxes == 0


class TestAdvanceAsset:
    def test_upgrade_spends_xp(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.legacy import advance_asset

        game = _game()
        game.campaign.xp = 5
        spent = advance_asset(game, "path/empath", "upgrade")
        assert spent == 2
        assert game.campaign.xp_spent == 2
        assert game.campaign.xp_available == 3

    def test_new_asset_costs_more(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.legacy import advance_asset

        game = _game()
        game.campaign.xp = 5
        spent = advance_asset(game, "path/empath", "new")
        assert spent == 3
        assert "path/empath" in game.assets

    def test_insufficient_xp_fails(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.legacy import advance_asset

        game = _game()
        game.campaign.xp = 1  # below any cost
        spent = advance_asset(game, "path/empath", "upgrade")
        assert spent == 0
        assert game.campaign.xp_spent == 0
        assert "path/empath" not in game.assets

    def test_new_asset_not_duplicated(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.legacy import advance_asset

        game = _game()
        game.campaign.xp = 10
        game.assets = ["path/empath"]
        advance_asset(game, "path/empath", "new")
        assert game.assets.count("path/empath") == 1


class TestThreatOvercomeBonus:
    def test_bonus_at_high_menace(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.legacy import apply_threat_overcome_bonus

        game = _game()
        threat = make_threat(id="t1", name="Foo", menace_ticks=30, max_menace_ticks=40)
        bonus = apply_threat_overcome_bonus(game, threat)
        assert bonus == 2
        assert game.campaign.xp == 2

    def test_no_bonus_below_threshold(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.legacy import apply_threat_overcome_bonus

        game = _game()
        threat = make_threat(id="t1", name="Foo", menace_ticks=10, max_menace_ticks=40)  # 25%
        bonus = apply_threat_overcome_bonus(game, threat)
        assert bonus == 0
        assert game.campaign.xp == 0

    def test_exactly_at_threshold_grants_bonus(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.legacy import apply_threat_overcome_bonus

        game = _game()
        threat = make_threat(id="t1", name="Foo", menace_ticks=20, max_menace_ticks=40)  # 50%
        bonus = apply_threat_overcome_bonus(game, threat)
        assert bonus == 2

    def test_zero_max_menace_safe(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.legacy import apply_threat_overcome_bonus

        game = _game()
        threat = make_threat(id="t1", name="Foo", menace_ticks=0, max_menace_ticks=0)
        bonus = apply_threat_overcome_bonus(game, threat)
        assert bonus == 0


class TestCampaignSnapshot:
    def test_snapshot_captures_xp(self, stub_engine: None) -> None:
        game = _game()
        game.campaign.xp = 7
        game.campaign.xp_spent = 2
        snap = game.campaign.snapshot()
        assert snap["xp"] == 7
        assert snap["xp_spent"] == 2

    def test_restore_reverts_legacy_progress(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.legacy import mark_legacy

        game = _game()
        snap = game.campaign.snapshot()
        mark_legacy(game, "quests", "epic")
        assert game.campaign.legacy_quests.filled_boxes == 3
        game.campaign.restore(snap)
        assert game.campaign.legacy_quests.filled_boxes == 0
        assert game.campaign.xp == 0

    def test_campaign_history_preserved_across_snapshot(self, stub_engine: None) -> None:
        """campaign_history is not in snapshot — it persists across turn undo."""
        from straightjacket.engine.models_story import ChapterSummary

        game = _game()
        game.campaign.campaign_history.append(ChapterSummary(summary="Chapter 1"))
        snap = game.campaign.snapshot()
        game.campaign.campaign_history.append(ChapterSummary(summary="Chapter 2"))
        game.campaign.restore(snap)
        # History was not in snapshot, so restore doesn't touch it
        assert len(game.campaign.campaign_history) == 2


class TestLegacyTrackType:
    def test_legacy_tracks_are_epic_rank(self, stub_engine: None) -> None:
        game = _game()
        assert game.campaign.legacy_quests.rank == "epic"
        assert game.campaign.legacy_bonds.rank == "epic"
        assert game.campaign.legacy_discoveries.rank == "epic"

    def test_legacy_tracks_have_correct_type(self, stub_engine: None) -> None:
        game = _game()
        assert game.campaign.legacy_quests.track_type == "legacy"
        assert game.campaign.legacy_bonds.track_type == "legacy"
        assert game.campaign.legacy_discoveries.track_type == "legacy"

    def test_get_legacy_track_returns_campaign_instance(self, stub_engine: None) -> None:
        from straightjacket.engine.mechanics.legacy import get_legacy_track

        game = _game()
        track = get_legacy_track(game, "quests")
        assert track is game.campaign.legacy_quests


class TestSharedProgressAndLegacyHelper:
    """apply_progress_and_legacy must consume both progress_marks and legacy_track
    from a resolved outcome. Shared by turn/correction/momentum burn to keep
    re-resolved scenes from silently dropping progress."""

    def test_helper_consumes_legacy_track(self, stub_engine: None) -> None:
        from straightjacket.engine.game.finalization import apply_progress_and_legacy
        from straightjacket.engine.mechanics.move_effects import OutcomeResult

        game = _game()
        outcome = OutcomeResult(legacy_track="quests")
        brain = make_brain_result(move="quest/fulfill_your_vow")
        apply_progress_and_legacy(game, outcome, brain, "vow", "dangerous")
        assert game.campaign.legacy_quests.ticks == 2

    def test_helper_consumes_progress_marks(self, stub_engine: None) -> None:
        from straightjacket.engine.game.finalization import apply_progress_and_legacy
        from straightjacket.engine.mechanics.move_effects import OutcomeResult

        game = _game()
        game.progress_tracks.append(
            make_progress_track(id="t1", name="Vow to Ally", track_type="vow", rank="dangerous")
        )
        outcome = OutcomeResult(progress_marks=1)
        brain = make_brain_result(move="exploration/undertake_an_expedition")
        apply_progress_and_legacy(game, outcome, brain, "vow", "dangerous")
        assert game.progress_tracks[0].ticks == 8  # dangerous = 8 ticks per mark

    def test_helper_handles_both_in_one_outcome(self, stub_engine: None) -> None:
        from straightjacket.engine.game.finalization import apply_progress_and_legacy
        from straightjacket.engine.mechanics.move_effects import OutcomeResult

        game = _game()
        outcome = OutcomeResult(progress_marks=0, legacy_track="bonds")
        brain = make_brain_result(move="connection/develop_your_relationship")
        apply_progress_and_legacy(game, outcome, brain, "vow", "formidable")
        assert game.campaign.legacy_bonds.ticks == 4  # formidable = 4 ticks

    def test_helper_noop_on_empty_outcome(self, stub_engine: None) -> None:
        from straightjacket.engine.game.finalization import apply_progress_and_legacy
        from straightjacket.engine.mechanics.move_effects import OutcomeResult

        game = _game()
        outcome = OutcomeResult()
        brain = make_brain_result(move="quest/swear_an_iron_vow")
        apply_progress_and_legacy(game, outcome, brain, "vow", "dangerous")
        assert game.campaign.legacy_quests.ticks == 0
        assert game.campaign.xp == 0


class TestChapterPersistence:
    """Legacy tracks and XP must survive chapter transitions (step 12 ↔ step 13)."""

    def test_reset_chapter_preserves_xp(self, stub_engine: None) -> None:
        from straightjacket.engine.game.chapters import _reset_chapter_mechanics

        game = _game()
        game.campaign.xp = 10
        game.campaign.xp_spent = 4
        _reset_chapter_mechanics(game)
        assert game.campaign.xp == 10
        assert game.campaign.xp_spent == 4
        assert game.campaign.xp_available == 6

    def test_reset_chapter_preserves_legacy_tracks(self, stub_engine: None) -> None:
        from straightjacket.engine.game.chapters import _reset_chapter_mechanics
        from straightjacket.engine.mechanics.legacy import mark_legacy

        game = _game()
        mark_legacy(game, "quests", "epic")  # 12 ticks = 3 boxes
        mark_legacy(game, "bonds", "formidable")  # 4 ticks = 1 box
        _reset_chapter_mechanics(game)
        assert game.campaign.legacy_quests.filled_boxes == 3
        assert game.campaign.legacy_bonds.filled_boxes == 1
        assert game.campaign.legacy_discoveries.filled_boxes == 0
