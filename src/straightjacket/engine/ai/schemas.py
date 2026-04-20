"""Engine JSON output schemas built from compact specs.

Move and stat enums are config-driven from engine.yaml.
Schema builder helpers eliminate repeated boilerplate.
Field-level `description=` strings sent to AI as part of the
structured-output JSON schema live in `engine.yaml ai_text.schema_descriptions`,
keyed by schema name.
"""

from ..datasworn.moves import get_moves
from ..datasworn.settings import list_packages
from ..engine_loader import eng


def _str(enum: list[str] | None = None, desc: str | None = None) -> dict:
    d: dict = {"type": "string"}
    if enum:
        d["enum"] = enum
    if desc:
        d["description"] = desc
    return d


def _int() -> dict:
    return {"type": "integer"}


def _bool(desc: str | None = None) -> dict:
    d: dict = {"type": "boolean"}
    if desc:
        d["description"] = desc
    return d


def _nullable(typ: str) -> dict:
    return {"anyOf": [{"type": typ}, {"type": "null"}]}


def _nullable_str() -> dict:
    return _nullable("string")


def _nullable_int() -> dict:
    return _nullable("integer")


def _nullable_obj(props: dict) -> dict:
    return {"anyOf": [_obj(props), {"type": "null"}]}


def _arr(item_schema: dict) -> dict:
    return {"type": "array", "items": item_schema}


def _str_arr() -> dict:
    return _arr({"type": "string"})


def _obj(props: dict, extra_required: list[str] | None = None) -> dict:
    """Build a strict JSON object schema. All keys are required by default."""
    required = extra_required or list(props.keys())
    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


_brain_cache = None
_correction_cache: dict | None = None
_director_cache: dict | None = None
_story_architect_cache: dict | None = None


def clear_brain_cache() -> None:
    """Invalidate cached schemas. Called by reload_engine()."""
    global _brain_cache, _metadata_cache, _opening_cache, _correction_cache
    global _revelation_check_cache, _validator_cache, _architect_validator_cache
    global _director_cache, _story_architect_cache
    _brain_cache = None
    _metadata_cache = None
    _opening_cache = None
    _correction_cache = None
    _revelation_check_cache = None
    _validator_cache = None
    _architect_validator_cache = None
    _director_cache = None
    _story_architect_cache = None


def get_brain_output_schema() -> dict:
    global _brain_cache
    if _brain_cache is None:
        _e = eng()
        stat_names = list(_e.stats.names)

        # Build move enum: all Datasworn moves across every discovered setting + engine-specific
        all_move_keys: set[str] = set()
        for setting_id in list_packages():
            moves = get_moves(setting_id)
            all_move_keys.update(k for k, m in moves.items() if m.roll_type not in ("no_roll", "special_track"))

        # Engine-specific moves — from engine.yaml, single source of truth
        all_move_keys.update(_e.engine_moves.keys())

        # Progress ranks from engine.yaml
        rank_enum = sorted(_e.progress.track_types["default"].ticks_per_mark.keys())

        _brain_cache = _obj(
            {
                "type": _str(["action"]),
                "move": _str(sorted(all_move_keys)),
                "stat": _str(stat_names),
                "approach": _str(),
                "target_npc": _nullable_str(),
                "dialog_only": _bool(),
                "player_intent": _str(),
                "world_addition": _nullable_str(),
                "location_change": _nullable_str(),
                "track_name": _nullable_str(),
                "track_rank": {
                    "anyOf": [
                        {"type": "string", "enum": rank_enum},
                        {"type": "null"},
                    ]
                },
                "target_track": _nullable_str(),
                "fate_question": _nullable_str(),
                "oracle_table": _nullable_str(),
            }
        )
    return _brain_cache


def get_director_output_schema() -> dict:
    global _director_cache
    if _director_cache is None:
        _e = eng()
        _director_cache = _obj(
            {
                "scene_summary": _str(),
                "narrator_guidance": _str(),
                "npc_guidance": _arr(
                    _obj(
                        {
                            "npc_id": _str(),
                            "guidance": _str(),
                        }
                    )
                ),
                "npc_reflections": _arr(
                    _obj(
                        {
                            "npc_id": _str(),
                            "reflection": _str(),
                            "tone": _str(),
                            "tone_key": _str(list(_e.enums.tone_keys)),
                            "updated_description": _nullable_str(),
                            "about_npc": _nullable_str(),
                            "agenda": _nullable_str(),
                            "instinct": _nullable_str(),
                            "updated_agenda": _nullable_str(),
                            "updated_arc": _nullable_str(),
                        }
                    )
                ),
                "arc_notes": _str(),
            }
        )
    return _director_cache


def get_story_architect_output_schema() -> dict:
    global _story_architect_cache
    if _story_architect_cache is None:
        _e = eng()
        _story_architect_cache = _obj(
            {
                "central_conflict": _str(),
                "antagonist_force": _str(),
                "thematic_thread": _str(),
                "acts": _arr(
                    _obj(
                        {
                            "phase": _str(),
                            "title": _str(),
                            "goal": _str(),
                            "scene_range": _arr(_int()),
                            "mood": _str(),
                            "transition_trigger": _str(),
                        }
                    )
                ),
                "revelations": _arr(
                    _obj(
                        {
                            "id": _str(),
                            "content": _str(),
                            "earliest_scene": _int(),
                            "dramatic_weight": _str(list(_e.enums.dramatic_weights)),
                        }
                    )
                ),
                "possible_endings": _arr(
                    _obj(
                        {
                            "type": _str(),
                            "description": _str(),
                        }
                    )
                ),
            }
        )
    return _story_architect_cache


CHAPTER_SUMMARY_OUTPUT_SCHEMA = _obj(
    {
        "title": _str(),
        "summary": _str(),
        "unresolved_threads": _str_arr(),
        "character_growth": _str(),
        "npc_evolutions": _arr(_obj({"name": _str(), "projection": _str()})),
        "thematic_question": _str(),
        "post_story_location": _str(),
    }
)


_metadata_cache: dict | None = None


def get_narrator_metadata_schema() -> dict:
    """Build narrator metadata schema with config-driven disposition enum."""
    global _metadata_cache
    if _metadata_cache is None:
        _e = eng()
        dispositions = list(_e.enums.dispositions)
        _metadata_cache = _obj(
            {
                "new_npcs": _arr(
                    _obj(
                        {
                            "name": _str(),
                            "description": _str(),
                            "disposition": _str(dispositions),
                        }
                    )
                ),
                "npc_renames": _arr(
                    _obj(
                        {
                            "npc_id": _str(),
                            "new_name": _str(),
                            "reason": _str(),
                        }
                    )
                ),
                "npc_details": _arr(
                    _obj(
                        {
                            "npc_id": _str(),
                            "full_name": _nullable_str(),
                            "description": _nullable_str(),
                            "extra": _nullable_str(),
                        }
                    )
                ),
                "deceased_npcs": _arr(_obj({"npc_id": _str()})),
                "lore_npcs": _arr(
                    _obj(
                        {
                            "name": _str(),
                            "description": _str(),
                        }
                    )
                ),
            }
        )
    return _metadata_cache


_opening_cache: dict | None = None


def get_opening_setup_schema() -> dict:
    """Build opening setup schema with config-driven enums."""
    global _opening_cache
    if _opening_cache is None:
        _e = eng()
        dispositions = list(_e.enums.dispositions)
        time_phases = list(_e.enums.time_phases)
        clock_types = [ct for ct in _e.enums.clock_types if ct != "scheme"]  # Opening only gets threat/progress
        _opening_cache = _obj(
            {
                "npcs": _arr(
                    _obj(
                        {
                            "name": _str(),
                            "description": _str(),
                            "agenda": _str(),
                            "instinct": _str(),
                            "secrets": _str_arr(),
                            "disposition": _str(dispositions),
                        }
                    )
                ),
                "clocks": _arr(
                    _obj(
                        {
                            "id": _str(),
                            "name": _str(),
                            "clock_type": _str(clock_types),
                            "segments": _int(),
                            "filled": _int(),
                            "trigger_description": _str(),
                            "owner": _str(),
                        }
                    )
                ),
                "location": _str(),
                "scene_context": _str(),
                "time_of_day": _str(time_phases),
                "memory_updates": _arr(
                    _obj(
                        {
                            "npc_name": _str(),
                            "event": _str(),
                            "emotional_weight": _str(),
                        }
                    )
                ),
                "deceased_npcs": _arr(_obj({"npc_id": _str()})),
            }
        )
    return _opening_cache


def get_correction_output_schema() -> dict:
    global _correction_cache
    if _correction_cache is None:
        _e = eng()
        stat_names = list(_e.stats.names)
        field_props: dict = {}
        for fname in _e.enums.correction_fields:
            if fname == "aliases":
                field_props[fname] = {"anyOf": [_str_arr(), {"type": "null"}]}
            else:
                field_props[fname] = _nullable_str()
        _correction_cache = _obj(
            {
                "correction_source": _str(["input_misread", "state_error"]),
                "corrected_input": _str(),
                "reroll_needed": _bool(),
                "corrected_stat": _str(stat_names),
                "narrator_guidance": _str(),
                "director_useful": _bool(),
                "state_ops": _arr(
                    _obj(
                        {
                            "op": _str(list(_e.enums.correction_ops)),
                            "npc_id": _nullable_str(),
                            "split_name": _nullable_str(),
                            "split_description": _nullable_str(),
                            "merge_source_id": _nullable_str(),
                            "fields": _nullable_obj(field_props),
                            "value": _nullable_str(),
                        }
                    )
                ),
            }
        )
    return _correction_cache


_revelation_check_cache: dict | None = None


def get_revelation_check_schema() -> dict:
    global _revelation_check_cache
    if _revelation_check_cache is None:
        descs = eng().ai_text.schema_descriptions["revelation_check"]
        _revelation_check_cache = _obj(
            {
                "revelation_confirmed": _bool(descs["revelation_confirmed"]),
                "reasoning": _str(desc=descs["reasoning"]),
            }
        )
    return _revelation_check_cache


_validator_cache: dict | None = None


def get_validator_schema() -> dict:
    global _validator_cache
    if _validator_cache is None:
        descs = eng().ai_text.schema_descriptions["validator"]
        _validator_cache = _obj(
            {
                "pass": _bool(descs["pass"]),
                "violations": _arr(_str()),
                "correction": _str(desc=descs["correction"]),
            }
        )
    return _validator_cache


_architect_validator_cache: dict | None = None


def get_architect_validator_schema() -> dict:
    global _architect_validator_cache
    if _architect_validator_cache is None:
        descs = eng().ai_text.schema_descriptions["architect_validator"]
        _architect_validator_cache = _obj(
            {
                "pass": _bool(descs["pass"]),
                "violations": _arr(_str()),
                "fixed_conflict": _str(desc=descs["fixed_conflict"]),
                "fixed_antagonist": _str(desc=descs["fixed_antagonist"]),
            }
        )
    return _architect_validator_cache
