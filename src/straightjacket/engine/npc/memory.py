#!/usr/bin/env python3
"""NPC memory system: importance scoring, memory retrieval, consolidation."""

import re

from ..emotions_loader import importance_map, keyword_boosts
from ..engine_loader import eng
from ..logging_util import log
from ..models import MemoryEntry, NpcData


def score_importance(emotional_weight: str, event_text: str = "",
                     debug: bool = False):
    """Score the importance of a memory entry (1-10).
    Uses emotional_weight as primary signal, with keyword boosts from event text.
    Handles compound phrases and snake_case.
    If debug=True, returns (score, explanation_string) instead of just score."""
    raw = emotional_weight.lower().strip()
    debug_info = ""
    _imp = importance_map()

    # Direct hit — fast path
    if raw in _imp:
        base = _imp[raw]
        debug_info = f"direct:{raw}={base}"
    else:
        tokens = re.split(r'[_/,;:\s]+|(?:\s+and\s+)|(?:\s+mixed\s+with\s+)', raw)
        tokens = [t.strip() for t in tokens if len(t.strip()) >= 3]

        best = 4  # default for unrecognized emotions
        best_token = "default"
        for token in tokens:
            if token in _imp and _imp[token] > best:
                    best = _imp[token]
                    best_token = f"token:{token}={best}"
        base = best
        debug_info = best_token

    # Keyword boost from event text
    if event_text:
        event_lower = event_text.lower()
        for min_score, keywords in keyword_boosts().items():
            matched_kw = [kw for kw in keywords if kw in event_lower]
            if matched_kw:
                if min_score > base:
                    debug_info += f"+event:{matched_kw[0]}≥{min_score}"
                base = max(base, min_score)
                break

    result = min(10, base)
    if debug:
        return result, debug_info
    return result


def retrieve_memories(npc: NpcData, context_text: str = "", max_count: int = 5,
                      current_scene: int = 0,
                      present_npc_ids: set | None = None) -> list[MemoryEntry]:
    """Retrieve the most relevant memories for an NPC using weighted scoring.
    Score = 0.40 x recency + 0.35 x importance + 0.25 x relevance
    Memories with about_npc matching a present NPC get a +0.6 relevance boost.
    Always includes at least 1 reflection if available."""
    memories = npc.memory
    if not memories:
        return []

    _present = present_npc_ids or set()
    reflections = [m for m in memories if m.type == "reflection"]

    context_words = set()
    if context_text:
        context_words = {w.lower() for w in context_text.split() if len(w) >= 3}

    def _score_memory(mem: MemoryEntry) -> float:
        scene_gap = max(0, current_scene - mem.scene)
        if mem.type == "reflection":
            recency = max(0.6, eng().npc.memory_recency_decay ** scene_gap)
        else:
            recency = eng().npc.memory_recency_decay ** scene_gap

        importance = mem.importance / 10.0

        relevance = 0.0
        if context_words:
            event_words = {w.lower() for w in mem.event.split() if len(w) >= 3}
            overlap = context_words & event_words
            if overlap:
                relevance = min(1.0, len(overlap) / max(3, len(context_words)) * 2)

        if _present and mem.about_npc in _present:
            relevance = min(1.0, relevance + 0.6)

        return 0.40 * recency + 0.35 * importance + 0.25 * relevance

    scored = [(m, _score_memory(m)) for m in memories]
    scored.sort(key=lambda x: x[1], reverse=True)

    result: list[MemoryEntry] = []
    reflection_included = False
    for mem, _score in scored:
        if len(result) >= max_count:
            break
        result.append(mem)
        if mem.type == "reflection":
            reflection_included = True

    if not reflection_included and reflections and result:
        best_ref = max(reflections, key=lambda m: m.importance)
        worst_idx = len(result) - 1
        if result[worst_idx].type != "reflection":
            result[worst_idx] = best_ref

    return result


def consolidate_memory(npc: NpcData) -> None:
    """Intelligent memory consolidation replacing simple FIFO.
    Keeps: all reflections (max eng().npc.max_reflections, newest) +
           observations sorted by importance then recency (max eng().npc.max_observations).
    Total never exceeds eng().npc.max_memory_entries."""
    memories = npc.memory
    if len(memories) <= eng().npc.max_memory_entries:
        return

    reflections = [m for m in memories if m.type == "reflection"]
    observations = [m for m in memories if m.type != "reflection"]

    kept_reflections = reflections[-eng().npc.max_reflections:]
    obs_budget = eng().npc.max_memory_entries - len(kept_reflections)

    if len(observations) <= obs_budget:
        kept_observations = observations
    else:
        recency_budget = max(3, int(obs_budget * 0.6))
        importance_budget = obs_budget - recency_budget

        by_recency = sorted(observations, key=lambda m: m.scene, reverse=True)
        kept_by_recency = by_recency[:recency_budget]

        kept_ids = {id(m) for m in kept_by_recency}
        remaining = [m for m in observations if id(m) not in kept_ids]
        by_importance = sorted(remaining, key=lambda m: m.importance, reverse=True)
        kept_by_importance = by_importance[:importance_budget]

        kept_observations = kept_by_recency + kept_by_importance

    all_kept = kept_reflections + kept_observations
    all_kept.sort(key=lambda m: m.scene)

    npc.memory = all_kept
    removed = len(memories) - len(all_kept)
    if removed > 0:
        log(f"[NPC] Consolidated {npc.name} memory: "
            f"{len(memories)} -> {len(all_kept)} ({removed} removed, "
            f"{len(kept_reflections)} reflections, {len(kept_observations)} observations)")
