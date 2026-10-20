import pytest

from straightjacket.engine.gamemaster.config import gm
from tests._helpers import (
    make_brain_result,
    make_clock,
    make_game_state,
    make_npc,
    make_progress_track,
    make_scene_log_entry,
)


def test_position_default_risky(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.resolvers import resolve_position

    game = make_game_state(player_name="Test")
    game.world.chaos_factor = 5
    brain = make_brain_result(move="adventure/face_danger", stat="wits")
    assert resolve_position(game, brain) == "risky"


def test_only_a_nearly_full_threat_clock_presses_the_position(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.resolvers import resolve_position

    game = make_game_state(player_name="Test")
    game.world.chaos_factor = 3
    game.narrative.session_log.append(
        make_scene_log_entry(scene=1, move="adventure/secure_an_advantage", result="STRONG_HIT")
    )
    brain = make_brain_result(move="adventure/gather_information", stat="wits")
    calm = resolve_position(game, brain)
    assert calm == "controlled"
    game.world.clocks = [
        make_clock(name="The bridge", clock_type="progress", segments=6, filled=5),
        make_clock(name="The plan", clock_type="scheme", segments=6, filled=5),
    ]
    assert resolve_position(game, brain) == calm
    game.world.clocks.append(make_clock(name="The flood", clock_type="threat", segments=6, filled=5))
    game.world.clocks.append(make_clock(name="The raid", clock_type="threat", segments=6, filled=5))
    assert resolve_position(game, brain) != calm


def test_position_desperate_on_low_resources(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.resolvers import resolve_position

    game = make_game_state(player_name="Test")
    game.resources.meters["health"] = 1
    game.resources.meters["spirit"] = 1
    game.resources.meters["supply"] = 1
    game.world.chaos_factor = 5
    brain = make_brain_result(move="adventure/face_danger", stat="wits")
    assert resolve_position(game, brain) == "desperate"


def test_position_controlled_on_high_resources_low_chaos(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.resolvers import resolve_position

    game = make_game_state(player_name="Test")
    game.resources.meters["health"] = 5
    game.resources.meters["spirit"] = 5
    game.resources.meters["supply"] = 5
    game.world.chaos_factor = 3

    game.narrative.session_log.append(
        make_scene_log_entry(scene=1, move="adventure/secure_an_advantage", result="STRONG_HIT")
    )
    brain = make_brain_result(move="adventure/gather_information", stat="wits")
    assert resolve_position(game, brain) == "controlled"


def test_position_hostile_npc_pushes_desperate(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.resolvers import resolve_position

    game = make_game_state(player_name="Test")
    game.resources.meters["health"] = 3
    game.resources.meters["spirit"] = 3
    game.resources.meters["supply"] = 3
    game.world.chaos_factor = 7
    game.npcs = [make_npc(id="npc_1", name="Enemy", disposition="hostile")]
    brain = make_brain_result(move="adventure/compel", stat="heart", target_npc="npc_1")
    pos = resolve_position(game, brain)
    assert pos == "desperate"


def test_position_friendly_npc_helps(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.resolvers import resolve_position

    game = make_game_state(player_name="Test")
    game.resources.meters["health"] = 5
    game.resources.meters["spirit"] = 5
    game.resources.meters["supply"] = 5
    game.world.chaos_factor = 5
    game.npcs = [make_npc(id="npc_1", name="Ally", disposition="friendly")]
    game.progress_tracks.append(
        make_progress_track(id="connection_npc_1", name="Ally", track_type="connection", rank="dangerous", ticks=12)
    )
    brain = make_brain_result(move="adventure/compel", stat="heart", target_npc="npc_1")
    pos = resolve_position(game, brain)
    assert pos in ("risky", "controlled")


def test_position_consecutive_misses(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.resolvers import resolve_position

    game = make_game_state(player_name="Test")
    game.world.chaos_factor = 5
    game.narrative.session_log = [
        make_scene_log_entry(scene=1, move="adventure/face_danger", result="MISS"),
        make_scene_log_entry(scene=2, move="combat/clash", result="MISS"),
    ]
    brain = make_brain_result(move="adventure/face_danger", stat="wits")
    pos = resolve_position(game, brain)

    assert pos in ("desperate", "risky")


def test_position_threat_clock_pressure(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.resolvers import resolve_position

    game = make_game_state(player_name="Test")
    game.world.chaos_factor = 5
    game.world.clocks = [make_clock(name="Doom", segments=4, filled=3)]
    brain = make_brain_result(move="adventure/face_danger", stat="wits")
    pos = resolve_position(game, brain)
    assert pos in ("desperate", "risky")


def test_position_combat_baseline(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.resolvers import resolve_position

    game = make_game_state(player_name="Test")
    game.world.chaos_factor = 5
    brain_combat = make_brain_result(move="combat/clash", stat="iron")
    brain_recovery = make_brain_result(move="recover/resupply", stat="wits")
    pos_combat = resolve_position(game, brain_combat)
    pos_recovery = resolve_position(game, brain_recovery)

    assert pos_combat != "controlled" or pos_recovery == "controlled"


@pytest.mark.parametrize("setting", ["classic", "delve", "starforged", "sundered_isles"])
def test_every_move_that_rolls_has_a_position(load_engine: None, setting: str) -> None:
    from straightjacket.engine.gamemaster.resolvers import resolve_position
    from straightjacket.engine.ruleset.config import rules
    from straightjacket.engine.ruleset.moves import get_moves

    game = make_game_state(player_name="Test", setting_id=setting)
    rolled = [key for key, move in get_moves(setting).items() if move.is_action_roll or move.is_progress_roll]
    for key in [*rolled, *rules().engine_moves]:
        position = resolve_position(game, make_brain_result(move=key, stat="iron"))
        assert position in gm().clocks.miss_ticks_by_position, key


def test_effect_default_standard(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.resolvers import resolve_effect

    game = make_game_state(player_name="Test")
    brain = make_brain_result(move="adventure/face_danger", stat="wits")
    assert resolve_effect(game, brain, "risky") == "standard"


def test_effect_desperate_pushes_limited(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.resolvers import resolve_effect

    game = make_game_state(player_name="Test")
    game.npcs = [make_npc(id="npc_1", name="Enemy", disposition="hostile")]
    brain = make_brain_result(move="adventure/compel", stat="heart", target_npc="npc_1")
    effect = resolve_effect(game, brain, "desperate")
    assert effect in ("limited", "standard")


def test_effect_controlled_pushes_great(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.resolvers import resolve_effect

    game = make_game_state(player_name="Test")
    game.npcs = [make_npc(id="npc_1", name="Ally", disposition="friendly")]
    game.progress_tracks.append(
        make_progress_track(id="connection_npc_1", name="Ally", track_type="connection", rank="dangerous", ticks=12)
    )

    game.narrative.session_log.append(
        make_scene_log_entry(scene=1, move="adventure/secure_an_advantage", result="STRONG_HIT")
    )
    brain = make_brain_result(move="combat/strike", stat="iron", target_npc="npc_1")
    effect = resolve_effect(game, brain, "controlled")
    assert effect == "great"


def test_effect_strike_baseline(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.resolvers import resolve_effect

    game = make_game_state(player_name="Test")
    brain = make_brain_result(move="combat/strike", stat="iron")
    effect = resolve_effect(game, brain, "risky")

    assert effect in ("standard", "great")


def test_time_progression_dialog_is_none(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.world import resolve_time_progression

    assert resolve_time_progression("dialog", has_location_change=False) == "none"


def test_the_game_master_s_own_moves_take_its_own_time(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.config import gm
    from straightjacket.engine.gamemaster.world import resolve_time_progression

    for move, spec in gm().moves.items():
        assert resolve_time_progression(move, has_location_change=False) == spec.time


def test_time_progression_gather_is_short(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.world import resolve_time_progression

    assert resolve_time_progression("adventure/gather_information", has_location_change=False) == "short"


def test_time_progression_resupply_is_moderate(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.world import resolve_time_progression

    assert resolve_time_progression("recover/resupply", has_location_change=False) == "moderate"


def test_time_progression_location_change_is_long(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.world import resolve_time_progression

    assert resolve_time_progression("adventure/face_danger", has_location_change=True) == "long"


def test_time_progression_unknown_move_uses_default(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.world import resolve_time_progression

    assert resolve_time_progression("unknown_move", has_location_change=False) == "short"


def test_locations_match_identical() -> None:
    from straightjacket.engine.gamemaster.world import locations_match

    assert locations_match("Tavern", "Tavern")


def test_locations_match_case_insensitive() -> None:
    from straightjacket.engine.gamemaster.world import locations_match

    assert locations_match("Old Tavern", "old tavern")


def test_locations_match_stopwords() -> None:
    from straightjacket.engine.gamemaster.world import locations_match

    assert locations_match("the dark forest", "dark forest")


def test_locations_match_subset() -> None:
    from straightjacket.engine.gamemaster.world import locations_match

    assert locations_match("market square", "the old market square")


def test_locations_match_different() -> None:
    from straightjacket.engine.gamemaster.world import locations_match

    assert not locations_match("tavern", "castle")


def test_locations_match_empty() -> None:
    from straightjacket.engine.gamemaster.world import locations_match

    assert locations_match("", "anywhere")
    assert locations_match("anywhere", "")


def test_locations_match_underscore() -> None:
    from straightjacket.engine.gamemaster.world import locations_match

    assert locations_match("dark_forest", "dark forest")
