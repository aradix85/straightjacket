#!/usr/bin/env python3
"""Tests for parse_narrator_response cleanup pipeline.

Each test targets a specific cleanup step in the parser. Step numbers
match the comments in parser.py for traceability.

Run: python -m pytest tests/test_parser.py -v
"""

from straightjacket.engine.models import GameState


def _game() -> GameState:
    game = GameState(player_name="Hero")
    game.narrative.scene_count = 3
    game.world.current_location = "Tavern"
    return game


# ── Step 0: Role prefix stripping ────────────────────────────


def test_strips_narrator_prefix(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "Narrator: The wind howled through the broken windows."
    result = parse_narrator_response(game, raw)
    assert not result.startswith("Narrator:")
    assert "wind howled" in result


def test_strips_memory_updates_xml(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = 'The door creaked open.\n<memory_updates>[{"npc_id": "npc_1", "event": "test"}]</memory_updates>'
    result = parse_narrator_response(game, raw)
    assert "<memory_updates>" not in result
    assert "npc_id" not in result
    assert "door creaked" in result


def test_strips_scene_context_xml(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "The fire crackled.\n<scene_context>Player is in tavern</scene_context>"
    result = parse_narrator_response(game, raw)
    assert "<scene_context>" not in result


def test_strips_prompt_echo_tags(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = '<task>Write a scene</task>The tavern was quiet.\n<world genre="fantasy">Medieval</world>'
    result = parse_narrator_response(game, raw)
    assert "<task>" not in result
    assert "<world" not in result
    assert "tavern was quiet" in result


# ── Step 3: Code fence stripping ─────────────────────────────


def test_strips_code_fences(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = 'The night was dark.\n```json\n{"scene_context": "dark"}\n```'
    result = parse_narrator_response(game, raw)
    assert "```" not in result
    assert "scene_context" not in result
    assert "night was dark" in result


# ── Step 4: Leaked JSON stripping ────────────────────────────


def test_strips_leaked_json_array(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = 'The sword gleamed.\n[{"npc_id": "npc_1", "event": "saw player", "emotional_weight": "neutral"}]'
    result = parse_narrator_response(game, raw)
    assert "npc_id" not in result
    assert "sword gleamed" in result


def test_strips_leaked_json_object(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = 'The rain fell.\n{"scene_context": "rainy day", "location": "street"}'
    result = parse_narrator_response(game, raw)
    assert "scene_context" not in result


# ── Step 5: Bracket-format metadata labels ───────────────────


def test_strips_bracket_metadata_labels(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "The wind howled.\n[MEMORY UPDATES] npc_1 saw something"
    result = parse_narrator_response(game, raw)
    assert "[MEMORY" not in result


# ── Step 6: Markdown metadata labels ─────────────────────────


def test_strips_markdown_metadata(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "The door opened slowly.\n\n**Scene Context:** The player enters the room."
    result = parse_narrator_response(game, raw)
    assert "Scene Context" not in result
    assert "door opened" in result


# ── Step 7.5: Bold-bracket game mechanic annotations ─────────


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


# ── Step 8: Markdown artifacts ───────────────────────────────


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


# ── Step 8.5: Em-dash normalization ──────────────────────────


def test_marks_npc_introduced_when_name_in_narration(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response
    from straightjacket.engine.models import NpcData

    game = _game()
    game.npcs = [NpcData(id="npc_1", name="Mira Ashwood", introduced=False)]
    raw = "Mira Ashwood stood by the window, watching the rain."
    parse_narrator_response(game, raw)
    assert game.npcs[0].introduced is True


def test_marks_npc_introduced_by_partial_name(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response
    from straightjacket.engine.models import NpcData

    game = _game()
    game.npcs = [NpcData(id="npc_1", name="Captain Ashwood", introduced=False)]
    raw = "Ashwood nodded slowly, his hand on the hilt."
    parse_narrator_response(game, raw)
    assert game.npcs[0].introduced is True


def test_does_not_mark_introduced_by_title_alone(load_engine: None, stub_emotions: None) -> None:
    """Titles like 'Captain' shouldn't trigger introduction on their own."""
    from straightjacket.engine.parser import parse_narrator_response
    from straightjacket.engine.models import NpcData

    game = _game()
    game.npcs = [NpcData(id="npc_1", name="Captain Jo", introduced=False)]
    raw = "The captain surveyed the field."  # generic "captain", not the name
    parse_narrator_response(game, raw)
    # "captain" matches the title filter in NAME_TITLES, and "jo" is only 2 chars
    assert game.npcs[0].introduced is False


# ── Edge case: empty narration fallback ──────────────────────


def test_empty_narration_returns_fallback(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = '<game_data>{"npcs": []}</game_data>'
    result = parse_narrator_response(game, raw)
    assert len(result) > 0  # should not be empty


# ── Combined: multiple cleanup steps in one response ─────────


def test_combined_cleanup(load_engine: None, stub_emotions: None) -> None:
    """Real-world scenario: narrator leaks multiple metadata formats."""
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = (
        "Narrator: The tavern was warm.\n\n"
        "She poured a drink \u2014 strong and bitter.\n\n"
        "**[SCENE CONTEXT: warm tavern]**\n"
        '<memory_updates>[{"npc_id": "npc_1", "event": "served drink"}]</memory_updates>\n'
        '```json\n{"location": "tavern"}\n```'
    )
    result = parse_narrator_response(game, raw)
    assert "Narrator:" not in result
    assert "\u2014" in result  # em-dashes preserved
    assert "SCENE CONTEXT" not in result
    assert "<memory_updates>" not in result
    assert "```" not in result
    assert "tavern was warm" in result
    assert "poured a drink" in result


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])


# ── Step 1.5: Untagged game_data JSON ────────────────────────


def test_strips_untagged_game_data_json(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = (
        "The stranger entered the room.\n\n"
        '{"npcs": [{"name": "Stranger", "description": "Tall figure"}], '
        '"clocks": [], "location": "Tavern"}'
    )
    result = parse_narrator_response(game, raw)
    assert '"npcs"' not in result
    assert "stranger entered" in result


# ── Step 7: Trailing JSON lines ──────────────────────────────


def test_strips_trailing_json_lines(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = 'The fire crackled softly.\n{"scene_context": "warm room"}\n[{"npc_id": "npc_1"}]'
    result = parse_narrator_response(game, raw)
    assert "scene_context" not in result
    assert "fire crackled" in result


def test_strips_trailing_metadata_label_lines(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "The wind howled.\n\nScene Context: The player is outside in the storm."
    result = parse_narrator_response(game, raw)
    assert "Scene Context:" not in result
    assert "wind howled" in result


# ── Clean prose regression: no false positives ───────────────
