from __future__ import annotations

import dataclasses
from typing import Any


class RawSections:
    _raw: dict[str, Any]

    def get_raw(self, key: str) -> Any:
        return self._raw[key]


def reject_unknown(cls: type, data: dict[str, Any]) -> dict[str, Any]:
    known = {f.name for f in dataclasses.fields(cls)}
    unknown = set(data.keys()) - known
    if unknown:
        raise ValueError(f"Unknown keys for {cls.__name__}: {sorted(unknown)}")
    return data


def build_strict(cls: type, data: dict[str, Any]) -> Any:
    return cls(**reject_unknown(cls, data))
