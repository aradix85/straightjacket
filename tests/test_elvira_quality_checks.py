from tests._helpers import make_game_state, make_npc


def _seen_moving(old: str, new: str) -> list[str]:
    from tests.elvira.elvira_bot.quality_checks import check_npc_spatial_consistency
    from tests.elvira.elvira_bot.recorder import record_turn

    game = make_game_state()
    npc = make_npc(id="npc_1", name="Saffi", status="active", last_location=old)
    game.npcs = [npc]
    before = record_turn(game, 1, "", "", None).npcs
    npc.last_location = new
    return check_npc_spatial_consistency(game, before, "The tide turns.")


def test_a_reworded_place_is_the_same_place(load_engine: None) -> None:
    assert (
        _seen_moving("A narrow quay in a harbor; the harbor's name is unknown.", "A narrow quay in an unnamed harbor")
        == []
    )
    assert _seen_moving("Cargo deck", "cargo deck ") == []


def test_an_npc_who_moves_unseen_is_reported(load_engine: None) -> None:
    for old, new in [
        ("Saltmarrow docks", "Saltmarrow harbourmaster's office"),
        ("Cargo deck of the Ashfall", "Bridge of the Ashfall"),
    ]:
        assert _seen_moving(old, new) == [
            f"NPC 'Saffi' teleported from '{old}' to '{new}' without appearing in narration"
        ]
