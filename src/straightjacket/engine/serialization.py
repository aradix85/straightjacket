"""Generic dataclass serialization using type annotations.

Replaces per-class to_dict/from_dict boilerplate. Handles nested dataclasses,
lists of dataclasses, and optional fields automatically.

Usage:
    @dataclass
    class Clock(SerializableMixin):
        name: str = ""
        filled: int = 0

    clock.to_dict()          # → {"name": "...", "filled": 0}
    Clock.from_dict(data)    # → Clock(name="...", filled=0)

Classes that need custom serialization (e.g. MemoryEntry strips _score_debug)
override to_dict and call serialize() directly.
"""

from __future__ import annotations

import dataclasses
import types
from typing import Any, Union, get_args, get_origin, get_type_hints


def _is_dataclass_type(tp: Any) -> bool:
    """Check if tp is a dataclass class (not instance)."""
    return isinstance(tp, type) and dataclasses.is_dataclass(tp)


def _resolve_item_type(tp: Any) -> type | None:
    """For list[X], return X if X is a dataclass. Else None."""
    origin = get_origin(tp)
    if origin is list:
        args = get_args(tp)
        if args and _is_dataclass_type(args[0]):
            return args[0]
    return None


def _unwrap_optional(tp: Any) -> tuple[type | None, bool]:
    """Unwrap Optional[X] / X | None → (X, True). Non-optional → (tp, False)."""
    origin = get_origin(tp)
    if origin is Union or isinstance(tp, types.UnionType):
        args = get_args(tp)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1 and type(None) in args:
            return non_none[0], True
    return tp, False


def serialize(obj: Any) -> dict:
    """Serialize a dataclass to a dict, recursing into nested dataclasses."""
    if not dataclasses.is_dataclass(obj):
        raise TypeError(f"Expected dataclass instance, got {type(obj).__name__}")
    result = {}
    for f in dataclasses.fields(obj):
        val = getattr(obj, f.name)
        result[f.name] = _serialize_value(val)
    return result


def _serialize_value(val: Any) -> Any:
    """Serialize a single value, recursing into dataclasses and lists."""
    if val is None:
        return None
    if dataclasses.is_dataclass(val) and not isinstance(val, type):
        return serialize(val)
    if isinstance(val, list):
        return [_serialize_value(item) for item in val]
    if isinstance(val, dict):
        return {k: _serialize_value(v) for k, v in val.items()}
    return val


def deserialize(cls: type, data: dict) -> Any:
    """Deserialize a dict into a dataclass, recursing into nested types."""
    if not _is_dataclass_type(cls):
        raise TypeError(f"Expected dataclass type, got {cls}")
    if not isinstance(data, dict):
        raise TypeError(f"Expected dict, got {type(data).__name__}")

    hints = get_type_hints(cls)
    known_fields = {f.name for f in dataclasses.fields(cls)}
    kwargs: dict[str, Any] = {}

    for key, val in data.items():
        if key not in known_fields:
            continue
        hint = hints.get(key)
        if hint is not None:
            kwargs[key] = _deserialize_value(hint, val)
        else:
            kwargs[key] = val

    return cls(**kwargs)


def _deserialize_value(hint: Any, val: Any) -> Any:
    """Deserialize a single value based on its type hint."""
    if val is None:
        return None

    # Unwrap Optional[X]
    inner, is_optional = _unwrap_optional(hint)
    if is_optional and inner is not None:
        return _deserialize_value(inner, val)

    # Direct dataclass
    if _is_dataclass_type(inner):
        if isinstance(val, dict):
            return deserialize(inner, val)  # type: ignore[arg-type]
        return val  # Already deserialized

    # list[Dataclass]
    item_type = _resolve_item_type(inner)
    if item_type is not None and isinstance(val, list):
        return [deserialize(item_type, item) if isinstance(item, dict) else item for item in val]

    # list[non-dataclass] — preserve as-is but copy
    if get_origin(inner) is list and isinstance(val, list):
        return list(val)

    # dict — preserve as-is but copy
    if isinstance(val, dict):
        return dict(val)

    return val


class SerializableMixin:
    """Mixin that adds to_dict/from_dict to any dataclass via serialize/deserialize."""

    def to_dict(self) -> dict:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> Any:
        return deserialize(cls, data)
