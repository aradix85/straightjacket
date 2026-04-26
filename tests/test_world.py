from tests._helpers import make_brain_result, make_game_state, make_npc


def test_update_chaos_factor_miss_increases(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import update_chaos_factor

    g = make_game_state()
    g.world.chaos_factor = 5
    update_chaos_factor(g, "MISS")
    assert g.world.chaos_factor > 5


def test_update_chaos_factor_strong_hit_decreases(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import update_chaos_factor

    g = make_game_state()
    g.world.chaos_factor = 5
    update_chaos_factor(g, "STRONG_HIT")
    assert g.world.chaos_factor < 5


def test_update_chaos_factor_dialog_hostile_increases(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import update_chaos_factor

    g = make_game_state()
    g.world.chaos_factor = 5
    g.npcs = [make_npc(id="npc_1", name="Foe", disposition="hostile")]
    update_chaos_factor(g, "dialog", target_npc_id="npc_1")
    assert g.world.chaos_factor >= 5


def test_update_chaos_factor_dialog_friendly_decreases(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import update_chaos_factor

    g = make_game_state()
    g.world.chaos_factor = 5
    g.npcs = [make_npc(id="npc_1", name="Friend", disposition="friendly")]
    update_chaos_factor(g, "dialog", target_npc_id="npc_1")
    assert g.world.chaos_factor <= 5


def test_update_chaos_factor_dialog_neutral_unchanged(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import update_chaos_factor

    g = make_game_state()
    g.world.chaos_factor = 5
    g.npcs = [make_npc(id="npc_1", name="Stranger", disposition="neutral")]
    update_chaos_factor(g, "dialog", target_npc_id="npc_1")
    assert g.world.chaos_factor == 5


def test_update_chaos_factor_dialog_unknown_npc(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import update_chaos_factor

    g = make_game_state()
    g.world.chaos_factor = 5
    update_chaos_factor(g, "dialog", target_npc_id="npc_missing")
    assert g.world.chaos_factor == 5


def test_update_chaos_factor_weak_hit_unchanged(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import update_chaos_factor

    g = make_game_state()
    g.world.chaos_factor = 5
    update_chaos_factor(g, "WEAK_HIT")
    assert g.world.chaos_factor == 5


def test_advance_time_short_progression_noop(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import advance_time

    g = make_game_state()
    g.world.time_of_day = "morning"
    advance_time(g, "short")
    assert g.world.time_of_day == "morning"


def test_advance_time_none_progression_noop(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import advance_time

    g = make_game_state()
    g.world.time_of_day = "morning"
    advance_time(g, "none")
    assert g.world.time_of_day == "morning"


def test_advance_time_no_current_time_noop(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import advance_time

    g = make_game_state()
    g.world.time_of_day = ""
    advance_time(g, "moderate")
    assert g.world.time_of_day == ""


def test_advance_time_unknown_phase_noop(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import advance_time

    g = make_game_state()
    g.world.time_of_day = "tea_time"
    advance_time(g, "moderate")
    assert g.world.time_of_day == "tea_time"


def test_advance_time_moderate_advances(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import advance_time, time_phases

    g = make_game_state()
    phases = time_phases()
    g.world.time_of_day = phases[0]
    advance_time(g, "moderate")
    assert g.world.time_of_day != phases[0]
    assert g.world.time_of_day in phases


def test_advance_time_long_wraps(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import advance_time, time_phases

    g = make_game_state()
    phases = time_phases()
    g.world.time_of_day = phases[-1]
    advance_time(g, "long")
    assert g.world.time_of_day in phases


def test_update_location_sets_initial(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import update_location

    g = make_game_state()
    g.world.current_location = ""
    update_location(g, "Tavern")
    assert g.world.current_location == "Tavern"


def test_update_location_empty_input_noop(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import update_location

    g = make_game_state()
    g.world.current_location = "Tavern"
    update_location(g, "")
    assert g.world.current_location == "Tavern"


def test_update_location_only_underscores_noop(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import update_location

    g = make_game_state()
    g.world.current_location = "Tavern"
    update_location(g, "   ")
    assert g.world.current_location == "Tavern"


def test_update_location_matching_keeps_current(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import update_location

    g = make_game_state()
    g.world.current_location = "Old Tavern"
    update_location(g, "old tavern")
    assert g.world.current_location == "Old Tavern"


def test_update_location_change_archives_history(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import update_location

    g = make_game_state()
    g.world.current_location = "Tavern"
    update_location(g, "Castle")
    assert g.world.current_location == "Castle"
    assert "Tavern" in g.world.location_history


def test_update_location_dedup_consecutive(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import update_location

    g = make_game_state()
    g.world.current_location = "Tavern"
    g.world.location_history = ["Tavern"]
    update_location(g, "Castle")
    assert g.world.location_history.count("Tavern") == 1


def test_update_location_history_capped(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.mechanics.world import update_location

    g = make_game_state()
    cap = eng().location.history_size
    g.world.current_location = "Start"
    for i in range(cap + 5):
        update_location(g, f"Place_{i}")
    assert len(g.world.location_history) <= cap


def test_apply_brain_location_time_with_change(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import apply_brain_location_time

    g = make_game_state()
    g.world.current_location = "Tavern"
    brain = make_brain_result(move="adventure/face_danger", location_change="Castle")
    apply_brain_location_time(g, brain)
    assert g.world.current_location == "Castle"


def test_apply_brain_location_time_null_change(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import apply_brain_location_time

    g = make_game_state()
    g.world.current_location = "Tavern"
    brain = make_brain_result(move="dialog", location_change="null")
    apply_brain_location_time(g, brain)
    assert g.world.current_location == "Tavern"


def test_get_pacing_hint_neutral_when_empty(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import get_pacing_hint

    g = make_game_state()
    g.narrative.scene_intensity_history = []
    assert get_pacing_hint(g) == "neutral"


def test_get_pacing_hint_breather_after_intense_run(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.mechanics.world import get_pacing_hint

    g = make_game_state()
    threshold = eng().pacing.intense_threshold
    g.narrative.scene_intensity_history = ["action"] * threshold
    assert get_pacing_hint(g) == "breather"


def test_get_pacing_hint_action_after_calm_run(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.mechanics.world import get_pacing_hint

    g = make_game_state()
    threshold = eng().pacing.calm_threshold
    g.narrative.scene_intensity_history = ["breather"] * threshold
    assert get_pacing_hint(g) == "action"


def test_get_pacing_hint_neutral_mixed(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import get_pacing_hint

    g = make_game_state()
    g.narrative.scene_intensity_history = ["action", "breather", "action"]
    assert get_pacing_hint(g) == "neutral"


def test_record_scene_intensity_caps_at_window(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.mechanics.world import record_scene_intensity

    g = make_game_state()
    window = eng().pacing.window_size
    for _ in range(window + 5):
        record_scene_intensity(g, "action")
    assert len(g.narrative.scene_intensity_history) == window


def test_choose_story_structure_returns_known(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import choose_story_structure

    result = choose_story_structure("serious")
    assert result in {"kishotenketsu", "3act"}


def test_choose_story_structure_unknown_tone_uses_fallback(load_engine: None) -> None:
    from straightjacket.engine.mechanics.world import choose_story_structure

    result = choose_story_structure("nonsense_tone")
    assert result in {"kishotenketsu", "3act"}
