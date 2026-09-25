from tests._helpers import make_game_state, make_npc


def _memory() -> dict:
    return {"npc_id": "npc_1", "event": "Saw the player leave", "emotional_weight": "calm", "importance": 2}


def test_an_npc_the_narration_leaves_behind_keeps_its_place(load_engine: None) -> None:
    from straightjacket.engine.game.finalization import apply_engine_memories

    game = make_game_state()
    game.world.current_location = "Glacier ridge trail"
    edda = make_npc(id="npc_1", name="Edda Varn")
    edda.last_location = "Settlement beneath the ridge"
    game.npcs = [edda]
    apply_engine_memories(game, [_memory()], "You climb the trail alone, the gate shrinking behind you.")
    assert edda.last_location == "Settlement beneath the ridge"
    assert edda.memory[-1].event == "Saw the player leave"


def test_an_npc_the_narration_names_moves_along(load_engine: None) -> None:
    from straightjacket.engine.game.finalization import apply_engine_memories

    game = make_game_state()
    game.world.current_location = "Glacier ridge trail"
    edda = make_npc(id="npc_1", name="Edda Varn")
    edda.last_location = "Settlement beneath the ridge"
    game.npcs = [edda]
    apply_engine_memories(game, [_memory()], "Edda follows you up the trail.")
    assert edda.last_location == "Glacier ridge trail"


def test_a_name_counts_as_a_whole_word_or_an_alias(load_engine: None) -> None:
    from straightjacket.engine.npc import named_in

    tomas = make_npc(id="npc_2", name="Tomas Reed", aliases=["the smith"])
    assert not named_in(tomas, "A crate of tomatoes waits by the door.")
    assert named_in(tomas, "Tomas waves from the forge.")
    assert named_in(tomas, "The smith looks up.")
