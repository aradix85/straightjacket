import inspect
from collections.abc import Callable
from typing import Any


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


def _schema_builders() -> list[tuple[str, Callable[[], dict[str, Any]]]]:
    from straightjacket.engine.ai import schemas

    return [
        (name, builder)
        for name, builder in sorted(inspect.getmembers(schemas, inspect.isfunction))
        if name.startswith("get_")
        and builder.__module__ == schemas.__name__
        and all(p.default is not inspect.Parameter.empty for p in inspect.signature(builder).parameters.values())
    ]


def test_every_engine_schema_requires_all_its_properties(load_engine: None) -> None:
    builders = _schema_builders()
    assert builders
    problems: list[str] = []
    for name, builder in builders:
        _loose_objects(builder(), name, problems)
    assert problems == []


def test_a_property_that_is_not_required_is_reported() -> None:
    problems: list[str] = []
    _loose_objects({"type": "object", "properties": {"a": {}, "b": {}}, "required": ["a"]}, "demo", problems)
    assert problems == ["demo: not required ['b']"]


def test_the_brain_schema_requires_all_its_properties(load_engine: None) -> None:
    from straightjacket.engine.ai.schemas import get_brain_output_schema

    problems: list[str] = []
    _loose_objects(
        get_brain_output_schema(["adventure/face_danger"], ["infiltrator#0"], ["npc_1"], []), "brain", problems
    )
    assert problems == []


def test_the_brain_schema_always_asks_for_a_track_name_and_rank(load_engine: None) -> None:
    from straightjacket.engine.ai.schemas import get_brain_output_schema

    props = get_brain_output_schema(["combat/enter_the_fray"], [], [], [])["properties"]
    assert props["track_name"] == {"type": "string"}
    assert props["track_rank"]["type"] == "string"
    assert "dangerous" in props["track_rank"]["enum"]


def test_the_director_schema_requires_all_its_properties(load_engine: None) -> None:
    from straightjacket.engine.ai.schemas import get_director_output_schema

    problems: list[str] = []
    _loose_objects(get_director_output_schema(["npc_1"]), "director", problems)
    assert problems == []


ANTHROPIC_UNION_LIMIT = 16


def _unions(node: Any) -> int:
    if isinstance(node, dict):
        own = 1 if "anyOf" in node or isinstance(node.get("type"), list) else 0
        return own + sum(_unions(value) for value in node.values())
    if isinstance(node, list):
        return sum(_unions(value) for value in node)
    return 0


def test_every_schema_stays_within_anthropics_limit_on_union_typed_fields(load_engine: None) -> None:
    from straightjacket.engine.ai.schemas import get_brain_output_schema, get_director_output_schema

    many_npcs = [f"npc_{i}" for i in range(1, 13)]
    schemas = {name: builder() for name, builder in _schema_builders()}
    schemas["director with twelve reflections"] = get_director_output_schema(many_npcs)
    schemas["brain with every choice"] = get_brain_output_schema(
        ["adventure/face_danger"], ["infiltrator#0"], many_npcs, ["track_1"]
    )
    over = {name: _unions(schema) for name, schema in schemas.items() if _unions(schema) > ANTHROPIC_UNION_LIMIT}
    assert over == {}


def test_the_union_count_sees_any_of_and_type_lists() -> None:
    assert _unions({"anyOf": [{"type": "string"}, {"type": "null"}]}) == 1
    assert _unions({"properties": {"a": {"type": ["string", "null"]}, "b": {"type": "string"}}}) == 1


def test_a_correction_can_set_only_a_known_disposition(load_engine: None) -> None:
    from straightjacket.engine.ai.schemas import get_correction_output_schema
    from straightjacket.engine.engine_loader import eng

    op = get_correction_output_schema()["properties"]["state_ops"]["items"]
    fields = next(branch for branch in op["properties"]["fields"]["anyOf"] if branch.get("type") == "object")
    choices = next(branch for branch in fields["properties"]["disposition"]["anyOf"] if branch.get("type") == "string")
    assert choices["enum"] == sorted(eng().enums.dispositions)
    assert "guarded" not in choices["enum"]


def test_a_correction_can_set_only_a_known_npc_status(load_engine: None) -> None:
    from straightjacket.engine.ai.schemas import get_correction_output_schema
    from straightjacket.engine.engine_loader import eng

    op = get_correction_output_schema()["properties"]["state_ops"]["items"]
    fields = next(branch for branch in op["properties"]["fields"]["anyOf"] if branch.get("type") == "object")
    choices = next(branch for branch in fields["properties"]["status"]["anyOf"] if branch.get("type") == "string")
    assert choices["enum"] == sorted(eng().enums.npc_statuses)
    assert "dead" not in choices["enum"]
