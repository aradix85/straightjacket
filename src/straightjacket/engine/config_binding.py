from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING, Any, TypeVar, get_args, get_origin, get_type_hints

from straightjacket.engine.serialization import is_dataclass_type, shaped, unwrap_optional

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

_D = TypeVar("_D", bound="DataclassInstance")

_RAW_FIELD = "_raw"
_SCALARS: dict[object, tuple[type, ...]] = {str: (str,), bool: (bool,), int: (int,), float: (int, float)}
_SEQUENCES = (list, frozenset)


@dataclass
class RawSections:
    _raw: dict[str, Any] = field(repr=False)

    def get_raw(self, key: str) -> Any:
        return self._raw[key]


def bind_sections(cls: type[_D], data: dict[str, object], **prepared: object) -> _D:
    hints = get_type_hints(cls)
    names = [f.name for f in fields(cls) if f.name != _RAW_FIELD and f.name not in prepared]
    sections = {name: _bind(hints[name], data[name], name) for name in names}
    return cls(**sections, **prepared, **{_RAW_FIELD: data})


def build_strict(cls: type[_D], data: object) -> _D:
    return _build(cls, data, cls.__name__)


def _build(cls: type[_D], data: object, where: str) -> _D:
    values = shaped(data, dict, f"{where}: expected dict")
    names = {f.name for f in fields(cls)}
    if unknown := set(values) - names:
        msg = f"Unknown keys for {cls.__name__}: {sorted(unknown)}"
        raise ValueError(msg)
    if missing := names - set(values):
        msg = f"{where}: missing keys {sorted(missing)}"
        raise ValueError(msg)
    hints = get_type_hints(cls)
    return cls(**{key: _bind(hints[key], value, f"{where}.{key}") for key, value in values.items()})


def _bind(hint: object, value: object, where: str) -> object:
    inner, optional = unwrap_optional(hint)
    if value is None and optional:
        return None
    if is_dataclass_type(inner):
        return _build(inner, value, where)
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
