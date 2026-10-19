import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config_loader import PROJECT_ROOT
from ..logging_util import log

_DATA_DIR = PROJECT_ROOT / "data"
_RULESET_TYPE = "ruleset"


@dataclass
class OracleRow:
    min: int
    max: int
    text: str
    oracle_rolls: list[Any] | None

    def __str__(self) -> str:
        return self.text


@dataclass
class OracleTable:
    id: str
    title: str
    rows: list[OracleRow] = field(default_factory=list)

    def roll(self) -> OracleRow:
        if not self.rows:
            raise ValueError(f"Oracle table '{self.id}' has no rows")
        die_roll = random.randint(1, max(row.max for row in self.rows))
        for row in self.rows:
            if row.min <= die_roll <= row.max:
                return row

        raise ValueError(f"Oracle table '{self.id}' rolled {die_roll} but no row covers it — malformed row ranges")

    def __len__(self) -> int:
        return len(self.rows)


def parse_oracle_table(full_id: str, data: dict[str, Any]) -> OracleTable:
    rows = [
        OracleRow(min=r["roll"]["min"], max=r["roll"]["max"], text=r["text"], oracle_rolls=r.get("oracle_rolls"))
        for r in data["rows"]
        if r["roll"] is not None
    ]
    return OracleTable(id=full_id, title=data["name"], rows=rows)


class Setting:
    def __init__(self, raw: dict[str, Any]):
        self.ruleset_id: str = raw["_id"] if raw["type"] == _RULESET_TYPE else raw["ruleset"]
        self._truths: dict[str, Any] = raw["truths"]
        self._oracles: dict[str, OracleTable] = {}
        for coll_id, coll in raw["oracles"].items():
            self._load_oracle_collection(coll_id, coll)

    def _load_oracle_collection(self, path: str, coll: dict[str, Any]) -> None:
        for table_id, table_data in (coll.get("contents") or {}).items():
            full_id = f"{path}/{table_id}"
            self._oracles[full_id] = parse_oracle_table(full_id, table_data)
        for sub_id, sub_coll in (coll.get("collections") or {}).items():
            self._load_oracle_collection(f"{path}/{sub_id}", sub_coll)

    def oracle(self, oracle_id: str) -> OracleTable | None:
        return self._oracles.get(oracle_id)

    def oracle_ids(self) -> list[str]:
        return sorted(self._oracles.keys())

    def truths(self) -> dict[str, Any]:
        return dict(self._truths)


_files: dict[str, dict[str, Any]] = {}
_cache: dict[str, Setting] = {}


def read_datasworn(datasworn_id: str) -> dict[str, Any]:
    if datasworn_id in _files:
        return _files[datasworn_id]
    path = _DATA_DIR / f"{datasworn_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Datasworn JSON not found: {path}\nRun: python data/data.py")
    log(f"[Datasworn] Loading {datasworn_id} from {path.name}")
    with Path(path).open(encoding="utf-8") as f:
        raw: dict[str, Any] = json.load(f)
    _files[datasworn_id] = raw
    return raw


def load_setting(datasworn_id: str) -> Setting:
    if datasworn_id in _cache:
        return _cache[datasworn_id]
    setting = Setting(read_datasworn(datasworn_id))
    _cache[datasworn_id] = setting
    log(f"[Setting] {datasworn_id}: {len(setting.oracle_ids())} oracle tables, {len(setting.truths())} truths")
    return setting
