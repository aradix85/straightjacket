import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config_loader import PROJECT_ROOT
from ..logging_util import log

_DATA_DIR = PROJECT_ROOT / "data"


@dataclass
class OracleRow:
    min: int
    max: int
    text: str

    oracle_rolls: list[Any] | None = None

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
        die_max = self.rows[-1].max
        die_roll = random.randint(1, die_max)
        for row in self.rows:
            if row.min <= die_roll <= row.max:
                return row

        raise ValueError(f"Oracle table '{self.id}' rolled {die_roll} but no row covers it — malformed row ranges")

    def __len__(self) -> int:
        return len(self.rows)


def parse_oracle_table(full_id: str, data: dict[str, Any]) -> OracleTable:
    rows = []
    for r in data["rows"]:
        roll_obj = r.get("roll")
        if isinstance(roll_obj, dict):
            row_min = roll_obj.get("min", 0)
            row_max = roll_obj.get("max", 0)
        else:
            row_min = r.get("min", 0)
            row_max = r.get("max", 0)
        rows.append(
            OracleRow(
                min=row_min,
                max=row_max,
                text=r["text"],
                oracle_rolls=r.get("oracle_rolls"),
            )
        )
    return OracleTable(id=full_id, title=data["name"], rows=rows)


class Setting:
    def __init__(self, raw: dict[str, Any]):
        self._raw = raw
        self._oracles: dict[str, OracleTable] = {}
        self._load_oracles()

    def _load_oracles(self) -> None:
        for coll_id, coll in self._raw["oracles"].items():
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

    def asset_categories(self) -> list[str]:
        return sorted(self._raw["assets"].keys())

    def assets(self, category: str) -> list[dict[str, Any]]:
        return list(self._raw["assets"][category]["contents"].values())

    def asset(self, category: str, asset_id: str) -> dict[str, Any] | None:
        result: dict[str, Any] | None = self._raw["assets"][category]["contents"].get(asset_id)
        return result

    def paths(self) -> list[dict[str, Any]]:
        return self.assets("path")

    def truths(self) -> dict[str, Any]:
        return dict(self._raw["truths"])

    def stats(self) -> dict[str, Any]:
        return dict(self._raw["rules"].get("stats", {}))

    @property
    def raw(self) -> dict[str, Any]:
        return self._raw


_cache: dict[str, Setting] = {}


def load_setting(datasworn_id: str) -> Setting:
    if datasworn_id in _cache:
        return _cache[datasworn_id]

    path = _DATA_DIR / f"{datasworn_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Datasworn JSON not found: {path}\nRun: python data/download_datasworn.py")

    log(f"[Datasworn] Loading {datasworn_id} from {path.name}")
    with Path(path).open(encoding="utf-8") as f:
        raw = json.load(f)

    setting = Setting(raw)
    _cache[datasworn_id] = setting

    oracle_count = len(setting.oracle_ids())
    asset_count = sum(len(setting.assets(c)) for c in setting.asset_categories())
    log(
        f"[Datasworn] {datasworn_id}: {oracle_count} oracle tables, {asset_count} assets, {len(setting.truths())} truths"
    )

    return setting
