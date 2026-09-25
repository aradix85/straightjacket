from straightjacket.engine.models import ClockFillResult
from straightjacket.engine.prompt_shared import _activated_npcs_block, _clock_filled_block
from tests._helpers import make_game_state, make_memory, make_npc


def test_no_filled_clock_adds_nothing_to_the_prompt() -> None:
    assert _clock_filled_block([]) == ""


def test_each_filled_clock_reaches_the_prompt_as_an_escaped_tag() -> None:
    block = _clock_filled_block(
        [
            ClockFillResult(clock_name='The "Tide"', clock_type="threat", tag_text="Water <rises>."),
            ClockFillResult(clock_name="Rations", clock_type="progress", tag_text="The last crate is opened."),
        ]
    )
    assert block.split("\n") == [
        '<clock_filled name="The &quot;Tide&quot;" clock_type="threat">Water &lt;rises&gt;.</clock_filled>',
        '<clock_filled name="Rations" clock_type="progress">The last crate is opened.</clock_filled>',
    ]


def test_an_activated_npc_carries_its_most_recent_memory(load_engine: None) -> None:
    game = make_game_state()
    game.narrative.scene_count = 4
    npc = make_npc(id="npc_1", name="Mara", memory=[make_memory(scene=3, event="saw the harbour seal broken")])
    block = _activated_npcs_block([npc], None, game, "the harbour seal lies broken", "social")
    assert block.startswith('<activated_npc name="Mara"')
    assert 'recent="saw the harbour seal broken(neutral)"' in block
    assert "insight=" not in block


def test_an_activated_npc_prefers_its_reflection_as_insight(load_engine: None) -> None:
    game = make_game_state()
    game.narrative.scene_count = 4
    npc = make_npc(
        id="npc_1",
        name="Mara",
        memory=[
            make_memory(scene=3, event="saw the harbour seal broken"),
            make_memory(scene=3, event="the stranger cannot be trusted", type="reflection", importance=8),
        ],
    )
    block = _activated_npcs_block([npc], None, game, "the harbour seal lies broken", "social")
    assert 'insight="the stranger cannot be trusted"' in block
    assert "recent=" not in block
