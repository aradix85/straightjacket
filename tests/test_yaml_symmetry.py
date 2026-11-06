from __future__ import annotations

from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.ruleset.answers import action_kind
from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.moves import get_moves
from straightjacket.engine.setting.packages import list_packages


def _all_categories() -> set[str]:
    return set(rules().get_raw("move_categories").keys())


def _stance_bucket_values() -> set[str]:
    return set(gm().stance_move_buckets.mapping.values())


class TestMoveCategoriesSymmetry:
    @staticmethod
    def test_stance_move_buckets_covers_every_category() -> None:
        cats = _all_categories()
        mapping_keys = set(gm().stance_move_buckets.mapping.keys())
        missing = cats - mapping_keys
        assert missing == set(), (
            "Categories defined in move_categories.yaml but missing from stance_move_buckets.mapping: "
            f"{sorted(missing)}. "
            "Every move_category value must map to a stance bucket — otherwise NPC stance resolution KeyErrors."
        )

    @staticmethod
    def test_stance_move_buckets_has_no_extra_keys() -> None:
        cats = _all_categories()
        mapping_keys = set(gm().stance_move_buckets.mapping.keys())
        extra = mapping_keys - cats
        assert extra == set(), (
            f"stance_move_buckets.mapping has keys not in move_categories: {sorted(extra)}. "
            "Either remove the mapping entry or add the category to move_categories.yaml."
        )

    @staticmethod
    def test_position_resolver_baselines_cover_every_category() -> None:
        cats = _all_categories()
        baselines = set(gm().position_resolver.move_baselines.keys())
        missing = cats - baselines
        assert missing == set(), (
            f"Categories missing from position_resolver.move_baselines: {sorted(missing)}. "
            "Without an entry, the position resolver silently falls back to the 'other' baseline, "
            "producing wrong dice difficulty for whole move classes."
        )

    @staticmethod
    def test_stance_matrix_buckets_cover_stance_move_buckets_values() -> None:
        bucket_values = _stance_bucket_values()
        matrix = gm().stance_matrix
        for disposition, bond_levels in matrix.items():
            for bond_level, cats in bond_levels.items():
                missing = bucket_values - set(cats.keys())
                assert missing == set(), (
                    f"stance_matrix[{disposition!r}][{bond_level!r}] missing buckets: {sorted(missing)}. "
                    "Every value that stance_move_buckets.mapping can produce must exist as a key in every "
                    "(disposition, bond_level) cell of stance_matrix."
                )

    @staticmethod
    def test_memory_emotions_covers_every_non_dialog_combination() -> None:
        cats = _all_categories()
        results = set(rules().get_raw("result_outcomes").values())
        base = gm().memory_emotions.base
        missing = []
        for cat in cats:
            for res in results:
                key = f"{cat}_{res}"
                if key not in base:
                    missing.append(key)
        assert missing == [], (
            f"memory_emotions.base missing keys: {missing}. Every (category, result) combination must be present."
        )

    @staticmethod
    def test_memory_result_text_covers_every_non_dialog_combination() -> None:
        cats = _all_categories()
        results = set(rules().get_raw("result_outcomes").values())
        result_text = gm().get_raw("memory_result_text")
        missing = [f"{cat}_{res}" for cat in cats for res in results if f"{cat}_{res}" not in result_text]
        assert missing == [], f"memory_result_text missing keys: {missing}."

    @staticmethod
    def test_memory_emotions_has_dialog_key() -> None:
        assert "dialog" in gm().memory_emotions.base, "memory_emotions.base must contain 'dialog' key for dialog turns."

    @staticmethod
    def test_memory_result_text_has_dialog_key() -> None:
        assert "dialog" in gm().get_raw("memory_result_text"), "memory_result_text must contain 'dialog' key."


class TestEveryMoveResolvesEndToEnd:
    @staticmethod
    def test_every_move_has_a_kind_with_a_stance_bucket_and_a_position_baseline() -> None:
        all_moves: set[str] = set()
        for sid in list_packages():
            all_moves.update(get_moves(sid).keys())
        all_moves.update(rules().engine_moves.keys())
        all_moves.update(gm().moves.keys())

        kinds = {move: action_kind(move) for move in sorted(all_moves)}
        buckets = gm().stance_move_buckets.mapping
        baselines = gm().position_resolver.move_baselines
        assert [m for m, kind in kinds.items() if kind not in buckets or kind not in baselines] == []


class TestMoveOutcomesCoverage:
    @staticmethod
    def test_every_action_roll_move_has_outcome_config() -> None:
        action_roll_moves: set[str] = set()
        for sid in list_packages():
            for move_id, move in get_moves(sid).items():
                if move.roll_type == "action_roll":
                    action_roll_moves.add(move_id)
        for move_id, em in rules().engine_moves.items():
            if em.roll_type == "action_roll":
                action_roll_moves.add(move_id)

        outcomes = rules().get_raw("move_outcomes")
        missing = sorted(action_roll_moves - set(outcomes.keys()))
        assert missing == [], (
            f"Action_roll moves without an entry in engine/move_outcomes.yaml: {missing}. "
            "Every action_roll move must have outcomes defined per result, "
            "otherwise resolve_move_outcome crashes mid-turn."
        )

    @staticmethod
    def test_no_orphan_outcome_entries() -> None:
        all_known_moves: set[str] = set()
        for sid in list_packages():
            all_known_moves.update(get_moves(sid).keys())
        all_known_moves.update(rules().engine_moves.keys())

        outcomes = rules().get_raw("move_outcomes")
        orphan = sorted(set(outcomes.keys()) - all_known_moves)
        assert orphan == [], (
            f"engine/move_outcomes.yaml has entries for moves that don't exist: {orphan}. "
            "Either remove the outcome entry or restore the move."
        )
