from straightjacket.engine.models import ClockFillResult
from tests._helpers import dialog_prompt, make_game_state, make_memory, make_npc


def test_no_filled_clock_adds_nothing_to_the_prompt(load_engine: None) -> None:
    assert "<clock_filled" not in dialog_prompt(make_game_state())


def test_each_filled_clock_reaches_the_prompt_as_an_escaped_tag(load_engine: None) -> None:
    prompt = dialog_prompt(
        make_game_state(),
        clock_fill_results=[
            ClockFillResult(clock_name='The "Tide"', clock_type="threat", tag_text="Water <rises>."),
            ClockFillResult(clock_name="Rations", clock_type="progress", tag_text="The last crate is opened."),
        ],
    )
    assert (
        '<clock_filled name="The &quot;Tide&quot;" clock_type="threat">Water &lt;rises&gt;.</clock_filled>\n'
        '<clock_filled name="Rations" clock_type="progress">The last crate is opened.</clock_filled>'
    ) in prompt


def _activated(*memories: object) -> str:
    game = make_game_state()
    game.narrative.scene_count = 4
    npc = make_npc(id="npc_1", name="Mara", memory=list(memories))
    return dialog_prompt(game, activated_npcs=[npc], player_words="the harbour seal lies broken")


def test_an_activated_npc_carries_its_most_recent_memory(load_engine: None) -> None:
    prompt = _activated(make_memory(scene=3, event="saw the harbour seal broken"))
    assert '<activated_npc name="Mara"' in prompt
    assert 'recent="saw the harbour seal broken(neutral)"' in prompt
    assert "insight=" not in prompt


def test_an_activated_npc_prefers_its_reflection_as_insight(load_engine: None) -> None:
    prompt = _activated(
        make_memory(scene=3, event="saw the harbour seal broken"),
        make_memory(scene=3, event="the stranger cannot be trusted", type="reflection", importance=8),
    )
    assert 'insight="the stranger cannot be trusted"' in prompt
    assert "recent=" not in prompt
