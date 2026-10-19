import re

from ...emotions_loader import importance_map, keyword_boosts
from ...logging_util import log
from ...models import MemoryEntry, NpcData
from ..config import gm


def score_importance(emotional_weight: str, event_text: str) -> int:
    raw = emotional_weight.lower().strip()
    _imp = importance_map()
    _mem_cfg = gm().memory

    if raw in _imp:
        base = _imp[raw]
    else:
        tokens = re.split(_mem_cfg.emotion_split_pattern, raw)
        tokens = [t.strip() for t in tokens if len(t.strip()) >= _mem_cfg.min_token_length]
        base = max([_imp[t] for t in tokens if t in _imp] + [_mem_cfg.unknown_emotion_importance])

    event_lower = event_text.lower()
    for min_score, keywords in keyword_boosts().items():
        if any(kw in event_lower for kw in keywords):
            base = max(base, min_score)
            break

    return min(_mem_cfg.importance_max, base)


def recent_observations(npc: NpcData) -> list[MemoryEntry]:
    return [m for m in npc.memory if m.type == "observation"][-gm().npc.reflection_observation_window :]


def retrieve_memories(
    npc: NpcData,
    *,
    context_text: str,
    max_count: int,
    current_scene: int,
    present_npc_ids: frozenset[str] = frozenset(),
) -> list[MemoryEntry]:
    memories = npc.memory
    reflections = [m for m in memories if m.type == "reflection"]
    _w = gm().memory_retrieval_weights
    _mem_cfg = gm().memory
    w_recency = _w.recency
    w_importance = _w.importance
    w_relevance = _w.relevance
    recency_floor = gm().npc.reflection_recency_floor
    about_boost = gm().npc.about_npc_relevance_boost

    context_words = {w.lower() for w in context_text.split() if len(w) >= _mem_cfg.min_token_length}

    def _score_memory(mem: MemoryEntry) -> float:
        scene_gap = max(0, current_scene - mem.scene)
        if mem.type == "reflection":
            recency = max(recency_floor, gm().npc.memory_recency_decay ** scene_gap)
        else:
            recency = gm().npc.memory_recency_decay ** scene_gap

        importance = mem.importance / _mem_cfg.importance_max

        relevance = 0.0
        if context_words:
            event_words = {w.lower() for w in mem.event.split() if len(w) >= _mem_cfg.min_token_length}
            overlap = context_words & event_words
            if overlap:
                relevance = min(
                    1.0,
                    len(overlap)
                    / max(_mem_cfg.relevance_min_context_words, len(context_words))
                    * _mem_cfg.overlap_scale,
                )

        if present_npc_ids and mem.about_npc in present_npc_ids:
            relevance = min(1.0, relevance + about_boost)

        return w_recency * recency + w_importance * importance + w_relevance * relevance

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
        result[-1] = max(reflections, key=lambda m: m.importance)

    return result


def consolidate_memory(npc: NpcData) -> None:
    memories = npc.memory
    if len(memories) <= gm().npc.max_memory_entries:
        return

    reflections = [m for m in memories if m.type == "reflection"]
    observations = [m for m in memories if m.type != "reflection"]

    kept_reflections = reflections[-gm().npc.max_reflections :]
    obs_budget = gm().npc.max_memory_entries - len(kept_reflections)

    if len(observations) <= obs_budget:
        kept_observations = observations
    else:
        recency_budget = max(gm().memory.consolidation_floor, int(obs_budget * gm().npc.consolidation_recency_ratio))
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
    log(
        f"[NPC] Consolidated {npc.name} memory: "
        f"{len(memories)} -> {len(all_kept)} ({len(memories) - len(all_kept)} removed, "
        f"{len(kept_reflections)} reflections, {len(kept_observations)} observations)"
    )
