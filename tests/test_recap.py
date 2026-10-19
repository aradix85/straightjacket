from tests._helpers import make_act, make_blueprint, make_game_state, make_npc, make_scene_log_entry
from tests._mocks import MockProvider


def _full_game(load_engine: None) -> object:
    g = make_game_state(
        player_name="Aria",
        character_concept="exiled archivist",
        setting_genre="dark_fantasy",
        setting_tone="serious",
        setting_description="A grim world.",
        backstory="She fled the temple.",
    )
    g.world.current_location = "Tavern"
    g.world.current_scene_context = "Quiet morning."
    return g


def test_call_recap_returns_content(load_engine: None) -> None:
    from straightjacket.engine.ai.recap import call_recap

    provider = MockProvider("Last time, Aria fled.")
    g = _full_game(None)
    result = call_recap(provider, g)
    assert result == "Last time, Aria fled."


def test_call_recap_falls_back_on_api_error(load_engine: None) -> None:
    from straightjacket.engine.ai.recap import call_recap

    provider = MockProvider(fail=True)
    g = _full_game(None)
    result = call_recap(provider, g)
    from straightjacket.engine.engine_loader import eng

    fallback = eng().ai_text.narrator_defaults["recap_fallback"].format(player_name=g.player_name)
    assert result == fallback


def test_call_recap_with_arc(load_engine: None) -> None:
    from straightjacket.engine.ai.recap import call_recap

    provider = MockProvider("recap text")
    g = _full_game(None)
    g.narrative.story_blueprint = make_blueprint(
        central_conflict="x",
        antagonist_force="y",
        thematic_thread="z",
        acts=[make_act(title="Act 1", goal="g", mood="tense", transition_trigger="trigger")],
    )
    g.narrative.scene_count = 3
    result = call_recap(provider, g)
    assert result == "recap text"


def test_call_recap_with_active_npcs(load_engine: None) -> None:
    from straightjacket.engine.ai.recap import call_recap

    provider = MockProvider("recap")
    g = _full_game(None)
    g.npcs = [
        make_npc(id="npc_1", name="Kira", disposition="friendly", status="active", introduced=True),
    ]
    result = call_recap(provider, g)
    assert result == "recap"


def test_call_recap_with_session_log(load_engine: None) -> None:
    from straightjacket.engine.ai.recap import call_recap

    provider = MockProvider("recap")
    g = _full_game(None)
    g.narrative.session_log = [
        make_scene_log_entry(scene=1, summary="Met Kira", move="adventure/face_danger", result="STRONG_HIT"),
    ]
    assert call_recap(provider, g) == "recap"
