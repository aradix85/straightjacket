from typing import Any

from ..engine_loader import eng
from ..gamemaster.config import gm
from ..ruleset.config import rules
from ..ruleset.moves import PICK_METHODS
from ..ruleset.progress import ranks


def _str() -> dict[str, Any]:
    return {"type": "string"}


def _str_enum(enum: list[str]) -> dict[str, Any]:
    return {"type": "string", "enum": enum}


def _bool() -> dict[str, Any]:
    return {"type": "boolean"}


def _nullable_str() -> dict[str, Any]:
    return {"anyOf": [{"type": "string"}, {"type": "null"}]}


def _nullable_obj(props: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [_obj(props), {"type": "null"}]}


def _arr(item_schema: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": item_schema}


def _str_arr() -> dict[str, Any]:
    return _arr({"type": "string"})


def _obj(props: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": list(props.keys()),
        "additionalProperties": False,
    }


def _obj_root(props: dict[str, Any], title: str) -> dict[str, Any]:
    return {**_obj(props), "title": title}


def _nullable_enum(values: list[str]) -> dict[str, Any]:
    if not values:
        return {"type": "null"}
    return {"anyOf": [{"type": "string", "enum": sorted(set(values))}, {"type": "null"}]}


def _fact_requests(npc_ids: list[str]) -> dict[str, Any]:
    cfg = gm().fact_resolution
    place_types = sorted(name for name, spec in cfg.types.items() if spec.subject == "place")
    npc_types = sorted(name for name, spec in cfg.types.items() if spec.subject == "npc")
    branches: list[dict[str, Any]] = []
    if place_types:
        branches.append(_obj({"fact_type": _str_enum(place_types), "about": _str_enum([cfg.place_reference])}))
    if npc_types and npc_ids:
        branches.append(_obj({"fact_type": _str_enum(npc_types), "about": _str_enum(sorted(set(npc_ids)))}))
    if not branches:
        return {"type": "array", "items": {"type": "null"}, "maxItems": 0}
    return {"type": "array", "items": {"anyOf": branches}, "maxItems": cfg.max_per_turn}


def get_brain_output_schema(
    move_keys: list[str],
    stat_names: list[str],
    bonus_ids: list[str],
    npc_ids: list[str],
    track_ids: list[str],
    clock_names: list[str],
    threat_ids: list[str],
) -> dict[str, Any]:
    rank_enum = sorted(ranks())
    return _obj_root(
        {
            "move": _str_enum(sorted(move_keys)),
            "stat": _str_enum([*stat_names, eng().ai_text.no_stat, *PICK_METHODS]),
            "approach": _str(),
            "target_npc": _nullable_enum(npc_ids),
            "dialog_only": _bool(),
            "player_intent": _str(),
            "world_addition": _nullable_str(),
            "location_change": _nullable_obj(
                {"name": _str(), "kind": _str_enum(sorted(gm().generation.place_categories))}
            ),
            "track_name": _str(),
            "track_rank": _str_enum(rank_enum),
            "target_track": _nullable_enum(track_ids),
            "target_clock": _nullable_enum(clock_names),
            "target_threat": _nullable_enum(threat_ids),
            "bonus_id": _nullable_enum(bonus_ids),
            "undetermined_facts": _fact_requests(npc_ids),
            "boasts": {
                "type": "array",
                "items": _str_enum(sorted(rules().boasts.options)),
                "maxItems": rules().boasts.max_per_roll,
            },
        },
        eng().ai_text.schema_titles["brain_output"],
    )


def get_director_output_schema(reflection_ids: list[str]) -> dict[str, Any]:
    return _obj_root(
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
            "npc_reflections": _obj(
                {
                    npc_id: _obj(
                        {
                            "reflection": _str(),
                            "tone": _str(),
                            "tone_key": _str_enum(list(gm().enums.tone_keys)),
                            "updated_description": _str(),
                            "about_npc": _str(),
                            "agenda": _str(),
                            "instinct": _str(),
                            "updated_agenda": _str(),
                            "updated_arc": _str(),
                        }
                    )
                    for npc_id in reflection_ids
                }
            ),
            "arc_notes": _str(),
        },
        eng().ai_text.schema_titles["director_output"],
    )


def _counted_arr(item_schema: dict[str, Any], count: int) -> dict[str, Any]:
    return {"type": "array", "items": item_schema, "minItems": count, "maxItems": count}


def get_blueprint_voicing_schema(acts: int, endings: int) -> dict[str, Any]:
    return _obj_root(
        {
            "central_conflict": _str(),
            "antagonist_force": _str(),
            "thematic_thread": _str(),
            "acts": _counted_arr(
                _obj(
                    {
                        "title": _str(),
                        "goal": _str(),
                        "mood": _str(),
                        "transition_trigger": _str(),
                    }
                ),
                acts,
            ),
            "revelations": _counted_arr(_obj({"content": _str()}), acts),
            "possible_endings": _counted_arr(_obj({"type": _str(), "description": _str()}), endings),
        },
        eng().ai_text.schema_titles["blueprint_voicing_output"],
    )


def _about_known_npcs(npc_ids: list[str], props: dict[str, Any]) -> dict[str, Any]:
    if not npc_ids:
        return {"type": "array", "items": {"type": "null"}, "maxItems": 0}
    return _arr(_obj({"npc_id": _str_enum(sorted(set(npc_ids))), **props}))


def get_narrator_metadata_schema(npc_ids: list[str]) -> dict[str, Any]:
    dispositions = list(gm().enums.dispositions)
    return _obj_root(
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
            "npc_renames": _about_known_npcs(npc_ids, {"new_name": _str()}),
            "npc_details": _about_known_npcs(npc_ids, {"full_name": _nullable_str(), "description": _nullable_str()}),
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
        eng().ai_text.schema_titles["narrator_metadata"],
    )


def get_opening_setup_schema() -> dict[str, Any]:
    return _obj_root(
        {
            "npcs": _arr(
                _obj(
                    {
                        "name": _str(),
                        "description": _str(),
                        "agenda": _str(),
                        "instinct": _str(),
                        "secrets": _str_arr(),
                        "disposition": _str_enum(list(gm().enums.dispositions)),
                    }
                )
            ),
            "location": _str(),
            "scene_context": _str(),
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
        eng().ai_text.schema_titles["opening_setup"],
    )


def get_correction_output_schema(npc_ids: list[str]) -> dict[str, Any]:
    field_props: dict[str, Any] = {}
    for fname in eng().correction.npc_edit_fields:
        if fname == "aliases":
            field_props[fname] = {"anyOf": [_str_arr(), {"type": "null"}]}
        elif fname == "disposition":
            field_props[fname] = _nullable_enum(list(gm().enums.dispositions))
        elif fname == "status":
            field_props[fname] = _nullable_enum(list(gm().enums.npc_statuses))
        else:
            field_props[fname] = _nullable_str()
    return _obj_root(
        {
            "correction_source": _str_enum(["input_misread", "state_error"]),
            "corrected_input": _str(),
            "narrator_guidance": _str(),
            "director_useful": _bool(),
            "state_ops": _arr(
                _obj(
                    {
                        "op": _str_enum(list(eng().correction.ops)),
                        "npc_id": _nullable_enum(npc_ids),
                        "split_name": _nullable_str(),
                        "split_description": _nullable_str(),
                        "merge_source_id": _nullable_enum(npc_ids),
                        "fields": _nullable_obj(field_props),
                        "value": _nullable_str(),
                    }
                )
            ),
        },
        eng().ai_text.schema_titles["correction_output"],
    )
