#!/usr/bin/env python3
"""
Straightjacket NPC Package — public API.
  from engine.npc import score_importance, find_npc, ...
"""

__all__ = [
    "absorb_duplicate_npc",
    "activate_npcs_for_prompt",
    "apply_name_sanitization",
    "compute_npc_tfidf_scores",
    "consolidate_memory",
    "description_match_existing_npc",
    "edit_distance_le1",
    "find_npc",
    "fuzzy_match_existing_npc",
    "get_npc_bond",
    "is_complete_description",
    "merge_npc_identity",
    "next_npc_id",
    "normalize_disposition",
    "normalize_for_match",
    "normalize_npc_dispositions",
    "process_new_npcs",
    "process_npc_details",
    "process_npc_renames",
    "reactivate_npc",
    "resolve_about_npc",
    "retire_distant_npcs",
    "retrieve_memories",
    "sanitize_npc_name",
    "score_importance",
]


# --- matching.py: name lookup, fuzzy matching, sanitization ---
# --- activation.py: TF-IDF scoring, prompt context selection ---
from .activation import (
    activate_npcs_for_prompt,
    compute_npc_tfidf_scores,
)

# --- lifecycle.py: identity merging, retiring, reactivating ---
from .lifecycle import (
    absorb_duplicate_npc,
    description_match_existing_npc,
    is_complete_description,
    merge_npc_identity,
    normalize_disposition,
    normalize_npc_dispositions,
    reactivate_npc,
    retire_distant_npcs,
)
from .matching import (
    apply_name_sanitization,
    edit_distance_le1,
    find_npc,
    fuzzy_match_existing_npc,
    next_npc_id,
    normalize_for_match,
    resolve_about_npc,
    sanitize_npc_name,
)

# --- memory.py: importance scoring, retrieval, consolidation ---
from .memory import (
    consolidate_memory,
    retrieve_memories,
    score_importance,
)

# --- processing.py: narrator metadata → NPC state changes ---
from .processing import (
    process_new_npcs,
    process_npc_details,
    process_npc_renames,
)

# --- bond query: separate module to avoid circular imports ---
from .bond import get_npc_bond
