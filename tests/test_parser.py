import pytest

from straightjacket.engine.ai.provider_base import AIUnavailableError
from straightjacket.engine.models import GameState
from tests._helpers import make_game_state, make_npc


def _game() -> GameState:
    game = make_game_state(player_name="Hero")
    game.narrative.scene_count = 3
    game.world.current_location = "Tavern"
    return game


def test_strips_narrator_prefix(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "Narrator: The wind howled through the broken windows."
    result = parse_narrator_response(game, raw)
    assert not result.startswith("Narrator:")
    assert "wind howled" in result


def test_strips_prompt_echo_tags(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = '<task>Write a scene</task>The tavern was quiet.\n<world genre="fantasy">Medieval</world>'
    result = parse_narrator_response(game, raw)
    assert "<task>" not in result
    assert "<world" not in result
    assert "tavern was quiet" in result


def test_strips_code_fences(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = 'The night was dark.\n```json\n{"scene_context": "dark"}\n```'
    result = parse_narrator_response(game, raw)
    assert "```" not in result
    assert "scene_context" not in result
    assert "night was dark" in result


def test_strips_bold_bracket_annotations(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "The blade struck true.\n**[CLOCK CREATED: Shadow Rising 0/6]**"
    result = parse_narrator_response(game, raw)
    assert "CLOCK CREATED" not in result
    assert "blade struck" in result


def test_strips_uppercase_bracket_annotations(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "She ran.\n[THREAT: rising danger]\n[SCENE CONTEXT: dark alley]"
    result = parse_narrator_response(game, raw)
    assert "[THREAT" not in result
    assert "[SCENE CONTEXT" not in result


def test_strips_markdown_bold_italic(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "She said **hello** and *smiled* at the ***stranger***."
    result = parse_narrator_response(game, raw)
    assert "**" not in result
    assert "*stranger*" not in result
    assert "hello" in result
    assert "smiled" in result


def test_strips_horizontal_rules(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "The scene ended.\n\n---\n\nA new beginning."
    result = parse_narrator_response(game, raw)
    assert "---" not in result


def test_marks_npc_introduced_when_name_in_narration(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    game.npcs = [make_npc(id="npc_1", name="Mira Ashwood", introduced=False)]
    raw = "Mira Ashwood stood by the window, watching the rain."
    parse_narrator_response(game, raw)
    assert game.npcs[0].introduced is True


def test_marks_npc_introduced_by_partial_name(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    game.npcs = [make_npc(id="npc_1", name="Captain Ashwood", introduced=False)]
    raw = "Ashwood nodded slowly, his hand on the hilt."
    parse_narrator_response(game, raw)
    assert game.npcs[0].introduced is True


def test_does_not_mark_introduced_by_title_alone(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    game.npcs = [make_npc(id="npc_1", name="Captain Jo", introduced=False)]
    raw = "The captain surveyed the field."
    parse_narrator_response(game, raw)

    assert game.npcs[0].introduced is False


def test_narration_without_prose_fails_like_an_empty_narration(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = '```json\n{"location": "a dark room"}\n```\n**[SCENE CONTEXT: a dark room]**'
    with pytest.raises(AIUnavailableError, match="empty narration after cleanup"):
        parse_narrator_response(game, raw)


def test_combined_cleanup(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = (
        "Narrator: The tavern was warm.\n\n"
        "She poured a drink \u2014 strong and bitter.\n\n"
        "**[SCENE CONTEXT: warm tavern]**\n"
        '```json\n{"location": "tavern"}\n```'
    )
    result = parse_narrator_response(game, raw)
    assert "Narrator:" not in result
    assert "\u2014" in result
    assert "SCENE CONTEXT" not in result
    assert "```" not in result
    assert "tavern was warm" in result
    assert "poured a drink" in result


def test_a_complete_narration_ending_in_a_stray_fence_keeps_every_sentence(load_engine: None) -> None:
    from straightjacket.engine.game.finalization import narrate_scene
    from tests._mocks import MockProvider

    raw = "The gate held against the storm all night. She turned away from it.\n```"
    narration = narrate_scene(MockProvider(response_content=raw), make_game_state(setting_id="starforged"), "<scene/>")
    assert narration == "The gate held against the storm all night. She turned away from it."


def test_salvage_clean_text() -> None:
    from straightjacket.engine.parser import salvage_truncated_narration

    text = "The door opened. She stepped inside."
    assert salvage_truncated_narration(text) == text


def test_salvage_keeps_a_cut_that_ends_on_a_closing_quote() -> None:
    from straightjacket.engine.parser import salvage_truncated_narration

    text = 'The door opened. "Stay back," she said. "Not one step."'
    assert salvage_truncated_narration(text) == text


def test_salvage_trims_mid_word() -> None:
    from straightjacket.engine.parser import salvage_truncated_narration

    text = "The door opened. She stepped inside. The light was fadi"
    result = salvage_truncated_narration(text)
    assert result.endswith("inside.")


def test_salvage_leaves_a_short_cut_whole() -> None:
    from straightjacket.engine.parser import salvage_truncated_narration

    text = "She ran. The light was fadi"
    assert salvage_truncated_narration(text) == text
