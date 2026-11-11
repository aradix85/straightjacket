from __future__ import annotations

import dataclasses
import types
from typing import TYPE_CHECKING, Any, Self, TypeVar, Union, get_args, get_origin, get_type_hints

if TYPE_CHECKING:
    from _typeshed import DataclassInstance
    from typing_extensions import TypeIs

_T = TypeVar("_T")
_S = TypeVar("_S")


def is_dataclass_type(tp: object) -> TypeIs[type[DataclassInstance]]:
    return isinstance(tp, type) and dataclasses.is_dataclass(tp)


def _resolve_item_type(tp: Any) -> type | None:
    origin = get_origin(tp)
    if origin is list and is_dataclass_type(item := get_args(tp)[0]):
        return item
    return None


def _allows_none(tp: Any) -> bool:
    if get_origin(tp) is Union or isinstance(tp, types.UnionType):
        return types.NoneType in get_args(tp)
    return False


def unwrap_optional(tp: Any) -> tuple[Any, bool]:
    origin = get_origin(tp)
    if origin is Union or isinstance(tp, types.UnionType):
        args = get_args(tp)
        non_none = [a for a in args if a is not types.NoneType]
        if len(non_none) == 1 and types.NoneType in args:
            return non_none[0], True
    return tp, False


def serialize(obj: Any) -> dict[str, Any]:
    if not dataclasses.is_dataclass(obj):
        msg = f"Expected dataclass instance, got {type(obj).__name__}"
        raise TypeError(msg)
    result = {}
    for f in dataclasses.fields(obj):
        val = getattr(obj, f.name)
        result[f.name] = _serialize_value(val)
    return result


def _serialize_value(val: Any) -> Any:
    if val is None:
        return None
    if dataclasses.is_dataclass(val) and not isinstance(val, type):
        return serialize(val)
    if isinstance(val, list):
        return [_serialize_value(item) for item in val]
    if isinstance(val, dict):
        return {k: _serialize_value(v) for k, v in val.items()}
    return val


def deserialize(cls: type[_T], data: object) -> _T:
    if not is_dataclass_type(cls):
        msg = f"Expected dataclass type, got {cls}"
        raise TypeError(msg)
    if not isinstance(data, dict):
        msg = f"Expected dict, got {type(data).__name__}"
        raise TypeError(msg)

    hints = get_type_hints(cls)
    field_names = {f.name for f in dataclasses.fields(cls)}
    unknown = sorted(set(data) - field_names)
    if unknown:
        msg = f"{cls.__name__}: unknown fields {unknown}"
        raise ValueError(msg)
    missing = sorted(field_names - set(data))
    if missing:
        msg = f"{cls.__name__}: missing fields {missing}"
        raise ValueError(msg)

    return cls(**{key: _deserialize_value(hints[key], val) for key, val in data.items()})


def _deserialize_value(hint: Any, val: Any) -> Any:
    if val is None:
        if _allows_none(hint):
            return None
        msg = f"null where {hint} is required"
        raise ValueError(msg)

    inner, is_optional = unwrap_optional(hint)
    if is_optional:
        return _deserialize_value(inner, val)
    if is_dataclass_type(inner):
        return deserialize(inner, shaped(val, dict, f"{inner.__name__} needs an object"))
    origin = get_origin(inner)
    if origin is list:
        return _deserialize_list(inner, shaped(val, list, f"{inner} needs a list"))
    if origin is dict:
        return _deserialize_dict(inner, shaped(val, dict, f"{inner} needs an object"))
    return dict(val) if isinstance(val, dict) else val


def shaped(val: object, shape: type[_S], requirement: str) -> _S:
    if isinstance(val, shape):
        return val
    msg = f"{requirement}, got {type(val).__name__}"
    raise ValueError(msg)


def _deserialize_list(hint: Any, val: list[Any]) -> list[Any]:
    item_type = _resolve_item_type(hint)
    if item_type is None:
        return list(val)
    if not all(isinstance(item, dict) for item in val):
        msg = f"a list of {item_type.__name__} holds an entry that is not an object"
        raise ValueError(msg)
    return [deserialize(item_type, item) for item in val]


def _deserialize_dict(hint: Any, val: dict[Any, Any]) -> dict[Any, Any]:
    if is_dataclass_type(value_type := get_args(hint)[1]):
        return {key: deserialize(value_type, item) for key, item in val.items()}
    return dict(val)


class SerializableMixin:
    def to_dict(self) -> dict[str, Any]:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return deserialize(cls, data)
