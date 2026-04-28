from __future__ import annotations

import pytest

from straightjacket.engine.mechanics import (
    generate_engine_memories,
    is_dialog_branch,
    is_dialog_memory,
    move_category,
)
from straightjacket.engine.engine_loader import eng

from tests._helpers import make_brain_result
from tests._mocks import make_test_game


class TestIsDialogBranch:
    def test_explicit_dialog_move(self) -> None:
        brain = make_brain_result(move="dialog")
        assert is_dialog_branch(brain) is True

    def test_ask_the_oracle(self) -> None:
        brain = make_brain_result(move="ask_the_oracle")
        assert is_dialog_branch(brain) is True

    def test_dialog_only_flag_with_action_move(self) -> None:
        brain = make_brain_result(move="combat/clash", dialog_only=True)
        assert is_dialog_branch(brain) is True

    def test_action_move_without_flag_is_not_dialog(self) -> None:
        brain = make_brain_result(move="combat/clash", dialog_only=False)
        assert is_dialog_branch(brain) is False


class TestIsDialogMemory:
    def test_dialog_branch_implies_dialog_memory(self) -> None:
        brain = make_brain_result(move="ask_the_oracle")
        assert is_dialog_memory(brain, roll_present=False) is True

    def test_no_roll_means_dialog_memory_even_for_action_move(self) -> None:
        brain = make_brain_result(move="adventure/face_danger", dialog_only=False)
        assert is_dialog_memory(brain, roll_present=False) is True

    def test_action_move_with_roll_is_not_dialog_memory(self) -> None:
        brain = make_brain_result(move="combat/clash", dialog_only=False)
        assert is_dialog_memory(brain, roll_present=True) is False


class TestEngineMemoriesNoKeyError:
    def test_ask_the_oracle_with_none_roll(self) -> None:
        game = make_test_game()
        brain = make_brain_result(move="ask_the_oracle", target_npc="npc_1")
        memories = generate_engine_memories(game, brain, roll=None, activated_npc_ids={"npc_1"})
        assert len(memories) == 1
        assert "exchanged words" in memories[0]["event"] or memories[0]["event"]

    def test_dialog_only_with_action_move_and_none_roll(self) -> None:
        game = make_test_game()
        brain = make_brain_result(move="combat/clash", dialog_only=True, target_npc="npc_1")
        memories = generate_engine_memories(game, brain, roll=None, activated_npc_ids={"npc_1"})
        assert len(memories) == 1

    def test_world_shaping_with_none_roll(self) -> None:
        game = make_test_game()
        brain = make_brain_result(move="world_shaping", dialog_only=True)
        memories = generate_engine_memories(game, brain, roll=None, activated_npc_ids={"npc_1"})
        assert len(memories) == 1


class TestMoveCategoriesCoverage:
    def test_every_implemented_move_has_real_category(self) -> None:
        outcomes = eng().get_raw("move_outcomes")
        engine_moves = eng().engine_moves

        implemented = set(outcomes.keys()) | set(engine_moves.keys())

        uncategorized = [m for m in sorted(implemented) if move_category(m) == "other" and m not in _explicitly_other()]
        assert uncategorized == [], (
            f"Implemented moves without a real category (will fall through to 'other'): {uncategorized}. "
            "Add them to engine/move_categories.yaml under the appropriate bucket."
        )

    def test_unknown_move_returns_other(self) -> None:
        assert move_category("nonexistent/fake_move") == "other"


class TestProcessTurnGuard:
    def test_raises_when_game_over(self) -> None:
        from straightjacket.engine.game.turn import process_turn

        game = make_test_game()
        game.game_over = True

        with pytest.raises(RuntimeError, match="game_over=True"):
            process_turn(provider=None, game=game, player_message="anything")  # type: ignore[arg-type]

    def test_does_not_raise_when_game_active(self) -> None:
        game = make_test_game()
        assert game.game_over is False


class TestExecuteRollStatNoneRejected:
    def test_action_roll_with_stat_none_raises(self) -> None:
        from straightjacket.engine.game.turn import _execute_roll

        game = make_test_game()
        game.setting_id = "classic"
        brain = make_brain_result(move="adventure/face_danger", stat="none", dialog_only=False)

        with pytest.raises(ValueError, match="stat='none'"):
            _execute_roll(game, brain)

    def test_action_roll_with_real_stat_succeeds(self) -> None:
        from straightjacket.engine.game.turn import _execute_roll

        game = make_test_game()
        game.setting_id = "classic"
        brain = make_brain_result(move="adventure/face_danger", stat="wits", dialog_only=False)

        outcome = _execute_roll(game, brain)
        assert outcome.roll is not None
        assert outcome.roll.stat_name == "wits"


class TestSanitizeBrainOutput:
    def test_action_roll_with_stat_none_routes_to_dialog(self) -> None:
        from straightjacket.engine.game.turn import _sanitize_brain_output

        game = make_test_game()
        game.setting_id = "classic"
        brain = make_brain_result(move="adventure/face_danger", stat="none", dialog_only=False)

        _sanitize_brain_output(game, brain)

        assert brain.dialog_only is True

    def test_dialog_move_unchanged(self) -> None:
        from straightjacket.engine.game.turn import _sanitize_brain_output

        game = make_test_game()
        game.setting_id = "classic"
        brain = make_brain_result(move="dialog", stat="none", dialog_only=False)

        _sanitize_brain_output(game, brain)

        assert brain.dialog_only is False

    def test_already_dialog_only_unchanged(self) -> None:
        from straightjacket.engine.game.turn import _sanitize_brain_output

        game = make_test_game()
        game.setting_id = "classic"
        brain = make_brain_result(move="adventure/face_danger", stat="none", dialog_only=True)

        _sanitize_brain_output(game, brain)

        assert brain.dialog_only is True

    def test_action_roll_with_real_stat_unchanged(self) -> None:
        from straightjacket.engine.game.turn import _sanitize_brain_output

        game = make_test_game()
        game.setting_id = "classic"
        brain = make_brain_result(move="adventure/face_danger", stat="wits", dialog_only=False)

        _sanitize_brain_output(game, brain)

        assert brain.dialog_only is False

    def test_unknown_move_unchanged(self) -> None:
        from straightjacket.engine.game.turn import _sanitize_brain_output

        game = make_test_game()
        game.setting_id = "classic"
        brain = make_brain_result(move="unknown/fake_move", stat="none", dialog_only=False)

        _sanitize_brain_output(game, brain)

        assert brain.dialog_only is False

    def test_engine_move_action_roll_with_stat_none_routes_to_dialog(self) -> None:
        from straightjacket.engine.game.turn import _sanitize_brain_output

        game = make_test_game()
        game.setting_id = "classic"
        brain = make_brain_result(move="world_shaping", stat="none", dialog_only=False)

        _sanitize_brain_output(game, brain)

        assert brain.dialog_only is True


def _explicitly_other() -> set[str]:
    mc = eng().get_raw("move_categories")
    return set(mc.get("other", []))
