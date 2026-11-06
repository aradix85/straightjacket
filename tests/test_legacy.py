from __future__ import annotations

import pytest

from straightjacket.engine.models import GameState, ProgressTrack
from straightjacket.engine.ruleset.assets import enabled_abilities
from straightjacket.engine.ruleset.legacy import advance_asset, apply_threat_overcome_bonus, mark_legacy, new_campaign
from straightjacket.engine.ruleset.progress import filled_boxes
from straightjacket.engine.ruleset.tracks import apply_progress_and_legacy
from tests._helpers import (
    make_brain_result,
    make_chapter_summary,
    make_game_state,
    make_outcome,
    make_progress_track,
    make_threat,
)


def _game() -> GameState:
    return make_game_state(player_name="Hero", setting_id="starforged")


class TestMarkLegacy:
    @staticmethod
    def test_mark_dangerous_adds_2_ticks() -> None:
        game = _game()
        mark_legacy(game, "quests", "dangerous")
        assert game.campaign.legacy["quests"].ticks == 2

    @staticmethod
    def test_mark_formidable_adds_4_ticks() -> None:
        game = _game()
        mark_legacy(game, "quests", "formidable")
        assert game.campaign.legacy["quests"].ticks == 4

    @staticmethod
    def test_mark_unknown_rank_raises() -> None:
        game = _game()
        with pytest.raises(KeyError):
            mark_legacy(game, "quests", "bogus")

    @staticmethod
    def test_mark_unknown_track_raises() -> None:
        game = _game()
        with pytest.raises(KeyError, match="bogus"):
            mark_legacy(game, "bogus", "dangerous")

    @staticmethod
    def test_each_ruleset_keeps_the_legacy_tracks_its_rules_name() -> None:
        assert list(new_campaign("classic").legacy) == ["bonds"]
        assert list(new_campaign("delve").legacy) == ["bonds"]
        assert set(new_campaign("starforged").legacy) == {"quests", "bonds", "discoveries"}
        assert set(new_campaign("sundered_isles").legacy) == {"quests", "bonds", "discoveries"}
        assert new_campaign("classic").legacy["bonds"].id == "legacy_bonds"

    @staticmethod
    def test_the_legacy_tracks_load_back_as_tracks() -> None:
        game = _game()
        game.campaign.legacy["bonds"].ticks = 8
        loaded = GameState.from_dict(game.to_dict()).campaign.legacy
        assert isinstance(loaded["bonds"], ProgressTrack)
        assert loaded["bonds"].ticks == 8

    @staticmethod
    def test_a_legacy_track_earns_experience_only_where_its_rules_say_so() -> None:
        classic = make_game_state(player_name="Hero", setting_id="classic")
        mark_legacy(classic, "bonds", "epic")
        assert filled_boxes(classic.campaign.legacy["bonds"]) == 3
        assert classic.campaign.xp == 0
        starforged = _game()
        mark_legacy(starforged, "bonds", "epic")
        assert starforged.campaign.xp == 6

    @staticmethod
    def test_no_xp_before_box_fills() -> None:
        game = _game()
        mark_legacy(game, "quests", "dangerous")
        assert game.campaign.xp == 0

    @staticmethod
    def test_xp_on_box_cross() -> None:
        game = _game()
        mark_legacy(game, "quests", "dangerous")
        mark_legacy(game, "quests", "dangerous")
        assert game.campaign.xp == 2
        assert filled_boxes(game.campaign.legacy["quests"]) == 1

    @staticmethod
    def test_epic_rank_fills_3_boxes_at_once() -> None:
        game = _game()
        mark_legacy(game, "quests", "epic")
        assert game.campaign.xp == 6
        assert filled_boxes(game.campaign.legacy["quests"]) == 3

    @staticmethod
    def test_full_track_clears_and_continues_at_one_xp_per_box() -> None:
        game = _game()
        game.campaign.legacy["quests"].ticks = 38
        mark_legacy(game, "quests", "epic")
        assert game.campaign.legacy["quests"].ticks == 10
        assert game.campaign.legacy["quests"].completions == 1
        assert game.campaign.xp == 2 + 1 + 1

    @staticmethod
    def test_separate_tracks_independent() -> None:
        game = _game()
        mark_legacy(game, "quests", "formidable")
        mark_legacy(game, "bonds", "dangerous")
        assert filled_boxes(game.campaign.legacy["quests"]) == 1
        assert filled_boxes(game.campaign.legacy["bonds"]) == 0
        assert filled_boxes(game.campaign.legacy["discoveries"]) == 0


class TestAdvanceAsset:
    @staticmethod
    def test_upgrade_spends_xp_on_the_next_ability() -> None:
        game = _game()
        game.paths = ["empath"]
        game.campaign.xp = 5
        before = sum(enabled_abilities(game, "empath"))
        assert advance_asset(game, "empath", "upgrade") is None
        assert game.campaign.xp_spent == 2
        assert game.campaign.xp_available == 3
        assert sum(enabled_abilities(game, "empath")) == before + 1

    @staticmethod
    def test_upgrade_by_another_spelling_lands_on_the_held_id() -> None:
        game = _game()
        game.paths = ["empath"]
        game.campaign.xp = 5
        assert advance_asset(game, "path/empath", "upgrade") is None
        assert list(game.asset_abilities) == ["empath"]

    @staticmethod
    def test_new_asset_costs_more_and_joins_the_assets() -> None:
        game = _game()
        game.campaign.xp = 5
        assert advance_asset(game, "empath", "new") is None
        assert game.campaign.xp_spent == 3
        assert game.assets == ["empath"]

    @staticmethod
    def test_insufficient_xp_is_refused() -> None:
        game = _game()
        game.campaign.xp = 2
        assert advance_asset(game, "empath", "new") == "insufficient"
        assert game.campaign.xp_spent == 0
        assert game.assets == []

    @staticmethod
    def test_an_asset_the_setting_lacks_is_refused() -> None:
        game = _game()
        game.campaign.xp = 10
        assert advance_asset(game, "no_such_asset", "new") == "unknown"
        assert game.campaign.xp_spent == 0
        assert game.assets == []

    @staticmethod
    def test_buying_an_asset_already_held_is_refused() -> None:
        game = _game()
        game.paths = ["empath"]
        game.campaign.xp = 10
        assert advance_asset(game, "path/empath", "new") == "held"
        assert game.campaign.xp_spent == 0
        assert game.assets == []

    @staticmethod
    def test_upgrading_an_asset_not_held_is_refused() -> None:
        game = _game()
        game.campaign.xp = 10
        assert advance_asset(game, "empath", "upgrade") == "not_held"
        assert game.campaign.xp_spent == 0
        assert game.asset_abilities == {}

    @staticmethod
    def test_upgrading_a_fully_upgraded_asset_is_refused() -> None:
        game = _game()
        game.paths = ["empath"]
        game.asset_abilities["empath"] = [True] * len(enabled_abilities(game, "empath"))
        game.campaign.xp = 10
        assert advance_asset(game, "empath", "upgrade") == "fully_upgraded"
        assert game.campaign.xp_spent == 0

    @staticmethod
    def test_an_unknown_kind_of_advance_raises() -> None:
        with pytest.raises(ValueError, match="Unknown advance"):
            advance_asset(_game(), "empath", "sell")


class TestThreatOvercomeBonus:
    @staticmethod
    def test_bonus_at_high_menace() -> None:
        game = _game()
        threat = make_threat(id="t1", name="Foo", menace_ticks=30, max_menace_ticks=40)
        apply_threat_overcome_bonus(game, threat)
        assert game.campaign.xp == 2

    @staticmethod
    def test_no_bonus_below_threshold() -> None:
        game = _game()
        threat = make_threat(id="t1", name="Foo", menace_ticks=10, max_menace_ticks=40)
        apply_threat_overcome_bonus(game, threat)
        assert game.campaign.xp == 0

    @staticmethod
    def test_exactly_at_threshold_grants_bonus() -> None:
        game = _game()
        threat = make_threat(id="t1", name="Foo", menace_ticks=20, max_menace_ticks=40)
        apply_threat_overcome_bonus(game, threat)
        assert game.campaign.xp == 2


class TestCampaignSnapshot:
    @staticmethod
    def test_restore_reverts_earned_experience_and_keeps_what_was_spent() -> None:
        game = _game()
        game.campaign.xp, game.campaign.xp_spent = 7, 2
        snap = game.campaign.snapshot()
        game.campaign.xp, game.campaign.xp_spent = 9, 5
        game.campaign.restore(snap)
        assert (game.campaign.xp, game.campaign.xp_spent) == (7, 5)

    @staticmethod
    def test_restore_reverts_legacy_progress() -> None:
        game = _game()
        snap = game.campaign.snapshot()
        mark_legacy(game, "quests", "epic")
        assert filled_boxes(game.campaign.legacy["quests"]) == 3
        game.campaign.restore(snap)
        assert filled_boxes(game.campaign.legacy["quests"]) == 0
        assert game.campaign.xp == 0

    @staticmethod
    def test_campaign_history_preserved_across_snapshot() -> None:
        game = _game()
        game.campaign.campaign_history.append(make_chapter_summary(summary="Chapter 1"))
        snap = game.campaign.snapshot()
        game.campaign.campaign_history.append(make_chapter_summary(summary="Chapter 2"))
        game.campaign.restore(snap)

        assert len(game.campaign.campaign_history) == 2


class TestLegacyTrackType:
    @staticmethod
    def test_legacy_tracks_are_epic_rank() -> None:
        game = _game()
        assert game.campaign.legacy["quests"].rank == "epic"
        assert game.campaign.legacy["bonds"].rank == "epic"
        assert game.campaign.legacy["discoveries"].rank == "epic"

    @staticmethod
    def test_legacy_tracks_have_correct_type() -> None:
        game = _game()
        assert game.campaign.legacy["quests"].track_type == "legacy"
        assert game.campaign.legacy["bonds"].track_type == "legacy"
        assert game.campaign.legacy["discoveries"].track_type == "legacy"

    @staticmethod
    def test_get_legacy_track_returns_campaign_instance() -> None:
        game = _game()
        track = game.campaign.legacy["quests"]
        assert track is game.campaign.legacy["quests"]


class TestSharedProgressAndLegacyHelper:
    @staticmethod
    def test_helper_consumes_legacy_track() -> None:
        game = _game()
        outcome = make_outcome(legacy_track="quests")
        brain = make_brain_result(move="quest/fulfill_your_vow")
        apply_progress_and_legacy(game, outcome, brain, make_progress_track(rank="dangerous"))
        assert game.campaign.legacy["quests"].ticks == 2

    @staticmethod
    def test_helper_consumes_progress_marks() -> None:
        game = _game()
        game.progress_tracks.append(
            make_progress_track(id="vow_ally", name="Vow to Ally", track_type="vow", rank="dangerous")
        )
        game.progress_tracks.append(
            make_progress_track(id="expedition_ruins", name="The ruins", track_type="expedition", rank="dangerous")
        )
        outcome = make_outcome(progress_marks=1)
        brain = make_brain_result(move="exploration/undertake_an_expedition", target_track="expedition_ruins")
        apply_progress_and_legacy(game, outcome, brain, None)
        assert game.progress_tracks[0].ticks == 0
        assert game.progress_tracks[1].ticks == 8

    @staticmethod
    def test_helper_handles_both_in_one_outcome() -> None:
        game = _game()
        outcome = make_outcome(progress_marks=0, legacy_track="bonds")
        brain = make_brain_result(move="connection/develop_your_relationship")
        apply_progress_and_legacy(game, outcome, brain, make_progress_track(rank="formidable"))
        assert game.campaign.legacy["bonds"].ticks == 4

    @staticmethod
    def test_helper_noop_on_empty_outcome() -> None:
        game = _game()
        outcome = make_outcome()
        brain = make_brain_result(move="quest/swear_an_iron_vow")
        apply_progress_and_legacy(game, outcome, brain, None)
        assert game.campaign.legacy["quests"].ticks == 0
        assert game.campaign.xp == 0

    @staticmethod
    def test_a_legacy_reward_by_rank_without_its_track_raises() -> None:
        outcome = make_outcome(legacy_track="quests")
        brain = make_brain_result(move="quest/fulfill_your_vow")
        with pytest.raises(ValueError, match="needs the progress track"):
            apply_progress_and_legacy(_game(), outcome, brain, None)

    @staticmethod
    def test_progress_marks_from_a_move_without_a_track_category_raise() -> None:
        outcome = make_outcome(progress_marks=1)
        with pytest.raises(KeyError):
            apply_progress_and_legacy(_game(), outcome, make_brain_result(move="world_shaping"), None)
