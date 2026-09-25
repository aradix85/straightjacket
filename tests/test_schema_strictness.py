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
    _loose_objects(get_brain_output_schema(["adventure/face_danger"]), "brain", problems)
    assert problems == []
