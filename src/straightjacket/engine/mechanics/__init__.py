"""Straightjacket game mechanics.

Re-exports all public symbols from submodules. Existing imports
(``from .mechanics import X``) continue to work unchanged.

Implementation split across:
- world.py: location matching, chaos, time, pacing, story structure
- resolvers.py: position, effect, time progression, move category
- consequences.py: dice, consequences, clocks, momentum, consequence sentences
- stance_gate.py: NPC stance resolution, information gating
- engine_memories.py: memory emotion derivation, engine memories, scene context
- fate.py: Mythic GME 2e fate chart, fate check, likelihood resolver
- keyed_scenes.py: director-pre-defined scene-start beats that override chaos
- random_events.py: event focus, meaning tables, random event pipeline, list maintenance
"""

__all__ = [
    "LEGACY_TRACKS",
    "NpcStance",
    "add_character_weight",
    "add_thread_weight",
    "advance_asset",
    "advance_time",
    "apply_brain_location_time",
    "apply_npc_carryover",
    "apply_threat_overcome_bonus",
    "build_predecessor_record",
    "can_burn_momentum",
    "check_npc_agency",
    "check_scene",
    "choose_story_structure",
    "compute_npc_gate",
    "consolidate_characters",
    "consolidate_threads",
    "deactivate_thread",
    "derive_memory_emotion",
    "drain_pending_events",
    "evaluate_keyed_scenes",
    "generate_consequence_sentences",
    "generate_engine_memories",
    "generate_random_event",
    "generate_scene_context",
    "get_legacy_track",
    "get_pacing_hint",
    "locations_match",
    "mark_legacy",
    "move_category",
    "pick_template",
    "purge_old_fired_clocks",
    "record_scene_intensity",
    "resolve_consequence_sentence",
    "resolve_effect",
    "resolve_fate",
    "resolve_fate_chart",
    "resolve_fate_check",
    "resolve_likelihood",
    "resolve_npc_stance",
    "resolve_position",
    "resolve_time_progression",
    "roll_action",
    "roll_event_focus",
    "roll_meaning_table",
    "run_inheritance_rolls",
    "seed_successor_legacy",
    "tick_autonomous_clocks",
    "time_phases",
    "update_chaos_factor",
    "update_location",
]

from .consequences import (
    can_burn_momentum,
    check_npc_agency,
    generate_consequence_sentences,
    pick_template,
    purge_old_fired_clocks,
    resolve_consequence_sentence,
    roll_action,
    roll_progress,
    tick_autonomous_clocks,
)
from .engine_memories import (
    derive_memory_emotion,
    generate_engine_memories,
    generate_scene_context,
)
from .fate import (
    resolve_fate,
    resolve_fate_chart,
    resolve_fate_check,
    resolve_likelihood,
)
from .keyed_scenes import (
    evaluate_keyed_scenes,
)
from .legacy import (
    LEGACY_TRACKS,
    advance_asset,
    apply_threat_overcome_bonus,
    get_legacy_track,
    mark_legacy,
)
from .random_events import (
    add_character_weight,
    add_thread_weight,
    consolidate_characters,
    consolidate_threads,
    deactivate_thread,
    drain_pending_events,
    generate_random_event,
    roll_event_focus,
    roll_meaning_table,
)
from .resolvers import (
    move_category,
    resolve_effect,
    resolve_position,
    resolve_time_progression,
)
from .scene import (
    check_scene,
)
from .stance_gate import (
    NpcStance,
    compute_npc_gate,
    resolve_npc_stance,
)
from .succession import (
    apply_npc_carryover,
    build_predecessor_record,
    run_inheritance_rolls,
    seed_successor_legacy,
)
from .world import (
    advance_time,
    apply_brain_location_time,
    choose_story_structure,
    get_pacing_hint,
    locations_match,
    record_scene_intensity,
    time_phases,
    update_chaos_factor,
    update_location,
)
