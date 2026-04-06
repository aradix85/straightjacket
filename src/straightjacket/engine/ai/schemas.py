#!/usr/bin/env python3
"""Engine JSON output schemas built from compact specs.

Move and stat enums are config-driven from engine.yaml.
Schema builder helpers eliminate repeated boilerplate.
"""

from ..engine_loader import eng

# ── Schema builder helpers ────────────────────────────────────

def _str(enum=None, desc=None):
    d = {"type": "string"}
    if enum:
        d["enum"] = enum
    if desc:
        d["description"] = desc
    return d

def _int():
    return {"type": "integer"}
def _bool(desc=None):
    d = {"type": "boolean"}
    if desc:
        d["description"] = desc
    return d

def _nullable(typ):
    return {"anyOf": [{"type": typ}, {"type": "null"}]}

def _nullable_str(): return _nullable("string")
def _nullable_int(): return _nullable("integer")

def _nullable_obj(props):
    return {"anyOf": [_obj(props), {"type": "null"}]}

def _arr(item_schema):
    return {"type": "array", "items": item_schema}

def _str_arr(): return _arr({"type": "string"})

def _obj(props, extra_required=None):
    """Build a strict JSON object schema. All keys are required by default."""
    required = extra_required or list(props.keys())
    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


# ── Brain output (config-driven moves/stats) ─────────────────

_brain_cache = None

def get_brain_output_schema() -> dict:
    global _brain_cache
    if _brain_cache is None:
        _e = eng()
        moves = list(_e.move_stats.keys())
        stat_names = list(_e.stats.names)
        _brain_cache = _obj({
            "type":              _str(["action"]),
            "move":              _str(moves),
            "stat":              _str(stat_names),
            "approach":          _str(),
            "target_npc":        _nullable_str(),
            "dialog_only":       _bool(),
            "player_intent":     _str(),
            "world_addition":    _nullable_str(),
            "position":          _str(["controlled", "risky", "desperate"]),
            "effect":            _str(["limited", "standard", "great"]),
            "dramatic_question": _str(),
            "location_change":   _nullable_str(),
            "time_progression":  _str(["none", "short", "moderate", "long"]),
        })
    return _brain_cache


# ── Director output ───────────────────────────────────────────

DIRECTOR_OUTPUT_SCHEMA = _obj({
    "scene_summary":     _str(),
    "narrator_guidance":  _str(),
    "npc_guidance":       _arr(_obj({
        "npc_id":   _str(),
        "guidance": _str(),
    })),
    "pacing": _str(["tension_rising", "building", "climax", "breather", "resolution"]),
    "npc_reflections": _arr(_obj({
        "npc_id":              _str(),
        "reflection":          _str(),
        "tone":                _str(),
        "tone_key":            _str([
            "neutral", "curious", "wary", "suspicious", "grateful",
            "terrified", "loyal", "conflicted", "betrayed", "devastated",
            "euphoric", "defiant", "guilty", "protective", "angry",
            "devoted", "impressed", "hopeful",
        ]),
        "updated_description": _nullable_str(),
        "about_npc":           _nullable_str(),
        "agenda":              _nullable_str(),
        "instinct":            _nullable_str(),
        "updated_agenda":      _nullable_str(),
        "updated_arc":         _nullable_str(),
    })),
    "arc_notes":      _str(),
    "act_transition": _bool(),
})


# ── Story architect output ────────────────────────────────────

STORY_ARCHITECT_OUTPUT_SCHEMA = _obj({
    "central_conflict": _str(),
    "antagonist_force":  _str(),
    "thematic_thread":   _str(),
    "acts": _arr(_obj({
        "phase":              _str(),
        "title":              _str(),
        "goal":               _str(),
        "scene_range":        _arr(_int()),
        "mood":               _str(),
        "transition_trigger": _str(),
    })),
    "revelations": _arr(_obj({
        "id":              _str(),
        "content":         _str(),
        "earliest_scene":  _int(),
        "dramatic_weight": _str(["low", "medium", "high", "critical"]),
    })),
    "possible_endings": _arr(_obj({
        "type":        _str(),
        "description": _str(),
    })),
})


# ── Chapter summary output ────────────────────────────────────

CHAPTER_SUMMARY_OUTPUT_SCHEMA = _obj({
    "title":              _str(),
    "summary":            _str(),
    "unresolved_threads": _str_arr(),
    "character_growth":   _str(),
    "npc_evolutions":     _arr(_obj({"name": _str(), "projection": _str()})),
    "thematic_question":  _str(),
    "post_story_location": _str(),
})


# ── Narrator metadata output ─────────────────────────────────

NARRATOR_METADATA_SCHEMA = _obj({
    "scene_context":   _str(),
    "location_update": _nullable_str(),
    "time_update":     _nullable_str(),
    "memory_updates": _arr(_obj({
        "npc_id":           _str(),
        "event":            _str(),
        "emotional_weight": _str(),
        "about_npc":        _nullable_str(),
    })),
    "new_npcs": _arr(_obj({
        "name":        _str(),
        "description": _str(),
        "disposition": _str(["neutral", "friendly", "hostile", "wary",
                             "curious", "fearful", "loyal", "distrustful"]),
    })),
    "npc_renames": _arr(_obj({
        "npc_id":   _str(),
        "new_name": _str(),
        "reason":   _str(),
    })),
    "npc_details": _arr(_obj({
        "npc_id":      _str(),
        "full_name":   _nullable_str(),
        "description": _nullable_str(),
        "extra":       _nullable_str(),
    })),
    "deceased_npcs": _arr(_obj({"npc_id": _str()})),
    "lore_npcs": _arr(_obj({
        "name":        _str(),
        "description": _str(),
    })),
})


# ── Opening setup output ─────────────────────────────────────

OPENING_SETUP_SCHEMA = _obj({
    "npcs": _arr(_obj({
        "name":        _str(),
        "description": _str(),
        "agenda":      _str(),
        "instinct":    _str(),
        "secrets":     _str_arr(),
        "disposition": _str(["neutral", "friendly", "hostile", "wary",
                             "curious", "fearful", "loyal", "distrustful"]),
        "bond":        _int(),
        "bond_max":    _int(),
    })),
    "clocks": _arr(_obj({
        "id":                  _str(),
        "name":                _str(),
        "clock_type":          _str(["threat", "progress"]),
        "segments":            _int(),
        "filled":              _int(),
        "trigger_description": _str(),
        "owner":               _str(),
    })),
    "location":       _str(),
    "scene_context":  _str(),
    "time_of_day":    _str(["early_morning", "morning", "midday", "afternoon",
                            "evening", "late_evening", "night", "deep_night"]),
    "memory_updates": _arr(_obj({
        "npc_name":         _str(),
        "event":            _str(),
        "emotional_weight": _str(),
    })),
    "deceased_npcs": _arr(_obj({"npc_id": _str()})),
})


# ── Correction output ─────────────────────────────────────────

CORRECTION_OUTPUT_SCHEMA = _obj({
    "correction_source": _str(["input_misread", "state_error"]),
    "corrected_input":   _str(),
    "reroll_needed":     _bool(),
    "corrected_stat":    _str(["edge", "heart", "iron", "shadow", "wits", "none"]),
    "narrator_guidance": _str(),
    "director_useful":   _bool(),
    "state_ops": _arr(_obj({
        "op":                _str(["npc_edit", "npc_split", "npc_merge",
                                   "location_edit", "scene_context", "time_edit",
                                   "backstory_append"]),
        "npc_id":            _nullable_str(),
        "split_name":        _nullable_str(),
        "split_description": _nullable_str(),
        "merge_source_id":   _nullable_str(),
        "fields": _nullable_obj({
            "name":        _nullable_str(),
            "description": _nullable_str(),
            "disposition": _nullable_str(),
            "agenda":      _nullable_str(),
            "instinct":    _nullable_str(),
            "aliases":     {"anyOf": [_str_arr(), {"type": "null"}]},
            "bond":        _nullable_int(),
        }),
        "value": _nullable_str(),
    })),
})


# ── Revelation check output ──────────────────────────────────

REVELATION_CHECK_SCHEMA = _obj({
    "revelation_confirmed": _bool(
        "True if the narration clearly contains or foreshadows the revelation."),
    "reasoning": _str(desc="One sentence explaining why."),
})


# ── Narrator validator output ─────────────────────────────────

VALIDATOR_SCHEMA = _obj({
    "pass":       _bool("true if narration respects all constraints"),
    "violations": _arr(_str()),
    "correction": _str(desc="One-sentence fix instruction. Empty if pass=true."),
})


# ── Architect validator output ────────────────────────────────

ARCHITECT_VALIDATOR_SCHEMA = _obj({
    "pass":             _bool("true if blueprint respects genre constraints"),
    "violations":       _arr(_str()),
    "fixed_conflict":   _str(desc="Rewritten central_conflict for genre. Empty if pass=true."),
    "fixed_antagonist": _str(desc="Rewritten antagonist_force for genre. Empty if pass=true."),
})
