import inspect
from typing import Any

from straightjacket.engine.gamemaster.config import gm

ANTHROPIC_UNION_LIMIT = 16
_TWELVE_NPCS = [f"npc_{i}" for i in range(1, 13)]


def _loose_objects(node: Any, path: str, out: list[str]) -> None:
    if isinstance(node, dict):
        kind = node.get("type")
        if kind == "object" or (isinstance(kind, list) and "object" in kind):
            properties = set(node.get("properties", {}))
            required = set(node.get("required", []))
            if properties != required:
                out.append(f"{path}: not required {sorted(properties - required)}")
        for key, value in node.items():
            _loose_objects(value, f"{path}.{key}", out)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _loose_objects(value, f"{path}[{index}]", out)


def _unions(node: Any) -> int:
    if isinstance(node, dict):
        own = 1 if "anyOf" in node or isinstance(node.get("type"), list) else 0
        return own + sum(_unions(value) for value in node.values())
    if isinstance(node, list):
        return sum(_unions(value) for value in node)
    return 0


def _every_schema() -> dict[str, dict[str, Any]]:
    from straightjacket.engine.ai import schemas

    built = {
        name: builder()
        for name, builder in sorted(inspect.getmembers(schemas, inspect.isfunction))
        if name.startswith("get_")
        and builder.__module__ == schemas.__name__
        and all(p.default is not inspect.Parameter.empty for p in inspect.signature(builder).parameters.values())
    }
    assert built
    return {
        **built,
        "correction with twelve known NPCs": schemas.get_correction_output_schema(_TWELVE_NPCS),
        "director with twelve reflections": schemas.get_director_output_schema(_TWELVE_NPCS),
        "metadata with twelve known NPCs": schemas.get_narrator_metadata_schema(_TWELVE_NPCS),
        "brain with every choice": schemas.get_brain_output_schema(
            ["adventure/face_danger"],
            ["iron"],
            ["infiltrator#0"],
            _TWELVE_NPCS,
            ["track_1"],
            ["A danger"],
            ["threat_1"],
        ),
    }


def test_every_schema_requires_all_its_properties(load_engine: None) -> None:
    problems: list[str] = []
    for name, schema in _every_schema().items():
        _loose_objects(schema, name, problems)
    assert problems == []


def test_every_schema_stays_within_anthropics_limit_on_union_typed_fields(load_engine: None) -> None:
    over = {
        name: _unions(schema) for name, schema in _every_schema().items() if _unions(schema) > ANTHROPIC_UNION_LIMIT
    }
    assert over == {}


def test_the_checks_see_a_property_that_is_not_required_and_every_kind_of_union() -> None:
    problems: list[str] = []
    _loose_objects({"type": "object", "properties": {"a": {}, "b": {}}, "required": ["a"]}, "demo", problems)
    assert problems == ["demo: not required ['b']"]
    assert _unions({"anyOf": [{"type": "string"}, {"type": "null"}]}) == 1
    assert _unions({"properties": {"a": {"type": ["string", "null"]}, "b": {"type": "string"}}}) == 1


def test_the_brain_schema_always_asks_for_a_track_name_and_rank(load_engine: None) -> None:
    from straightjacket.engine.ai.schemas import get_brain_output_schema

    props = get_brain_output_schema(["combat/enter_the_fray"], [], [], [], [], [], [])["properties"]
    assert props["track_name"] == {"type": "string"}
    assert props["track_rank"]["type"] == "string"
    assert "dangerous" in props["track_rank"]["enum"]


def test_the_brain_schema_offers_exactly_the_moves_it_is_given(load_engine: None) -> None:
    from straightjacket.engine.ai.schemas import get_brain_output_schema

    props = get_brain_output_schema(["dialog", "combat/enter_the_fray"], [], [], [], [], [], [])["properties"]
    assert props["move"]["enum"] == ["combat/enter_the_fray", "dialog"]


def test_the_brain_schema_offers_the_stats_it_is_given_beside_no_stat_and_the_pick_methods(load_engine: None) -> None:
    from straightjacket.engine.ai.schemas import get_brain_output_schema

    props = get_brain_output_schema(["adventure/face_danger"], ["grit", "guile"], [], [], [], [], [])["properties"]
    assert props["stat"]["enum"] == ["grit", "guile", "none", "highest", "lowest"]


def test_the_metadata_extraction_names_only_known_npcs(load_engine: None) -> None:
    from straightjacket.engine.ai.schemas import get_narrator_metadata_schema

    schema = get_narrator_metadata_schema(["npc_2", "npc_1"])
    for field in ("npc_renames", "npc_details"):
        assert schema["properties"][field]["items"]["properties"]["npc_id"]["enum"] == ["npc_1", "npc_2"]
        assert get_narrator_metadata_schema([])["properties"][field]["maxItems"] == 0


def test_a_correction_names_only_known_npcs(load_engine: None) -> None:
    from straightjacket.engine.ai.schemas import get_correction_output_schema
    from straightjacket.engine.engine_loader import eng

    op = get_correction_output_schema(["npc_2", "npc_1"])["properties"]["state_ops"]["items"]["properties"]
    assert op["op"]["enum"] == eng().correction.ops
    for field in ("npc_id", "merge_source_id"):
        assert op[field]["anyOf"][0]["enum"] == ["npc_1", "npc_2"]
        no_npcs = get_correction_output_schema([])["properties"]["state_ops"]["items"]["properties"][field]
        assert no_npcs == {"type": "null"}


def test_a_correction_can_set_only_a_known_disposition_and_npc_status(load_engine: None) -> None:
    from straightjacket.engine.ai.schemas import get_correction_output_schema

    op = get_correction_output_schema(["npc_1"])["properties"]["state_ops"]["items"]
    fields = next(branch for branch in op["properties"]["fields"]["anyOf"] if branch.get("type") == "object")

    def choices(field: str) -> list[str]:
        values: list[str] = next(
            branch for branch in fields["properties"][field]["anyOf"] if branch.get("type") == "string"
        )["enum"]
        return values

    assert choices("disposition") == sorted(gm().enums.dispositions)
    assert choices("status") == sorted(gm().enums.npc_statuses)
    assert "guarded" not in choices("disposition")
    assert "dead" not in choices("status")
