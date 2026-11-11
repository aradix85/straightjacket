from __future__ import annotations

from dataclasses import fields
from typing import TYPE_CHECKING, TypeVar, get_args, get_origin, get_type_hints

from straightjacket.engine.serialization import allows_none, is_dataclass_type, shaped, unwrap_optional

if TYPE_CHECKING:
    from collections.abc import Callable

    from _typeshed import DataclassInstance

_D = TypeVar("_D", bound="DataclassInstance")

_SCALARS: dict[object, tuple[type, ...]] = {str: (str,), bool: (bool,), int: (int,), float: (int, float)}
_SEQUENCES = (list, frozenset)


def build_strict(cls: type[_D], data: object, where: str, **parsers: Callable[[object, str], object]) -> _D:
    values = shaped(data, dict, f"{where}: expected dict")
    names = {f.name for f in fields(cls)}
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


def _bind(hint: object, value: object, where: str) -> object:
    if hint is object or (value is None and allows_none(hint)):
        return value
    inner, _ = unwrap_optional(hint)
    if is_dataclass_type(inner):
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
