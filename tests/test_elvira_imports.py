"""Smoke test: import all Elvira modules to catch interface breakages.

Elvira runs as an integration test with API keys, so its code is not
exercised by the normal pytest suite. This test ensures that Elvira's
imports resolve and its key functions are callable — catching issues
like removed fields (e.g. NpcData.bond) that would crash at runtime.
"""


def test_import_display() -> None:
    from tests.elvira.elvira_bot.display import final_state_dict, print_narration, print_state, print_summary

    assert callable(final_state_dict)
    assert callable(print_narration)
    assert callable(print_state)
    assert callable(print_summary)


def test_import_models() -> None:
    from tests.elvira.elvira_bot.models import ChapterRecord, NpcSnapshot, SessionLog, StateSnapshot, TurnRecord

    assert callable(SessionLog)
    assert callable(TurnRecord)
    assert callable(StateSnapshot)
    assert callable(NpcSnapshot)
    assert callable(ChapterRecord)


def test_import_recorder() -> None:
    from tests.elvira.elvira_bot.recorder import record_turn

    assert callable(record_turn)


def test_import_invariants() -> None:
    from tests.elvira.elvira_bot.invariants import assert_game_state

    assert callable(assert_game_state)


def test_final_state_dict_runs(load_engine: None) -> None:
    """Verify final_state_dict doesn't crash on a minimal game state."""
    from straightjacket.engine.models import GameState, NpcData

    from tests.elvira.elvira_bot.display import final_state_dict

    game = GameState(player_name="Test")
    game.npcs.append(NpcData(id="npc_1", name="Kira", status="active", disposition="friendly"))
    result = final_state_dict(game)
    assert result["character"] == "Test"
    assert len(result["npcs"]) == 1
    assert "bond" in result["npcs"][0]
