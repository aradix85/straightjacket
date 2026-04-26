from __future__ import annotations

from straightjacket.engine.engine_loader import eng


def _all_categories() -> set[str]:
    return set(eng().get_raw("move_categories").keys())


def _stance_bucket_values() -> set[str]:
    return set(eng().stance_move_buckets.mapping.values())


class TestMoveCategoriesSymmetry:
    def test_stance_move_buckets_covers_every_category(self) -> None:
        cats = _all_categories()
        mapping_keys = set(eng().stance_move_buckets.mapping.keys())
        missing = cats - mapping_keys
        assert missing == set(), (
            f"Categories defined in move_categories.yaml but missing from stance_move_buckets.mapping: {sorted(missing)}. "
            "Every move_category value must map to a stance bucket — otherwise NPC stance resolution KeyErrors."
        )

    def test_stance_move_buckets_has_no_extra_keys(self) -> None:
        cats = _all_categories()
        mapping_keys = set(eng().stance_move_buckets.mapping.keys())
        extra = mapping_keys - cats
        assert extra == set(), (
            f"stance_move_buckets.mapping has keys not in move_categories: {sorted(extra)}. "
            "Either remove the mapping entry or add the category to move_categories.yaml."
        )

    def test_position_resolver_baselines_cover_every_category(self) -> None:
        cats = _all_categories()
        baselines = set(eng().position_resolver.move_baselines.keys())
        missing = cats - baselines
        assert missing == set(), (
            f"Categories missing from position_resolver.move_baselines: {sorted(missing)}. "
            "Without an entry, the position resolver silently falls back to the 'other' baseline, "
            "producing wrong dice difficulty for whole move classes."
        )

    def test_stance_matrix_buckets_cover_stance_move_buckets_values(self) -> None:
        bucket_values = _stance_bucket_values()
        matrix = eng().stance_matrix
        for disposition, bond_levels in matrix.items():
            for bond_level, cats in bond_levels.items():
                missing = bucket_values - set(cats.keys())
                assert missing == set(), (
                    f"stance_matrix[{disposition!r}][{bond_level!r}] missing buckets: {sorted(missing)}. "
                    "Every value that stance_move_buckets.mapping can produce must exist as a key in every "
                    "(disposition, bond_level) cell of stance_matrix."
                )

    def test_memory_emotions_covers_every_non_dialog_combination(self) -> None:
        cats = _all_categories()
        results = ("MISS", "WEAK_HIT", "STRONG_HIT")
        base = eng().memory_emotions.base
        missing = []
        for cat in cats:
            for res in results:
                key = f"{cat}_{res}"
                if key not in base and not (cat == "recovery" and res == "MISS"):
                    missing.append(key)
        assert missing == [], (
            f"memory_emotions.base missing keys: {missing}. "
            "Every (category, result) combination must be present (recovery_MISS is exempted by design)."
        )

    def test_memory_result_text_covers_every_non_dialog_combination(self) -> None:
        cats = _all_categories()
        results = ("MISS", "WEAK_HIT", "STRONG_HIT")
        result_text = eng().get_raw("memory_result_text")
        missing = [f"{cat}_{res}" for cat in cats for res in results if f"{cat}_{res}" not in result_text]
        assert missing == [], f"memory_result_text missing keys: {missing}."

    def test_memory_emotions_has_dialog_key(self) -> None:
        assert (
            "dialog" in eng().memory_emotions.base
        ), "memory_emotions.base must contain 'dialog' key for dialog turns."

    def test_memory_result_text_has_dialog_key(self) -> None:
        assert "dialog" in eng().get_raw("memory_result_text"), "memory_result_text must contain 'dialog' key."


class TestEveryMoveResolvesEndToEnd:
    def test_every_move_passes_through_full_stance_pipeline(self) -> None:
        from straightjacket.engine.datasworn.moves import get_moves
        from straightjacket.engine.datasworn.settings import list_packages
        from straightjacket.engine.prompt_shared import _resolve_stance_category

        all_moves: set[str] = set()
        for sid in list_packages():
            all_moves.update(get_moves(sid).keys())
        all_moves.update(eng().engine_moves.keys())

        failures = []
        for move in sorted(all_moves):
            try:
                bucket = _resolve_stance_category(move)
                if bucket not in _stance_bucket_values():
                    failures.append(f"{move} → {bucket} (not a valid bucket)")
            except KeyError as e:
                failures.append(f"{move} → KeyError({e})")

        assert failures == [], (
            f"Moves that fail to resolve through the stance pipeline: {failures}. "
            "Every move must produce a valid stance bucket without crashing."
        )

    def test_every_move_resolves_position_baseline(self) -> None:
        from straightjacket.engine.datasworn.moves import get_moves
        from straightjacket.engine.datasworn.settings import list_packages
        from straightjacket.engine.mechanics.resolvers import move_category

        all_moves: set[str] = set()
        for sid in list_packages():
            all_moves.update(get_moves(sid).keys())
        all_moves.update(eng().engine_moves.keys())

        baselines = eng().position_resolver.move_baselines
        unmapped = [m for m in sorted(all_moves) if move_category(m) not in baselines]
        assert unmapped == [], f"Moves whose category has no baseline in position_resolver.move_baselines: {unmapped}."


class TestMoveOutcomesCoverage:
    def test_every_action_roll_move_has_outcome_config(self) -> None:
        from straightjacket.engine.datasworn.moves import get_moves
        from straightjacket.engine.datasworn.settings import list_packages

        action_roll_moves: set[str] = set()
        for sid in list_packages():
            for move_id, move in get_moves(sid).items():
                if move.roll_type == "action_roll":
                    action_roll_moves.add(move_id)
        for move_id, em in eng().engine_moves.items():
            if em.roll_type == "action_roll":
                action_roll_moves.add(move_id)

        outcomes = eng().get_raw("move_outcomes")
        missing = sorted(action_roll_moves - set(outcomes.keys()))
        assert missing == [], (
            f"Action_roll moves without an entry in engine/move_outcomes.yaml: {missing}. "
            "Every action_roll move must have outcomes defined per result, otherwise resolve_move_outcome crashes mid-turn."
        )

    def test_no_orphan_outcome_entries(self) -> None:
        from straightjacket.engine.datasworn.moves import get_moves
        from straightjacket.engine.datasworn.settings import list_packages

        all_known_moves: set[str] = set()
        for sid in list_packages():
            all_known_moves.update(get_moves(sid).keys())
        all_known_moves.update(eng().engine_moves.keys())

        outcomes = eng().get_raw("move_outcomes")
        orphan = sorted(set(outcomes.keys()) - all_known_moves)
        assert orphan == [], (
            f"engine/move_outcomes.yaml has entries for moves that don't exist: {orphan}. "
            "Either remove the outcome entry or restore the move."
        )
