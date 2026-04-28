from ..datasworn.moves import get_moves
from ..datasworn.settings import list_packages
from ..engine_loader import eng


def _str() -> dict:
    return {"type": "string"}


def _str_enum(enum: list[str]) -> dict:
    return {"type": "string", "enum": enum}


def _str_with_desc(desc: str) -> dict:
    return {"type": "string", "description": desc}


def _int() -> dict:
    return {"type": "integer"}


def _bool() -> dict:
    return {"type": "boolean"}


def _bool_with_desc(desc: str) -> dict:
    return {"type": "boolean", "description": desc}


def _nullable(typ: str) -> dict:
    return {"anyOf": [{"type": typ}, {"type": "null"}]}


def _nullable_str() -> dict:
    return _nullable("string")


def _nullable_obj(props: dict) -> dict:
    return {"anyOf": [_obj(props), {"type": "null"}]}


def _arr(item_schema: dict) -> dict:
    return {"type": "array", "items": item_schema}


def _str_arr() -> dict:
    return _arr({"type": "string"})


def _obj(props: dict) -> dict:
    return {
        "type": "object",
        "properties": props,
        "required": list(props.keys()),
        "additionalProperties": False,
    }


def _obj_root(props: dict, title: str) -> dict:
    return {
        "type": "object",
        "properties": props,
        "required": list(props.keys()),
        "additionalProperties": False,
        "title": title,
    }


_brain_cache = None
_correction_cache: dict | None = None
_director_cache: dict | None = None
_story_architect_cache: dict | None = None


def get_brain_output_schema() -> dict:
    global _brain_cache
    if _brain_cache is None:
        _e = eng()
        stat_names = list(_e.stats.names)

        all_move_keys: set[str] = set()
        for setting_id in list_packages():
            moves = get_moves(setting_id)
            all_move_keys.update(k for k, m in moves.items() if m.roll_type not in ("no_roll", "special_track"))

        all_move_keys.update(_e.engine_moves.keys())

        rank_enum = sorted(_e.progress.track_types["default"].ticks_per_mark.keys())

        _brain_cache = _obj_root(
            {
                "type": _str_enum(["action"]),
                "move": _str_enum(sorted(all_move_keys)),
                "stat": _str_enum(stat_names),
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
            },
            _e.ai_text.schema_titles["brain_output"],
        )
    return _brain_cache


def get_director_output_schema() -> dict:
    global _director_cache
    if _director_cache is None:
        _e = eng()
        _director_cache = _obj_root(
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
                            "tone_key": _str_enum(list(_e.enums.tone_keys)),
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
            },
            _e.ai_text.schema_titles["director_output"],
        )
    return _director_cache


def get_story_architect_output_schema() -> dict:
    global _story_architect_cache
    if _story_architect_cache is None:
        _e = eng()
        _story_architect_cache = _obj_root(
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
                            "dramatic_weight": _str_enum(list(_e.enums.dramatic_weights)),
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
            },
            _e.ai_text.schema_titles["story_architect_output"],
        )
    return _story_architect_cache


_chapter_summary_cache: dict | None = None


def get_chapter_summary_schema() -> dict:
    global _chapter_summary_cache
    if _chapter_summary_cache is None:
        _chapter_summary_cache = _obj_root(
            {
                "title": _str(),
                "summary": _str(),
                "unresolved_threads": _str_arr(),
                "character_growth": _str(),
                "npc_evolutions": _arr(_obj({"name": _str(), "projection": _str()})),
                "thematic_question": _str(),
                "post_story_location": _str(),
            },
            eng().ai_text.schema_titles["chapter_summary_output"],
        )
    return _chapter_summary_cache


_metadata_cache: dict | None = None


def get_narrator_metadata_schema() -> dict:
    global _metadata_cache
    if _metadata_cache is None:
        _e = eng()
        dispositions = list(_e.enums.dispositions)
        _metadata_cache = _obj_root(
            {
                "new_npcs": _arr(
                    _obj(
                        {
                            "name": _str(),
                            "description": _str(),
                            "disposition": _str_enum(dispositions),
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
            },
            _e.ai_text.schema_titles["narrator_metadata"],
        )
    return _metadata_cache


_opening_cache: dict | None = None


def get_opening_setup_schema() -> dict:
    global _opening_cache
    if _opening_cache is None:
        _e = eng()
        dispositions = list(_e.enums.dispositions)
        time_phases = list(_e.enums.time_phases)
        clock_types = [ct for ct in _e.enums.clock_types if ct != "scheme"]
        _opening_cache = _obj_root(
            {
                "npcs": _arr(
                    _obj(
                        {
                            "name": _str(),
                            "description": _str(),
                            "agenda": _str(),
                            "instinct": _str(),
                            "secrets": _str_arr(),
                            "disposition": _str_enum(dispositions),
                        }
                    )
                ),
                "clocks": _arr(
                    _obj(
                        {
                            "id": _str(),
                            "name": _str(),
                            "clock_type": _str_enum(clock_types),
                            "segments": _int(),
                            "filled": _int(),
                            "trigger_description": _str(),
                            "owner": _str(),
                        }
                    )
                ),
                "location": _str(),
                "scene_context": _str(),
                "time_of_day": _str_enum(time_phases),
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
            },
            _e.ai_text.schema_titles["opening_setup"],
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
        _correction_cache = _obj_root(
            {
                "correction_source": _str_enum(["input_misread", "state_error"]),
                "corrected_input": _str(),
                "reroll_needed": _bool(),
                "corrected_stat": _str_enum(stat_names),
                "narrator_guidance": _str(),
                "director_useful": _bool(),
                "state_ops": _arr(
                    _obj(
                        {
                            "op": _str_enum(list(_e.enums.correction_ops)),
                            "npc_id": _nullable_str(),
                            "split_name": _nullable_str(),
                            "split_description": _nullable_str(),
                            "merge_source_id": _nullable_str(),
                            "fields": _nullable_obj(field_props),
                            "value": _nullable_str(),
                        }
                    )
                ),
            },
            _e.ai_text.schema_titles["correction_output"],
        )
    return _correction_cache


_revelation_check_cache: dict | None = None


def get_revelation_check_schema() -> dict:
    global _revelation_check_cache
    if _revelation_check_cache is None:
        _e = eng()
        descs = _e.ai_text.schema_descriptions["revelation_check"]
        _revelation_check_cache = _obj_root(
            {
                "revelation_confirmed": _bool_with_desc(descs["revelation_confirmed"]),
                "reasoning": _str_with_desc(descs["reasoning"]),
            },
            _e.ai_text.schema_titles["revelation_check"],
        )
    return _revelation_check_cache
