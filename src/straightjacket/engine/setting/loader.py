import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from typing_extensions import override

from straightjacket.engine.config_loader import PROJECT_ROOT
from straightjacket.engine.logging_util import log
from straightjacket.engine.serialization import read_key, read_optional_key, shaped

_DATA_DIR = PROJECT_ROOT / "data"
_RULESET_TYPE = "ruleset"


@dataclass(frozen=True)
class OracleRoll:
    auto: bool
    oracle: str | None
    number_of_rolls: int
    duplicates: str


@dataclass
class OracleRow:
    min: int
    max: int
    text: str
    oracle_rolls: list[OracleRoll]

    @override
    def __str__(self) -> str:
        return self.text


@dataclass
class OracleTable:
    id: str
    title: str
    rows: list[OracleRow] = field(default_factory=list)

    def roll(self) -> OracleRow:
        if not self.rows:
            msg = f"Oracle table '{self.id}' has no rows"
            raise ValueError(msg)
        die_roll = random.randint(1, max(row.max for row in self.rows))
        for row in self.rows:
            if row.min <= die_roll <= row.max:
                return row

        msg = f"Oracle table '{self.id}' rolled {die_roll} but no row covers it — malformed row ranges"
        raise ValueError(msg)

    def __len__(self) -> int:
        return len(self.rows)


@dataclass(frozen=True)
class TruthOption:
    summary: str
    description: str


@dataclass(frozen=True)
class Truth:
    name: str
    options: list[TruthOption]


def _parse_oracle_roll(raw: object, where: str) -> OracleRoll:
    return OracleRoll(
        auto=read_key(raw, "auto", bool, where),
        oracle=read_optional_key(raw, "oracle", str, where),
        number_of_rolls=read_key(raw, "number_of_rolls", int, where),
        duplicates=read_key(raw, "duplicates", str, where),
    )


def parse_oracle_table(full_id: str, data: object, table_where: str) -> OracleTable:
    rows: list[OracleRow] = []
    for index, row in enumerate(read_key(data, "rows", list, table_where)):
        where = f"{table_where}.rows[{index}]"
        roll = read_optional_key(row, "roll", dict, where)
        if roll is None:
            continue
        rows.append(
            OracleRow(
                min=read_key(roll, "min", int, where),
                max=read_key(roll, "max", int, where),
                text=read_key(row, "text", str, where),
                oracle_rolls=[
                    _parse_oracle_roll(found, f"{where}.oracle_rolls[{at}]")
                    for at, found in enumerate(read_optional_key(row, "oracle_rolls", list, where) or [])
                ],
            )
        )
    return OracleTable(id=full_id, title=read_key(data, "name", str, table_where), rows=rows)


def _parse_truth(raw: object, where: str) -> Truth:
    options: list[TruthOption] = []
    for index, option in enumerate(read_key(raw, "options", list, where)):
        description = read_key(option, "description", str, f"{where}.options[{index}]")
        summary = read_optional_key(option, "summary", str, f"{where}.options[{index}]") or description
        options.append(TruthOption(summary=summary, description=description))
    return Truth(name=read_key(raw, "name", str, where), options=options)


class Setting:
    def __init__(self, raw: object, datasworn_id: str) -> None:
        ruleset_key = "_id" if read_key(raw, "type", str, datasworn_id) == _RULESET_TYPE else "ruleset"
        self.ruleset_id = read_key(raw, ruleset_key, str, datasworn_id)
        self._truths = {
            truth_id: _parse_truth(truth, f"{datasworn_id}.truths.{truth_id}")
            for truth_id, truth in read_key(raw, "truths", dict, datasworn_id).items()
        }
        self._oracles: dict[str, OracleTable] = {}
        for coll_id, coll in read_key(raw, "oracles", dict, datasworn_id).items():
            self._load_oracle_collection(coll_id, coll, f"{datasworn_id}.oracles")

    def _load_oracle_collection(self, path: str, coll: object, file_where: str) -> None:
        where = f"{file_where}.{path}"
        for table_id, table_data in (read_optional_key(coll, "contents", dict, where) or {}).items():
            full_id = f"{path}/{table_id}"
            self._oracles[full_id] = parse_oracle_table(full_id, table_data, f"{file_where}.{full_id}")
        for sub_id, sub_coll in (read_optional_key(coll, "collections", dict, where) or {}).items():
            self._load_oracle_collection(f"{path}/{sub_id}", sub_coll, file_where)

    def oracle(self, oracle_id: str) -> OracleTable | None:
        return self._oracles.get(oracle_id)

    def oracle_ids(self) -> list[str]:
        return sorted(self._oracles.keys())

    def truths(self) -> dict[str, Truth]:
        return dict(self._truths)


_files: dict[str, dict[str, object]] = {}
_cache: dict[str, Setting] = {}


def read_datasworn(datasworn_id: str) -> dict[str, object]:
    if datasworn_id in _files:
        return _files[datasworn_id]
    path = _DATA_DIR / f"{datasworn_id}.json"
    if not path.exists():
        msg = f"Datasworn JSON not found: {path}\nRun: python data/data.py"
        raise FileNotFoundError(msg)
    log(f"[Datasworn] Loading {datasworn_id} from {path.name}")
    with Path(path).open(encoding="utf-8") as f:
        raw: dict[str, object] = shaped(json.load(f), dict, f"{path.name}: expected dict")
    _files[datasworn_id] = raw
    return raw


def load_setting(datasworn_id: str) -> Setting:
    if datasworn_id in _cache:
        return _cache[datasworn_id]
    setting = Setting(read_datasworn(datasworn_id), datasworn_id)
    _cache[datasworn_id] = setting
    log(f"[Setting] {datasworn_id}: {len(setting.oracle_ids())} oracle tables, {len(setting.truths())} truths")
    return setting
