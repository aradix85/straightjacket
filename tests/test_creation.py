#!/usr/bin/env python3
"""Tests for character creation enhancements: progress tracks, threads, stat validation, chaos modifier.

Run: python -m pytest tests/test_creation.py -v
"""

import pytest

# Stubs are set up in conftest.py

from straightjacket.engine.models import (
    GameState,
    ProgressTrack,
)
from straightjacket.engine.models_base import PROGRESS_RANKS


# ── ProgressTrack ─────────────────────────────────────────────


def test_progress_track_ticks_per_mark() -> None:
    for rank, expected in PROGRESS_RANKS.items():
        t = ProgressTrack(rank=rank)
        assert t.ticks_per_mark == expected


def test_progress_track_mark_progress_troublesome() -> None:
    t = ProgressTrack(rank="troublesome", ticks=0)
    added = t.mark_progress()
    assert added == 12
    assert t.ticks == 12
    assert t.filled_boxes == 3


def test_progress_track_mark_progress_epic() -> None:
    t = ProgressTrack(rank="epic", ticks=0)
    added = t.mark_progress()
    assert added == 1
    assert t.ticks == 1
    assert t.filled_boxes == 0


def test_progress_track_mark_progress_clamps_at_max() -> None:
    t = ProgressTrack(rank="troublesome", ticks=36)
    added = t.mark_progress()
    assert t.ticks == 40
    assert added == 4


def test_progress_track_filled_boxes() -> None:
    t = ProgressTrack(ticks=17)
    assert t.filled_boxes == 4  # 17 // 4


# ── ThreadEntry ───────────────────────────────────────────────


def test_validate_stats_valid(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import validate_stats

    validate_stats({"edge": 3, "heart": 2, "iron": 2, "shadow": 1, "wits": 1})


def test_validate_stats_wrong_sum(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import validate_stats

    with pytest.raises(ValueError, match="must total"):
        validate_stats({"edge": 3, "heart": 2, "iron": 2, "shadow": 1, "wits": 2})  # sums to 10


def test_validate_stats_out_of_range(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import validate_stats

    with pytest.raises(ValueError, match="outside"):
        validate_stats({"edge": 4, "heart": 2, "iron": 2, "shadow": 1, "wits": 0})  # 4 > max 3, sum=9


def test_validate_stats_invalid_array(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import validate_stats

    with pytest.raises(ValueError, match="Invalid stat distribution"):
        validate_stats({"edge": 3, "heart": 3, "iron": 1, "shadow": 1, "wits": 1})  # [3,3,1,1,1] not valid, sum=9


def test_validate_stats_missing_stat(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import validate_stats

    with pytest.raises(ValueError, match="Missing stat"):
        validate_stats({"edge": 3, "heart": 2, "iron": 1, "shadow": 1})


# ── Chaos vow modifier ───────────────────────────────────────


def test_chaos_start_desperate_vow(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import _compute_chaos_start

    result = _compute_chaos_start("I must survive the siege at all costs")
    assert result == 7  # 5 + 2


def test_chaos_start_tense_vow(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import _compute_chaos_start

    result = _compute_chaos_start("I will find my lost sister")
    assert result == 6  # 5 + 1


def test_chaos_start_calm_vow(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import _compute_chaos_start

    result = _compute_chaos_start("I want to explore the uncharted regions")
    assert result == 4  # 5 - 1


def test_chaos_start_no_match(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import _compute_chaos_start

    result = _compute_chaos_start("I seek redemption")
    assert result == 5  # no match, default


def test_chaos_start_empty_vow(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import _compute_chaos_start

    result = _compute_chaos_start("")
    assert result == 5


# ── Vow seeding ──────────────────────────────────────────────


def test_seed_background_vow(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import _seed_background_vow

    game = GameState(player_name="Test")
    _seed_background_vow(game, "Find my sister", "extreme")
    assert len(game.progress_tracks) == 1
    assert game.progress_tracks[0].rank == "extreme"
    assert game.progress_tracks[0].name == "Find my sister"
    assert len(game.narrative.threads) == 1
    assert game.narrative.threads[0].linked_track_id == "vow_background"
    assert game.narrative.threads[0].weight == 2


def test_seed_background_vow_custom_rank(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import _seed_background_vow

    game = GameState(player_name="Test")
    _seed_background_vow(game, "Minor task", "troublesome")
    assert game.progress_tracks[0].rank == "troublesome"


def test_seed_background_vow_invalid_rank_uses_default(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import _seed_background_vow

    game = GameState(player_name="Test")
    _seed_background_vow(game, "Quest", "nonexistent_rank")
    assert game.progress_tracks[0].rank == "extreme"  # default from engine.yaml


def test_seed_background_vow_empty_skips(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import _seed_background_vow

    game = GameState(player_name="Test")
    _seed_background_vow(game, "", "")
    assert len(game.progress_tracks) == 0
    assert len(game.narrative.threads) == 0


# ── Creation flow on settings ────────────────────────────────


def test_setting_creation_flow_starforged() -> None:
    from straightjacket.engine.datasworn.settings import clear_cache, load_package

    clear_cache()
    pkg = load_package("starforged")
    flow = pkg.creation_flow
    assert flow["has_truths"] is True
    assert flow["has_backstory_oracle"] is True
    assert flow["has_name_tables"] is True
    assert flow["has_ship_creation"] is False


def test_setting_creation_flow_classic() -> None:
    from straightjacket.engine.datasworn.settings import clear_cache, load_package

    clear_cache()
    pkg = load_package("classic")
    flow = pkg.creation_flow
    assert flow["has_truths"] is True
    assert flow["has_backstory_oracle"] is False


def test_setting_creation_flow_sundered_isles() -> None:
    from straightjacket.engine.datasworn.settings import clear_cache, load_package

    clear_cache()
    pkg = load_package("sundered_isles")
    flow = pkg.creation_flow
    assert flow["has_ship_creation"] is True


# ── build_creation_options ────────────────────────────────────


def test_build_creation_options_has_stat_constraints(load_engine: None) -> None:
    from straightjacket.web.serializers import build_creation_options

    opts = build_creation_options()
    assert "stat_constraints" in opts
    sc = opts["stat_constraints"]
    assert sc["target_sum"] == 9
    assert sc["min"] == 0
    assert sc["max"] == 3
    assert [3, 2, 2, 1, 1] in sc["valid_arrays"]


def test_build_creation_options_has_creation_defaults(load_engine: None) -> None:
    from straightjacket.web.serializers import build_creation_options

    opts = build_creation_options()
    cd = opts["creation_defaults"]
    assert cd["max_paths"] == 2
    assert cd["background_vow_default_rank"] == "extreme"
    assert "epic" in cd["vow_ranks"]


def test_build_creation_options_settings_have_truths(load_engine: None) -> None:
    from straightjacket.web.serializers import build_creation_options

    opts = build_creation_options()
    sf = next(s for s in opts["settings"] if s["id"] == "starforged")
    assert len(sf["truths"]) > 0
    assert "options" in sf["truths"][0]


def test_build_creation_options_settings_have_backstory(load_engine: None) -> None:
    from straightjacket.web.serializers import build_creation_options

    opts = build_creation_options()
    sf = next(s for s in opts["settings"] if s["id"] == "starforged")
    assert len(sf["backstory_prompts"]) > 0


def test_build_creation_options_settings_have_name_tables(load_engine: None) -> None:
    from straightjacket.web.serializers import build_creation_options

    opts = build_creation_options()
    sf = next(s for s in opts["settings"] if s["id"] == "starforged")
    assert "given" in sf["name_tables"]
    assert len(sf["name_tables"]["given"]) > 0


def test_build_creation_options_settings_have_starting_assets(load_engine: None) -> None:
    from straightjacket.web.serializers import build_creation_options

    opts = build_creation_options()
    sf = next(s for s in opts["settings"] if s["id"] == "starforged")
    assert len(sf["starting_assets"]) > 0
    cats = {a["category"] for a in sf["starting_assets"]}
    assert "companion" in cats


def test_build_creation_options_classic_no_backstory(load_engine: None) -> None:
    from straightjacket.web.serializers import build_creation_options

    opts = build_creation_options()
    cl = next(s for s in opts["settings"] if s["id"] == "classic")
    assert len(cl["backstory_prompts"]) == 0


def test_build_creation_options_has_creation_flow(load_engine: None) -> None:
    from straightjacket.web.serializers import build_creation_options

    opts = build_creation_options()
    sf = next(s for s in opts["settings"] if s["id"] == "starforged")
    assert "creation_flow" in sf
    assert sf["creation_flow"]["has_truths"] is True


# ── Truth thread seeding ──────────────────────────────────────


def test_seed_truth_threads_matches(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import _seed_truth_threads

    game = GameState(player_name="Test", truths={"communities": "Communities are scattered and isolated"})
    _seed_truth_threads(game)
    assert len(game.narrative.threads) == 1
    assert game.narrative.threads[0].thread_type == "tension"
    assert game.narrative.threads[0].source == "creation"


def test_seed_truth_threads_no_match(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import _seed_truth_threads

    game = GameState(player_name="Test", truths={"cataclysm": "Something unique happened"})
    _seed_truth_threads(game)
    assert len(game.narrative.threads) == 0


def test_seed_truth_threads_empty_truths(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import _seed_truth_threads

    game = GameState(player_name="Test")
    _seed_truth_threads(game)
    assert len(game.narrative.threads) == 0


# ── Vow subject seeding ──────────────────────────────────────


def test_seed_vow_subject(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import _seed_vow_subject

    game = GameState(player_name="Test")
    _seed_vow_subject(game, "my lost sister")
    assert len(game.narrative.characters_list) == 1
    assert game.narrative.characters_list[0].name == "my lost sister"
    assert game.narrative.characters_list[0].entry_type == "abstract"
    assert game.narrative.characters_list[0].weight == 2


def test_seed_vow_subject_empty_skips(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import _seed_vow_subject

    game = GameState(player_name="Test")
    _seed_vow_subject(game, "")
    assert len(game.narrative.characters_list) == 0


# ── Truths block in narrator prompt ───────────────────────────


def test_truths_block_with_truths() -> None:
    from straightjacket.engine.prompt_blocks import truths_block

    game = GameState(player_name="Test", truths={"cataclysm": "The Sun Plague", "exodus": "We fled"})
    block = truths_block(game)
    assert "<world_truths>" in block
    assert "The Sun Plague" in block
    assert "We fled" in block


def test_truths_block_empty() -> None:
    from straightjacket.engine.prompt_blocks import truths_block

    game = GameState(player_name="Test")
    assert truths_block(game) == ""


# ── Creation enforcement ──────────────────────────────────────


def test_validate_creation_too_many_paths(load_engine: None) -> None:
    from straightjacket.engine.datasworn.settings import clear_cache, load_package
    from straightjacket.engine.game.game_start import validate_creation

    clear_cache()
    pkg = load_package("starforged")
    with pytest.raises(ValueError, match="Too many paths"):
        validate_creation({"paths": ["a", "b", "c"]}, pkg)


def test_validate_creation_too_many_assets(load_engine: None) -> None:
    from straightjacket.engine.datasworn.settings import clear_cache, load_package
    from straightjacket.engine.game.game_start import validate_creation

    clear_cache()
    pkg = load_package("starforged")
    with pytest.raises(ValueError, match="Too many starting assets"):
        validate_creation({"assets": ["a", "b"]}, pkg)


def test_validate_creation_truths_wrong_setting(load_engine: None) -> None:
    from straightjacket.engine.datasworn.settings import clear_cache, load_package
    from straightjacket.engine.game.game_start import validate_creation

    clear_cache()
    pkg = load_package("delve")
    with pytest.raises(ValueError, match="does not support truths"):
        validate_creation({"truths": {"x": "y"}}, pkg)


def test_validate_creation_valid_passes(load_engine: None) -> None:
    from straightjacket.engine.datasworn.settings import clear_cache, load_package
    from straightjacket.engine.game.game_start import validate_creation

    clear_cache()
    pkg = load_package("starforged")
    validate_creation({"paths": ["ace", "explorer"], "assets": [], "truths": {"x": "y"}}, pkg)


def test_validate_creation_path_not_in_setting(load_engine: None) -> None:
    from straightjacket.engine.datasworn.settings import clear_cache, load_package
    from straightjacket.engine.game.game_start import validate_creation

    clear_cache()
    pkg = load_package("starforged")
    with pytest.raises(ValueError, match="not found in setting"):
        validate_creation({"paths": ["alchemist"]}, pkg)  # Classic path, not Starforged


def test_validate_creation_invalid_vow_rank(load_engine: None) -> None:
    from straightjacket.engine.datasworn.settings import clear_cache, load_package
    from straightjacket.engine.game.game_start import validate_creation

    clear_cache()
    pkg = load_package("starforged")
    with pytest.raises(ValueError, match="Invalid vow rank"):
        validate_creation({"background_vow_rank": "legendary"}, pkg)


def test_validate_creation_valid_vow_rank_passes(load_engine: None) -> None:
    from straightjacket.engine.datasworn.settings import clear_cache, load_package
    from straightjacket.engine.game.game_start import validate_creation

    clear_cache()
    pkg = load_package("starforged")
    validate_creation({"background_vow_rank": "epic"}, pkg)


# ── Memory emotional weight derivation ────────────────────────


def test_derive_memory_emotion_combat_miss(load_engine: None) -> None:
    from straightjacket.engine.mechanics import derive_memory_emotion

    result = derive_memory_emotion("combat/clash", "MISS", "hostile")
    assert result == "fear_pain_hostile"


def test_derive_memory_emotion_social_strong_hit_friendly(load_engine: None) -> None:
    from straightjacket.engine.mechanics import derive_memory_emotion

    result = derive_memory_emotion("adventure/compel", "STRONG_HIT", "friendly")
    assert result == "trusting_open_warm"


def test_derive_memory_emotion_dialog(load_engine: None) -> None:
    from straightjacket.engine.mechanics import derive_memory_emotion

    result = derive_memory_emotion("dialog", "dialog", "neutral")
    assert result == "neutral"


def test_derive_memory_emotion_unknown_move(load_engine: None) -> None:
    from straightjacket.engine.mechanics import derive_memory_emotion

    result = derive_memory_emotion("unknown_move", "MISS", "neutral")
    assert result == "frustrated_setback"


def test_derive_memory_emotion_recovery_strong(load_engine: None) -> None:
    from straightjacket.engine.mechanics import derive_memory_emotion

    result = derive_memory_emotion("suffer/endure_harm", "STRONG_HIT", "loyal")
    # endure_harm is in both endure and recovery categories; endure matches first
    assert "devoted" in result
