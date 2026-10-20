from straightjacket.engine.models import GameState
from tests._helpers import make_act, make_blueprint, make_game_state, make_npc, make_scene_log_entry
from tests._mocks import MockProvider


def _game() -> GameState:
    game = make_game_state(
        player_name="Aria",
        character_concept="exiled archivist",
        setting_genre="dark_fantasy",
        setting_tone="serious",
        setting_description="A grim world.",
        backstory="She fled the temple.",
    )
    game.world.current_location = "Tavern"
    game.world.current_scene_context = "Quiet morning."
    return game


def test_a_recap_is_asked_with_the_story_so_far_and_returns_the_answer(load_engine: None) -> None:
    from straightjacket.engine.ai.recap import call_recap

    game = _game()
    game.narrative.story_blueprint = make_blueprint(
        central_conflict="x",
        acts=[make_act(phase="setup", title="Act 1", goal="g", mood="tense", transition_trigger="trigger")],
    )
    game.narrative.scene_count = 3
    game.npcs = [make_npc(id="npc_1", name="Kira", disposition="friendly", status="active", introduced=True)]
    game.narrative.session_log = [
        make_scene_log_entry(scene=1, summary="Met Kira", move="adventure/face_danger", result="STRONG_HIT")
    ]
    provider = MockProvider("Last time, Aria fled.")

    assert call_recap(provider, game) == "Last time, Aria fled."
    [call] = provider.calls
    request = call["messages"][0]["content"]
    for told in ("Aria", "Tavern", "Quiet morning.", "Kira", "Met Kira", "setup"):
        assert told in request


def test_a_failed_recap_falls_back_to_the_engines_text(load_engine: None) -> None:
    from straightjacket.engine.ai.recap import call_recap
    from straightjacket.engine.engine_loader import eng

    game = _game()
    fallback = eng().ai_text.narrator_defaults["recap_fallback"].format(player_name=game.player_name)
    assert call_recap(MockProvider(fail=True), game) == fallback
