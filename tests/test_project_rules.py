from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

from tests._rules_code import (
    _check_ai_calls_route_by_their_role,
    _check_broad_except_inside_carve_out_only,
    _check_dataclasses_in_models_inherit_serializablemixin,
    _check_no_dataclass_defaults,
    _check_no_domain_default_in_dict_get,
    _check_no_get_raw_with_fallback,
    _check_no_hardcoded_model_names_in_engine,
    _check_no_name_or_empty_collection_fallback,
    _check_no_optional_collection_param_default_none,
    _check_no_or_literal_fallback_on_lookups,
    _check_no_python_comments_or_docstrings,
    _check_no_setdefault_calls,
    _check_no_skip_or_xfail_in_tests,
    _check_no_versioned_filenames,
    _check_no_warning_suppression,
    _check_no_yaml_comments,
    _check_ruff_format_clean,
)
from tests._rules_docs import (
    _check_changelog_consistent,
    _check_code_map_complete,
    _check_divergences_have_a_status,
    _check_doc_paths_exist,
    _check_doc_references_resolve,
    _check_doc_symbols_exist,
)
from tests._rules_imports import (
    _check_hub_packages_imported_through_init,
    _check_import_layers,
    _check_no_direct_provider_sdk_imports,
)
from tests._rules_orphans import (
    _check_no_orphan_prompt_keys,
    _check_no_orphan_public_symbols,
    _check_no_orphan_yaml_keys,
    _check_no_stale_carve_out_entries,
)

if TYPE_CHECKING:
    from tests._rules import Violation


def _format_report(category: str, violations: list[Violation]) -> str:
    header = f"{category}: {len(violations)} violation(s)\n"
    body = "\n".join(str(v) for v in violations)
    return header + body


_ALL_CHECKS = (
    _check_ai_calls_route_by_their_role,
    _check_no_domain_default_in_dict_get,
    _check_no_or_literal_fallback_on_lookups,
    _check_no_name_or_empty_collection_fallback,
    _check_no_optional_collection_param_default_none,
    _check_no_dataclass_defaults,
    _check_broad_except_inside_carve_out_only,
    _check_no_python_comments_or_docstrings,
    _check_no_yaml_comments,
    _check_dataclasses_in_models_inherit_serializablemixin,
    _check_no_direct_provider_sdk_imports,
    _check_no_hardcoded_model_names_in_engine,
    _check_no_setdefault_calls,
    _check_no_get_raw_with_fallback,
    _check_no_warning_suppression,
    _check_no_versioned_filenames,
    _check_ruff_format_clean,
    _check_no_orphan_public_symbols,
    _check_no_orphan_yaml_keys,
    _check_no_stale_carve_out_entries,
    _check_no_skip_or_xfail_in_tests,
    _check_no_orphan_prompt_keys,
    _check_doc_paths_exist,
    _check_code_map_complete,
    _check_doc_symbols_exist,
    _check_doc_references_resolve,
    _check_changelog_consistent,
    _check_divergences_have_a_status,
    _check_import_layers,
    _check_hub_packages_imported_through_init,
)


def test_project_rules() -> None:
    failed: list[tuple[str, list[Violation]]] = []
    for check in _ALL_CHECKS:
        category, violations = check()
        if violations:
            failed.append((category, violations))

    if failed:
        report = "\n\n".join(itertools.starmap(_format_report, failed))
        raise AssertionError("\n" + report)
