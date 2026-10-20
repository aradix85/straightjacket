from typing import Any

from tests._helpers import make_brain_result, make_game_state, make_npc


def test_a_descriptive_alias_names_its_npc_only_as_a_whole(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.npc.matching import named_in

    morell = make_npc(id="npc_1", name="Morell", aliases=["The gate guard"])
    assert not named_in(morell, "You slip through the gate. Back at the gate, torches gutter.")
    assert named_in(morell, "The gate guard shouts after you.")
    assert named_in(morell, "You nod to the gate guard.")


def test_the_small_words_of_an_alias_name_nobody(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.npc.matching import named_in

    shona = make_npc(id="npc_2", name="Shona", aliases=["The young woman with the bucket"])
    assert not named_in(shona, "You walk with care while a woman sings at the well.")
    assert named_in(shona, "The young woman with the bucket waves.")


def test_a_proper_name_keeps_its_capital(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.npc.matching import named_in

    hope = make_npc(id="npc_3", name="Hope")
    wolf = make_npc(id="npc_4", name="Wolf")
    assert not named_in(hope, "There is little hope left in the hold.")
    assert named_in(hope, "Hope draws her knife.")
    assert not named_in(wolf, "Somewhere below, a wolf howls.")
    assert named_in(wolf, "Wolf grins at you.")


def test_a_name_inside_another_word_names_nobody(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.npc.matching import named_in

    ash = make_npc(id="npc_5", name="Ash")
    assert not named_in(ash, "Ashes drift over the ridge.")
    assert named_in(ash, "Ash shrugs and turns away.")


def test_an_empty_alias_names_nobody(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.npc.matching import named_in

    edda = make_npc(id="npc_6", name="Edda Varn", aliases=["", "  "])
    assert not named_in(edda, "The wind howls over the empty pass.")


def test_only_the_leading_given_names_of_a_name_count_alone(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.npc.matching import proper_name_words

    def words(name: str) -> list[str]:
        return proper_name_words(make_npc(id="npc_7", name=name))

    assert words("Mira Ashwood") == ["Mira", "Ashwood"]
    assert words("Captain Ashwood") == ["Ashwood"]
    assert words("Captain Jo") == []
    assert words("Kira the smith") == ["Kira"]
    assert words("Young woman with bucket") == []
    assert words("The Gate Guard") == []


def test_the_narration_introduces_an_npc_only_by_a_whole_name(load_engine: None) -> None:
    from straightjacket.engine.parser import parse_narrator_response

    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="npc_1", name="Mira Hale", introduced=False)]
    parse_narrator_response(game, "A miraculous calm settles. The old man is hale and quiet.")
    assert game.npcs[0].introduced is False
    parse_narrator_response(game, "Hale steps out of the rain.")
    assert game.npcs[0].introduced is True


def test_an_alias_word_in_the_brains_words_does_not_activate_its_npc(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.npc.activation import activate_npcs_for_prompt

    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="npc_1", name="Morell", aliases=["The gate guard"])]
    brain = make_brain_result(player_intent="Slip back through the gate")
    activated, _mentioned = activate_npcs_for_prompt(game, brain, "I slip back out")
    assert activated == []
    brain = make_brain_result(player_intent="Ask the gate guard about the road")
    activated, _mentioned = activate_npcs_for_prompt(game, brain, "I ask him about the road")
    assert [n.id for n in activated] == ["npc_1"]


def test_the_player_may_type_a_name_in_lower_case(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.npc.activation import activate_npcs_for_prompt

    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="npc_1", name="Kira Voss"), make_npc(id="npc_2", name="Borin Hale")]
    activated, mentioned = activate_npcs_for_prompt(game, make_brain_result(player_intent=""), "i look for kira")
    found = {n.id for n in activated + mentioned}
    assert "npc_1" in found
    assert "npc_2" not in found


def _memory(npc_name: str) -> dict[str, Any]:
    return {"npc_name": npc_name, "event": "Watched the player arrive", "emotional_weight": "neutral"}


def test_an_opening_memory_finds_its_npc_by_a_given_name_and_not_by_a_title(load_engine: None) -> None:
    from straightjacket.engine.game.setup_common import seed_opening_memories

    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="npc_1", name="Kira Voss"), make_npc(id="npc_2", name="Captain Ashwood")]
    seed_opening_memories(game, [_memory("Kira"), _memory("Captain Reed")])
    assert [len(n.memory) for n in game.npcs] == [1, 0]
