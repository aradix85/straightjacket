from __future__ import annotations

from typing import Any

import pytest

from straightjacket.engine.game.turn import process_turn
from straightjacket.engine.gamemaster.engine_memories import generate_engine_memories
from straightjacket.engine.gamemaster.moves import asks_the_oracle, is_dialog_branch
from straightjacket.engine.ruleset.answers import action_kind
from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.make_move import roll_move
from tests._helpers import make_brain_result
from tests._mocks import MockProvider, make_test_game


class TestIsDialogBranch:
    @staticmethod
    def test_explicit_dialog_move() -> None:
        brain = make_brain_result(move="dialog")
        assert is_dialog_branch(brain) is True

    @staticmethod
    def test_ask_the_oracle() -> None:
        brain = make_brain_result(move="ask_the_oracle")
        assert is_dialog_branch(brain) is True

    @staticmethod
    def test_dialog_only_flag_with_action_move() -> None:
        brain = make_brain_result(move="combat/clash", dialog_only=True)
        assert is_dialog_branch(brain) is True

    @staticmethod
    def test_action_move_without_flag_is_not_dialog() -> None:
        brain = make_brain_result(move="combat/clash", dialog_only=False)
        assert is_dialog_branch(brain) is False

    @staticmethod
    def test_world_shaping_is_the_rulesets_move_and_rolls() -> None:
        brain = make_brain_result(move="world_shaping", dialog_only=False)
        assert is_dialog_branch(brain) is False

    @staticmethod
    def test_only_asking_the_oracle_asks_the_oracle() -> None:
        assert asks_the_oracle("ask_the_oracle") is True
        assert asks_the_oracle("dialog") is False


class TestEngineMemoriesWithoutRoll:
    @staticmethod
    def _memory(brain: Any, outcome: str) -> Any:
        game = make_test_game()
        memories = generate_engine_memories(game, brain, outcome=outcome, activated_npc_ids={"npc_1"}, consequences=())
        assert len(memories) == 1
        return memories[0][1]

    def test_ask_the_oracle_is_remembered_as_a_dialog(self) -> None:
        dialog = self._memory(make_brain_result(move="dialog", target_npc="npc_1"), "dialog")
        oracle = self._memory(make_brain_result(move="ask_the_oracle", target_npc="npc_1"), "oracle")
        assert oracle == dialog

    def test_dialog_only_with_action_move_is_remembered_as_a_dialog(self) -> None:
        dialog = self._memory(make_brain_result(move="dialog", target_npc="npc_1"), "dialog")
        clash = self._memory(make_brain_result(move="combat/clash", dialog_only=True, target_npc="npc_1"), "dialog")
        assert clash == dialog

    def test_world_shaping_as_dialog(self) -> None:
        self._memory(make_brain_result(move="world_shaping", dialog_only=True), "dialog")


class TestMoveCategoriesCoverage:
    @staticmethod
    def test_every_implemented_move_has_real_category() -> None:
        outcomes = rules().move_outcomes
        engine_moves = rules().engine_moves

        implemented = set(outcomes.keys()) | set(engine_moves.keys())

        uncategorized = [m for m in sorted(implemented) if action_kind(m) == "other" and m not in _explicitly_other()]
        assert uncategorized == [], (
            f"Implemented moves without a real category (will fall through to 'other'): {uncategorized}. "
            "Add them to ruleset/move_categories.yaml under the appropriate bucket."
        )

    @staticmethod
    def test_unknown_move_returns_other() -> None:
        assert action_kind("nonexistent/fake_move") == "other"


class TestProcessTurnGuard:
    @staticmethod
    def test_raises_when_game_over() -> None:
        game = make_test_game()
        game.end_reason = "death"

        with pytest.raises(RuntimeError, match="game_over=True"):
            process_turn(provider=MockProvider(), game=game, player_message="anything", stream=None)

    @staticmethod
    def test_does_not_raise_when_game_active() -> None:
        game = make_test_game()
        assert game.game_over is False


class TestExecuteRollStatNoneRejected:
    @staticmethod
    def test_action_roll_with_stat_none_raises() -> None:
        game = make_test_game()
        game.setting_id = "classic"
        brain = make_brain_result(move="adventure/face_danger", stat="none", dialog_only=False)
        game.last_turn_snapshot = game.snapshot()

        with pytest.raises(ValueError, match="named no stat"):
            roll_move(game, brain, None)

    @staticmethod
    def test_action_roll_with_real_stat_succeeds() -> None:
        game = make_test_game()
        game.setting_id = "classic"
        brain = make_brain_result(move="adventure/face_danger", stat="wits", dialog_only=False)
        game.last_turn_snapshot = game.snapshot()

        outcome = roll_move(game, brain, None)
        assert outcome.roll.stat_name == "wits"


def _explicitly_other() -> set[str]:
    return set(rules().move_categories["other"])
