from __future__ import annotations

import dataclasses
import types
from typing import TYPE_CHECKING, Self, TypeVar, Union, get_args, get_origin, get_type_hints

if TYPE_CHECKING:
    from collections.abc import Callable

    from _typeshed import DataclassInstance
    from typing_extensions import TypeIs

_D = TypeVar("_D", bound="DataclassInstance")
_S = TypeVar("_S")

_SCALARS: dict[object, tuple[type, ...]] = {str: (str,), bool: (bool,), int: (int,), float: (int, float)}
_SEQUENCES = (list, frozenset)


def serialize(obj: DataclassInstance) -> dict[str, object]:
    return {f.name: _serialize_value(getattr(obj, f.name)) for f in dataclasses.fields(obj)}


def _serialize_value(val: object) -> object:
    if dataclasses.is_dataclass(val) and not isinstance(val, type):
        return serialize(val)
    if isinstance(val, list):
        return [_serialize_value(item) for item in val]
    if isinstance(val, dict):
        return {key: _serialize_value(item) for key, item in val.items()}
    return val


def shaped(val: object, shape: type[_S], requirement: str) -> _S:
    if isinstance(val, shape):
        return val
    msg = f"{requirement}, got {type(val).__name__}"
    raise ValueError(msg)


def build_strict(cls: type[_D], data: object, where: str, **parsers: Callable[[object, str], object]) -> _D:
    values = shaped(data, dict, f"{where}: expected dict")
    names = {f.name for f in dataclasses.fields(cls)}
    if unknown := set(values) - names:
        msg = f"{where}: unknown keys {sorted(unknown)}"
        raise ValueError(msg)
    if missing := names - set(values):
        msg = f"{where}: missing keys {sorted(missing)}"
        raise ValueError(msg)
    hints = get_type_hints(cls)
    return cls(
        **{
            key: parsers[key](value, f"{where}.{key}") if key in parsers else _bind(hints[key], value, f"{where}.{key}")
            for key, value in values.items()
        }
    )


def _is_dataclass_type(tp: object) -> TypeIs[type[DataclassInstance]]:
    return isinstance(tp, type) and dataclasses.is_dataclass(tp)


def _without_none(hint: object) -> tuple[object, bool]:
    if get_origin(hint) is Union or isinstance(hint, types.UnionType):
        members = [member for member in get_args(hint) if member is not types.NoneType]
        return (members[0] if len(members) == 1 else hint), len(members) < len(get_args(hint))
    return hint, False


def _bind(hint: object, value: object, where: str) -> object:
    inner, optional = _without_none(hint)
    if inner is object or (value is None and optional):
        return value
    if _is_dataclass_type(inner):
        return build_strict(inner, value, where)
    origin = get_origin(inner)
    if origin in _SEQUENCES:
        (item_hint,) = get_args(inner)
        items = shaped(value, list, f"{where}: expected list")
        return origin(_bind(item_hint, item, f"{where}[{i}]") for i, item in enumerate(items))
    if origin is dict:
        key_hint, value_hint = get_args(inner)
        return {
            _bind(key_hint, key, f"{where} key"): _bind(value_hint, item, f"{where}.{key}")
            for key, item in shaped(value, dict, f"{where}: expected dict").items()
        }
    return _scalar(inner, value, where)


def _scalar(hint: object, value: object, where: str) -> object:
    if hint in _SCALARS and isinstance(value, _SCALARS[hint]) and isinstance(value, bool) == (hint is bool):
        return value
    msg = f"{where}: expected {hint}, got {value!r}"
    raise ValueError(msg)


@dataclasses.dataclass
class SerializableMixin:
    def to_dict(self) -> dict[str, object]:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: object) -> Self:
        return build_strict(cls, data, cls.__name__)
