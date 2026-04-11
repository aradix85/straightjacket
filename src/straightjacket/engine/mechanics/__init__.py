#!/usr/bin/env python3
"""Straightjacket game mechanics.

Re-exports all public symbols from submodules. Existing imports
(``from .mechanics import X``) continue to work unchanged.

Implementation split across:
- world.py: location matching, chaos, time, pacing, story structure
- resolvers.py: position, effect, time progression, move category
- consequences.py: dice, consequences, clocks, momentum, consequence sentences
- stance_gate.py: NPC stance resolution, information gating
- engine_memories.py: memory emotion derivation, engine memories, scene context
"""

__all__ = [
    "NpcStance",
    "_move_category",
    "_time_phases",
    "advance_time",
    "apply_brain_location_time",
    "apply_consequences",
    "can_burn_momentum",
    "check_chaos_interrupt",
    "check_npc_agency",
    "choose_story_structure",
    "compute_npc_gate",
    "derive_memory_emotion",
    "generate_consequence_sentences",
    "generate_engine_memories",
    "generate_scene_context",
    "get_pacing_hint",
    "locations_match",
    "purge_old_fired_clocks",
    "record_scene_intensity",
    "resolve_effect",
    "resolve_npc_stance",
    "resolve_position",
    "resolve_time_progression",
    "roll_action",
    "tick_autonomous_clocks",
    "update_chaos_factor",
    "update_location",
]

from .consequences import (
    _pick_template,
    _resolve_consequence_sentence,
    apply_consequences,
    can_burn_momentum,
    check_npc_agency,
    generate_consequence_sentences,
    purge_old_fired_clocks,
    roll_action,
    tick_autonomous_clocks,
)
from .engine_memories import (
    derive_memory_emotion,
    generate_engine_memories,
    generate_scene_context,
)
from .resolvers import (
    _move_category,
    resolve_effect,
    resolve_position,
    resolve_time_progression,
)
from .stance_gate import (
    NpcStance,
    compute_npc_gate,
    resolve_npc_stance,
)
from .world import (
    _time_phases,
    advance_time,
    apply_brain_location_time,
    check_chaos_interrupt,
    choose_story_structure,
    get_pacing_hint,
    locations_match,
    record_scene_intensity,
    update_chaos_factor,
    update_location,
)
