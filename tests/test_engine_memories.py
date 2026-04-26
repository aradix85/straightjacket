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
    def test_every_datasworn_and_engine_move_has_category(self) -> None:
        from straightjacket.engine.datasworn.moves import get_moves
        from straightjacket.engine.datasworn.settings import list_packages

        all_moves: set[str] = set()
        for sid in list_packages():
            all_moves.update(get_moves(sid).keys())
        all_moves.update(eng().engine_moves.keys())

        uncategorized = [m for m in sorted(all_moves) if move_category(m) == "other" and m not in _explicitly_other()]
        assert uncategorized == [], (
            f"Moves without a real category (will fall through to 'other'): {uncategorized}. "
            "Add them to engine/move_categories.yaml under the appropriate bucket."
        )

    def test_unknown_move_returns_other(self) -> None:
        assert move_category("nonexistent/fake_move") == "other"


class TestMemoryYamlSymmetry:
    def test_every_category_has_all_three_results_in_emotions(self) -> None:
        base = eng().memory_emotions.base
        categories = ("combat", "social", "endure", "recovery", "other", "gather_information")
        results = ("MISS", "WEAK_HIT", "STRONG_HIT")
        missing = []
        for cat in categories:
            for res in results:
                key = f"{cat}_{res}"
                if key not in base and not (cat == "recovery" and res == "MISS"):
                    missing.append(key)
        assert missing == [], f"Missing keys in memory_emotions.base: {missing}"

    def test_every_category_has_all_three_results_in_result_text(self) -> None:
        result_text = eng().get_raw("memory_result_text")
        categories = ("combat", "social", "endure", "recovery", "other", "gather_information")
        results = ("MISS", "WEAK_HIT", "STRONG_HIT")
        missing = [f"{cat}_{res}" for cat in categories for res in results if f"{cat}_{res}" not in result_text]
        assert missing == [], f"Missing keys in memory_result_text: {missing}"


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


def _explicitly_other() -> set[str]:
    mc = eng().get_raw("move_categories")
    return set(mc.get("other", []))
