#!/usr/bin/env python3
"""Tests for parse_narrator_response cleanup pipeline.

Each test targets a specific cleanup step in the parser. Step numbers
match the comments in parser.py for traceability.

Run: python -m pytest tests/test_parser.py -v
"""

from straightjacket.engine import engine_loader
from straightjacket.engine.models import GameState


def _load_engine():
    engine_loader._eng = None
    engine_loader.eng()


def _stub_emotions():
    from straightjacket.engine import emotions_loader

    emotions_loader._data = {
        "importance": {"neutral": 2},
        "keyword_boosts": {},
        "disposition_map": {"neutral": "neutral", "friendly": "friendly"},
    }


def _game() -> GameState:
    game = GameState(player_name="Hero")
    game.narrative.scene_count = 3
    game.world.current_location = "Tavern"
    return game


# ── Step 0: Role prefix stripping ────────────────────────────


def test_strips_narrator_prefix():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "Narrator: The wind howled through the broken windows."
    result = parse_narrator_response(game, raw)
    assert not result.startswith("Narrator:")
    assert "wind howled" in result


def test_strips_narrator_prefix_case_insensitive():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "narrator: Silence fell over the room."
    result = parse_narrator_response(game, raw)
    assert not result.lower().startswith("narrator:")


# ── Step 2: XML metadata tag stripping ───────────────────────


def test_strips_memory_updates_xml():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = 'The door creaked open.\n<memory_updates>[{"npc_id": "npc_1", "event": "test"}]</memory_updates>'
    result = parse_narrator_response(game, raw)
    assert "<memory_updates>" not in result
    assert "npc_id" not in result
    assert "door creaked" in result


def test_strips_scene_context_xml():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "The fire crackled.\n<scene_context>Player is in tavern</scene_context>"
    result = parse_narrator_response(game, raw)
    assert "<scene_context>" not in result


def test_strips_prompt_echo_tags():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = '<task>Write a scene</task>The tavern was quiet.\n<world genre="fantasy">Medieval</world>'
    result = parse_narrator_response(game, raw)
    assert "<task>" not in result
    assert "<world" not in result
    assert "tavern was quiet" in result


# ── Step 3: Code fence stripping ─────────────────────────────


def test_strips_code_fences():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = 'The night was dark.\n```json\n{"scene_context": "dark"}\n```'
    result = parse_narrator_response(game, raw)
    assert "```" not in result
    assert "scene_context" not in result
    assert "night was dark" in result


# ── Step 4: Leaked JSON stripping ────────────────────────────


def test_strips_leaked_json_array():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = 'The sword gleamed.\n[{"npc_id": "npc_1", "event": "saw player", "emotional_weight": "neutral"}]'
    result = parse_narrator_response(game, raw)
    assert "npc_id" not in result
    assert "sword gleamed" in result


def test_strips_leaked_json_object():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = 'The rain fell.\n{"scene_context": "rainy day", "location": "street"}'
    result = parse_narrator_response(game, raw)
    assert "scene_context" not in result


# ── Step 5: Bracket-format metadata labels ───────────────────


def test_strips_bracket_metadata_labels():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "The wind howled.\n[MEMORY UPDATES] npc_1 saw something"
    result = parse_narrator_response(game, raw)
    assert "[MEMORY" not in result


# ── Step 6: Markdown metadata labels ─────────────────────────


def test_strips_markdown_metadata():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "The door opened slowly.\n\n**Scene Context:** The player enters the room."
    result = parse_narrator_response(game, raw)
    assert "Scene Context" not in result
    assert "door opened" in result


# ── Step 7.5: Bold-bracket game mechanic annotations ─────────


def test_strips_bold_bracket_annotations():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "The blade struck true.\n**[CLOCK CREATED: Shadow Rising 0/6]**"
    result = parse_narrator_response(game, raw)
    assert "CLOCK CREATED" not in result
    assert "blade struck" in result


def test_strips_uppercase_bracket_annotations():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "She ran.\n[THREAT: rising danger]\n[SCENE CONTEXT: dark alley]"
    result = parse_narrator_response(game, raw)
    assert "[THREAT" not in result
    assert "[SCENE CONTEXT" not in result


# ── Step 8: Markdown artifacts ───────────────────────────────


def test_strips_markdown_bold_italic():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "She said **hello** and *smiled* at the ***stranger***."
    result = parse_narrator_response(game, raw)
    assert "**" not in result
    assert "*stranger*" not in result
    assert "hello" in result
    assert "smiled" in result


def test_strips_horizontal_rules():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "The scene ended.\n\n---\n\nA new beginning."
    result = parse_narrator_response(game, raw)
    assert "---" not in result


# ── Step 8.5: Em-dash normalization ──────────────────────────


def test_preserves_em_dashes():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "The warrior\u2014battle-scarred and weary\u2014drew his sword."
    result = parse_narrator_response(game, raw)
    assert "\u2014" in result


def test_preserves_en_dashes():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "The path\u2013narrow and treacherous\u2013led upward."
    result = parse_narrator_response(game, raw)
    assert "\u2013" in result


# ── Step 10: NPC introduction marking ────────────────────────


def test_marks_npc_introduced_when_name_in_narration():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response
    from straightjacket.engine.models import NpcData

    game = _game()
    game.npcs = [NpcData(id="npc_1", name="Mira Ashwood", introduced=False)]
    raw = "Mira Ashwood stood by the window, watching the rain."
    parse_narrator_response(game, raw)
    assert game.npcs[0].introduced is True


def test_marks_npc_introduced_by_partial_name():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response
    from straightjacket.engine.models import NpcData

    game = _game()
    game.npcs = [NpcData(id="npc_1", name="Captain Ashwood", introduced=False)]
    raw = "Ashwood nodded slowly, his hand on the hilt."
    parse_narrator_response(game, raw)
    assert game.npcs[0].introduced is True


def test_does_not_mark_introduced_by_title_alone():
    """Titles like 'Captain' shouldn't trigger introduction on their own."""
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response
    from straightjacket.engine.models import NpcData

    game = _game()
    game.npcs = [NpcData(id="npc_1", name="Captain Jo", introduced=False)]
    raw = "The captain surveyed the field."  # generic "captain", not the name
    parse_narrator_response(game, raw)
    # "captain" matches the title filter in NAME_TITLES, and "jo" is only 2 chars
    assert game.npcs[0].introduced is False


# ── Edge case: empty narration fallback ──────────────────────


def test_empty_narration_returns_fallback():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = '<game_data>{"npcs": []}</game_data>'
    result = parse_narrator_response(game, raw)
    assert len(result) > 0  # should not be empty


# ── Combined: multiple cleanup steps in one response ─────────


def test_combined_cleanup():
    """Real-world scenario: narrator leaks multiple metadata formats."""
    _load_engine()
    _stub_emotions()
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


def test_strips_untagged_game_data_json():
    _load_engine()
    _stub_emotions()
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


def test_strips_trailing_json_lines():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = 'The fire crackled softly.\n{"scene_context": "warm room"}\n[{"npc_id": "npc_1"}]'
    result = parse_narrator_response(game, raw)
    assert "scene_context" not in result
    assert "fire crackled" in result


def test_strips_trailing_metadata_label_lines():
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    raw = "The wind howled.\n\nScene Context: The player is outside in the storm."
    result = parse_narrator_response(game, raw)
    assert "Scene Context:" not in result
    assert "wind howled" in result


# ── Clean prose regression: no false positives ───────────────


def test_clean_prose_passes_through_unchanged():
    """Clean narrator prose must not be mangled by the cleanup pipeline."""
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    prose = (
        "The corridor stretched ahead, dust motes drifting through a shaft "
        "of amber light. Somewhere above, a floorboard groaned under weight "
        "that was not yours.\n\n"
        '"You should not be here," the archivist said, not looking up from '
        "her ledger. Her pen scratched across parchment - steady, deliberate, "
        "as if your presence was a minor inconvenience in a long afternoon.\n\n"
        "The smell of old paper and candle wax hung in the air. Through the "
        "window, the last light of evening painted the rooftops in copper."
    )
    result = parse_narrator_response(game, prose)
    # Em-dash normalization is expected (— → -), but content must survive intact
    assert "corridor stretched" in result
    assert "should not be here" in result
    assert "candle wax" in result
    assert "copper" in result
    # No truncation: all three paragraphs present
    assert result.count("\n\n") >= 2


def test_clean_prose_with_dialog_quotes_preserved():
    """Dialog with various quote styles must not be stripped."""
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    prose = (
        "\u201cI have been waiting,\u201d she said. \u201cDid you bring the key?\u201d\n\n"
        "You hesitated. The key was in your pocket, warm against your thigh."
    )
    result = parse_narrator_response(game, prose)
    assert "waiting" in result
    assert "bring the key" in result
    assert "hesitated" in result


def test_clean_prose_with_parenthetical_survives():
    """Parenthetical remarks in prose must not trigger bracket stripping."""
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    prose = (
        "The guard (a tall woman with a scar across her jaw) stepped "
        "aside without a word. Her hand rested on the pommel of her sword."
    )
    result = parse_narrator_response(game, prose)
    assert "tall woman" in result
    assert "pommel" in result


def test_prose_with_ellipsis_not_truncated():
    """Prose ending with ellipsis must not be treated as truncated."""
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    prose = "The door creaked open, revealing nothing but darkness and the faint smell of iron..."
    result = parse_narrator_response(game, prose)
    assert "darkness" in result
    assert "iron" in result


def test_prose_with_numbers_not_stripped():
    """Prose containing numbers must not be confused with game data."""
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    prose = (
        "Three guards stood at the gate. The tallest held up 5 fingers, "
        "a signal you did not recognize. Behind them, 12 torches lined "
        "the wall like teeth in a jaw."
    )
    result = parse_narrator_response(game, prose)
    assert "Three guards" in result
    assert "5 fingers" in result
    assert "12 torches" in result


# ── Edge cases: multi-format contamination ───────────────────


def test_prose_with_xml_style_tags_in_dialog():
    """Narrator sometimes uses <sigh> or <pause> as stylistic elements."""
    _load_engine()
    _stub_emotions()
    from straightjacket.engine.parser import parse_narrator_response

    game = _game()
    prose = (
        'She set down the cup. "I do not know what you want from me." '
        'A long silence. "But I suppose it does not matter now."'
    )
    result = parse_narrator_response(game, prose)
    assert "set down the cup" in result
    assert "does not matter" in result
