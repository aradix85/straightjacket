from straightjacket.engine.models import SceneLogEntry
from tests._helpers import make_brain_result, make_clock, make_game_state, make_npc, make_progress_track


def test_position_default_risky(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_position

    game = make_game_state(player_name="Test")
    game.world.chaos_factor = 5
    brain = make_brain_result(move="adventure/face_danger", stat="wits")
    assert resolve_position(game, brain) == "risky"


def test_position_desperate_on_low_resources(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_position

    game = make_game_state(player_name="Test")
    game.resources.health = 1
    game.resources.spirit = 1
    game.resources.supply = 1
    game.world.chaos_factor = 5
    brain = make_brain_result(move="adventure/face_danger", stat="wits")
    assert resolve_position(game, brain) == "desperate"


def test_position_controlled_on_high_resources_low_chaos(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_position

    game = make_game_state(player_name="Test")
    game.resources.health = 5
    game.resources.spirit = 5
    game.resources.supply = 5
    game.world.chaos_factor = 3

    game.narrative.session_log.append(
        SceneLogEntry(scene=1, move="secure_advantage", result="STRONG_HIT", scene_type="expected")
    )
    brain = make_brain_result(move="adventure/gather_information", stat="wits")
    assert resolve_position(game, brain) == "controlled"


def test_position_hostile_npc_pushes_desperate(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_position

    game = make_game_state(player_name="Test")
    game.resources.health = 3
    game.resources.spirit = 3
    game.resources.supply = 3
    game.world.chaos_factor = 7
    game.npcs = [make_npc(id="npc_1", name="Enemy", disposition="hostile")]
    brain = make_brain_result(move="adventure/compel", stat="heart", target_npc="npc_1")
    pos = resolve_position(game, brain)
    assert pos == "desperate"


def test_position_friendly_npc_helps(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_position

    game = make_game_state(player_name="Test")
    game.resources.health = 5
    game.resources.spirit = 5
    game.resources.supply = 5
    game.world.chaos_factor = 5
    game.npcs = [make_npc(id="npc_1", name="Ally", disposition="friendly")]
    game.progress_tracks.append(
        make_progress_track(id="connection_npc_1", name="Ally", track_type="connection", rank="dangerous", ticks=12)
    )
    brain = make_brain_result(move="adventure/compel", stat="heart", target_npc="npc_1")
    pos = resolve_position(game, brain)
    assert pos in ("risky", "controlled")


def test_position_consecutive_misses(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_position

    game = make_game_state(player_name="Test")
    game.world.chaos_factor = 5
    game.narrative.session_log = [
        SceneLogEntry(scene=1, move="adventure/face_danger", result="MISS", scene_type="expected"),
        SceneLogEntry(scene=2, move="combat/clash", result="MISS", scene_type="expected"),
    ]
    brain = make_brain_result(move="adventure/face_danger", stat="wits")
    pos = resolve_position(game, brain)

    assert pos in ("desperate", "risky")


def test_position_threat_clock_pressure(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_position

    game = make_game_state(player_name="Test")
    game.world.chaos_factor = 5
    game.world.clocks = [make_clock(name="Doom", segments=4, filled=3)]
    brain = make_brain_result(move="adventure/face_danger", stat="wits")
    pos = resolve_position(game, brain)
    assert pos in ("desperate", "risky")


def test_position_combat_baseline(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_position

    game = make_game_state(player_name="Test")
    game.world.chaos_factor = 5
    brain_combat = make_brain_result(move="combat/clash", stat="iron")
    brain_recovery = make_brain_result(move="recover/resupply", stat="wits")
    pos_combat = resolve_position(game, brain_combat)
    pos_recovery = resolve_position(game, brain_recovery)

    assert pos_combat != "controlled" or pos_recovery == "controlled"


def test_effect_default_standard(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_effect

    game = make_game_state(player_name="Test")
    brain = make_brain_result(move="adventure/face_danger", stat="wits")
    assert resolve_effect(game, brain, "risky") == "standard"


def test_effect_desperate_pushes_limited(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_effect

    game = make_game_state(player_name="Test")
    game.npcs = [make_npc(id="npc_1", name="Enemy", disposition="hostile")]
    brain = make_brain_result(move="adventure/compel", stat="heart", target_npc="npc_1")
    effect = resolve_effect(game, brain, "desperate")
    assert effect in ("limited", "standard")


def test_effect_controlled_pushes_great(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_effect

    game = make_game_state(player_name="Test")
    game.npcs = [make_npc(id="npc_1", name="Ally", disposition="friendly")]
    game.progress_tracks.append(
        make_progress_track(id="connection_npc_1", name="Ally", track_type="connection", rank="dangerous", ticks=12)
    )

    game.narrative.session_log.append(
        SceneLogEntry(scene=1, move="secure_advantage", result="STRONG_HIT", scene_type="expected")
    )
    brain = make_brain_result(move="combat/strike", stat="iron", target_npc="npc_1")
    effect = resolve_effect(game, brain, "controlled")
    assert effect == "great"


def test_effect_strike_baseline(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_effect

    game = make_game_state(player_name="Test")
    brain = make_brain_result(move="combat/strike", stat="iron")
    effect = resolve_effect(game, brain, "risky")

    assert effect in ("standard", "great")


def test_time_progression_dialog_is_none(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_time_progression

    assert resolve_time_progression("dialog") == "none"


def test_time_progression_gather_is_short(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_time_progression

    assert resolve_time_progression("adventure/gather_information") == "short"


def test_time_progression_resupply_is_moderate(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_time_progression

    assert resolve_time_progression("recover/resupply") == "moderate"


def test_time_progression_location_change_is_long(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_time_progression

    assert resolve_time_progression("adventure/face_danger", has_location_change=True) == "long"


def test_time_progression_unknown_move_uses_default(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_time_progression

    assert resolve_time_progression("unknown_move") == "short"


def test_locations_match_identical() -> None:
    from straightjacket.engine.mechanics import locations_match

    assert locations_match("Tavern", "Tavern")


def test_locations_match_case_insensitive() -> None:
    from straightjacket.engine.mechanics import locations_match

    assert locations_match("Old Tavern", "old tavern")


def test_locations_match_stopwords() -> None:
    from straightjacket.engine.mechanics import locations_match

    assert locations_match("the dark forest", "dark forest")


def test_locations_match_subset() -> None:
    from straightjacket.engine.mechanics import locations_match

    assert locations_match("market square", "the old market square")


def test_locations_match_different() -> None:
    from straightjacket.engine.mechanics import locations_match

    assert not locations_match("tavern", "castle")


def test_locations_match_empty() -> None:
    from straightjacket.engine.mechanics import locations_match

    assert locations_match("", "anywhere")
    assert locations_match("anywhere", "")


def test_locations_match_underscore() -> None:
    from straightjacket.engine.mechanics import locations_match

    assert locations_match("dark_forest", "dark forest")
