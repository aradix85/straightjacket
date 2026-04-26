import json
import random
from dataclasses import dataclass, field

from ..config_loader import PROJECT_ROOT
from ..logging_util import log

_DATA_DIR = PROJECT_ROOT / "data"


def extract_title(obj: dict, fallback: str = "") -> str:
    title_raw = obj.get("title")
    if isinstance(title_raw, dict):
        return str(title_raw.get("canonical") or title_raw.get("standard") or fallback)
    if isinstance(title_raw, str) and title_raw:
        return title_raw
    obj_id = obj.get("_id", "")
    if obj_id:
        return obj_id.rsplit("/", 1)[-1].replace("_", " ").title()
    return fallback


def list_available() -> list[str]:
    from .settings import datasworn_id_of, list_packages

    result = []
    for setting_id in list_packages():
        try:
            ds_id = datasworn_id_of(setting_id)
        except (FileNotFoundError, KeyError):
            continue
        if (_DATA_DIR / f"{ds_id}.json").exists():
            result.append(setting_id)
    return result


@dataclass
class OracleRow:
    min: int
    max: int
    text: str

    oracle_rolls: list | None = None

    def __str__(self) -> str:
        return self.text


@dataclass
class OracleResult:
    value: str
    roll: int
    table_path: str
    table_title: str
    row: OracleRow


@dataclass
class OracleTable:
    id: str
    title: str
    rows: list[OracleRow] = field(default_factory=list)
    collection_path: str = ""

    def roll(self) -> OracleResult:
        if not self.rows:
            raise ValueError(f"Oracle table '{self.id}' has no rows")
        die_max = self.rows[-1].max
        die_roll = random.randint(1, die_max)
        for row in self.rows:
            if row.min <= die_roll <= row.max:
                return OracleResult(value=row.text, roll=die_roll, table_path=self.id, table_title=self.title, row=row)

        raise ValueError(f"Oracle table '{self.id}' rolled {die_roll} but no row covers it — malformed row ranges")

    def roll_text(self) -> str:
        return self.roll().value

    def __len__(self) -> int:
        return len(self.rows)


class Setting:
    def __init__(self, raw: dict):
        self._raw = raw
        self._oracles: dict[str, OracleTable] = {}
        self._load_oracles()

    @property
    def id(self) -> str:
        return self._raw.get("_id", "")

    @property
    def title(self) -> str:
        return extract_title(self._raw, self.id)

    def _load_oracles(self) -> None:
        for coll_id, coll in self._raw.get("oracles", {}).items():
            self._load_oracle_collection(coll_id, coll)

    def _load_oracle_collection(self, path: str, coll: dict) -> None:
        for table_id, table_data in (coll.get("contents") or {}).items():
            full_id = f"{path}/{table_id}"
            self._oracles[full_id] = self._parse_oracle_table(full_id, table_data, path)
        for sub_id, sub_coll in (coll.get("collections") or {}).items():
            self._load_oracle_collection(f"{path}/{sub_id}", sub_coll)

    def _parse_oracle_table(self, full_id: str, data: dict, collection_path: str) -> OracleTable:
        title = extract_title(data, full_id)
        rows = []
        for r in data.get("rows", []):
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
                    text=r.get("text", ""),
                    oracle_rolls=r.get("oracle_rolls"),
                )
            )
        return OracleTable(id=full_id, title=title, rows=rows, collection_path=collection_path)

    def oracle(self, oracle_id: str) -> OracleTable | None:
        return self._oracles.get(oracle_id)

    def oracle_ids(self) -> list[str]:
        return sorted(self._oracles.keys())

    def roll_oracle(self, oracle_id: str) -> str:
        table = self._oracles.get(oracle_id)
        if table is None:
            raise KeyError(f"Oracle table '{oracle_id}' not found in {self.id}")
        return table.roll_text()

    def asset_categories(self) -> list[str]:
        return sorted(self._raw.get("assets", {}).keys())

    def assets(self, category: str) -> list[dict]:
        cat = self._raw.get("assets", {}).get(category, {})
        return list(cat.get("contents", {}).values())

    def asset(self, category: str, asset_id: str) -> dict | None:
        cat = self._raw.get("assets", {}).get(category, {})
        return cat.get("contents", {}).get(asset_id)

    def paths(self) -> list[dict]:
        return self.assets("path")

    def moves(self, category: str) -> list[dict]:
        cat = self._raw.get("moves", {}).get(category, {})
        return list(cat.get("contents", {}).values())

    def truths(self) -> dict:
        return dict(self._raw.get("truths", {}))

    def stats(self) -> dict:
        return dict(self._raw.get("rules", {}).get("stats", {}))

    @property
    def raw(self) -> dict:
        return self._raw


_cache: dict[str, Setting] = {}


def load_setting(datasworn_id: str) -> Setting:
    if datasworn_id in _cache:
        return _cache[datasworn_id]

    path = _DATA_DIR / f"{datasworn_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Datasworn JSON not found: {path}\nRun: python data/download_datasworn.py")

    log(f"[Datasworn] Loading {datasworn_id} from {path.name}")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    setting = Setting(raw)
    _cache[datasworn_id] = setting

    oracle_count = len(setting.oracle_ids())
    asset_count = sum(len(setting.assets(c)) for c in setting.asset_categories())
    log(
        f"[Datasworn] {datasworn_id}: {oracle_count} oracle tables, {asset_count} assets, {len(setting.truths())} truths"
    )

    return setting


def clear_cache() -> None:
    _cache.clear()
