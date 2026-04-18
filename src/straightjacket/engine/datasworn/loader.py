#!/usr/bin/env python3
"""Datasworn JSON loader.

Reads compiled Datasworn JSON files and provides typed access to:
- Oracle tables (d100 rolls with min/max/text rows)
- Assets (paths, companions, deeds, modules, vehicles)
- Moves (player actions with triggers and outcomes)
- Truths (world-building options)
- Faction oracles

The loader is setting-agnostic. Each setting (Classic, Starforged,
Sundered Isles, Delve) produces the same interface. Delve is an
expansion (type: "expansion") that layers on top of Classic.

Character-creation data (backstory prompts, name tables) is not
exposed here — it belongs to SettingPackage, which reads paths
from the settings.yaml and resolves them against this loader.

Mapping from setting-id to JSON filename is driven by each setting's
yaml (`datasworn_id` field), read lazily via
`settings.datasworn_id_of()` to avoid a circular import at module load.

Usage:
    from straightjacket.engine.datasworn.loader import load_setting, list_available

    available = list_available()
    # ['classic', 'delve', 'starforged', 'sundered_isles']

    sf = load_setting("starforged")
    sf.title          # "Ironsworn: Starforged Rulebook"
    sf.oracle_ids()   # all oracle table IDs
    sf.oracle("core/action")  # OracleTable with .roll() method
    sf.assets("path")         # list of asset dicts
    sf.truths()               # list of truth dicts
"""

import json
import random
from dataclasses import dataclass, field

from ..config_loader import PROJECT_ROOT
from ..logging_util import log

_DATA_DIR = PROJECT_ROOT / "data"


def extract_title(obj: dict, fallback: str = "") -> str:
    """Extract display title from a Datasworn object.

    Handles three formats:
      {"title": {"canonical": "...", "standard": "..."}}  — Starforged
      {"title": "string"}                                  — some objects
      {"title": None} or missing                           — Classic assets (use key)

    Datasworn JSON is external third-party data; .get() on it is
    data-shape probing, not domain-config reading.
    """
    title_raw = obj.get("title")
    if isinstance(title_raw, dict):
        return str(title_raw.get("canonical") or title_raw.get("standard") or fallback)
    if isinstance(title_raw, str) and title_raw:
        return title_raw
    obj_id = obj.get("_id", "")
    if obj_id:
        # "classic/assets/path/alchemist" → "Alchemist"
        return obj_id.rsplit("/", 1)[-1].replace("_", " ").title()
    return fallback


def list_available() -> list[str]:
    """Return setting IDs whose settings.yaml declares a Datasworn JSON that exists on disk."""
    # Late import: settings.py imports from loader.py.
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


# ── Oracle tables ─────────────────────────────────────────────


@dataclass
class OracleRow:
    """Single row in an oracle table."""

    min: int
    max: int
    text: str
    # Some rows reference other oracle tables (e.g. "Roll twice")
    oracle_rolls: list | None = None

    def __str__(self) -> str:
        return self.text


@dataclass
class OracleResult:
    """Result of rolling on an oracle table."""

    value: str
    roll: int
    table_path: str
    table_title: str
    row: OracleRow


@dataclass
class OracleTable:
    """A rollable d100 (or dN) oracle table."""

    id: str
    title: str
    rows: list[OracleRow] = field(default_factory=list)
    collection_path: str = ""

    def roll(self) -> OracleResult:
        """Roll on this table and return a structured result with the actual die value."""
        if not self.rows:
            raise ValueError(f"Oracle table '{self.id}' has no rows")
        die_max = self.rows[-1].max
        die_roll = random.randint(1, die_max)
        for row in self.rows:
            if row.min <= die_roll <= row.max:
                return OracleResult(value=row.text, roll=die_roll, table_path=self.id, table_title=self.title, row=row)
        # Unreachable with well-formed Datasworn data: roll is in [1, die_max]
        # and rows cover that range contiguously. A gap means the JSON is malformed.
        raise ValueError(f"Oracle table '{self.id}' rolled {die_roll} but no row covers it — malformed row ranges")

    def roll_text(self) -> str:
        """Roll and return just the text."""
        return self.roll().value

    def __len__(self) -> int:
        return len(self.rows)


class Setting:
    """Loaded Datasworn setting with query methods."""

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

    @property
    def setting_type(self) -> str:
        """'ruleset' for standalone, 'expansion' for add-ons like Delve."""
        return self._raw.get("type", "ruleset")

    @property
    def license(self) -> str:
        return self._raw.get("license", "")

    # ── Oracles ───────────────────────────────────────────────

    def _load_oracles(self) -> None:
        """Parse all oracle tables into OracleTable objects, recursively."""
        for coll_id, coll in self._raw.get("oracles", {}).items():
            self._load_oracle_collection(coll_id, coll)

    def _load_oracle_collection(self, path: str, coll: dict) -> None:
        """Recursively load oracle tables from a collection."""
        for table_id, table_data in (coll.get("contents") or {}).items():
            full_id = f"{path}/{table_id}"
            self._oracles[full_id] = self._parse_oracle_table(full_id, table_data, path)
        for sub_id, sub_coll in (coll.get("collections") or {}).items():
            self._load_oracle_collection(f"{path}/{sub_id}", sub_coll)

    def _parse_oracle_table(self, full_id: str, data: dict, collection_path: str) -> OracleTable:
        """Parse a single oracle table from raw JSON."""
        title = extract_title(data, full_id)
        rows = []
        for r in data.get("rows", []):
            # Two row formats across Datasworn versions:
            #   Classic/Starforged: {"min": 1, "max": 5, "text": "..."}
            #   Sundered Isles:     {"roll": {"min": 1, "max": 5}, "text": "..."}
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
        """Get an oracle table by ID path (e.g. 'core/action')."""
        return self._oracles.get(oracle_id)

    def oracle_ids(self) -> list[str]:
        """List all oracle table IDs."""
        return sorted(self._oracles.keys())

    def oracle_ids_in(self, collection: str) -> list[str]:
        """List oracle IDs within a collection (e.g. 'characters')."""
        prefix = collection + "/"
        return sorted(k for k in self._oracles if k.startswith(prefix))

    def roll_oracle(self, oracle_id: str) -> str:
        """Roll on an oracle table and return the text. Raises KeyError if not found."""
        table = self._oracles.get(oracle_id)
        if table is None:
            raise KeyError(f"Oracle table '{oracle_id}' not found in {self.id}")
        return table.roll_text()

    def oracle_collections(self) -> list[str]:
        """List top-level oracle collection IDs."""
        return sorted(self._raw.get("oracles", {}).keys())

    # ── Assets ────────────────────────────────────────────────

    def asset_categories(self) -> list[str]:
        """List asset category IDs (e.g. 'path', 'companion')."""
        return sorted(self._raw.get("assets", {}).keys())

    def assets(self, category: str) -> list[dict]:
        """Get all assets in a category. Returns raw dicts."""
        cat = self._raw.get("assets", {}).get(category, {})
        return list(cat.get("contents", {}).values())

    def asset(self, category: str, asset_id: str) -> dict | None:
        """Get a specific asset by category and ID."""
        cat = self._raw.get("assets", {}).get(category, {})
        return cat.get("contents", {}).get(asset_id)

    def paths(self) -> list[dict]:
        """Convenience: get all path assets (character creation)."""
        return self.assets("path")

    # ── Moves ─────────────────────────────────────────────────

    def move_categories(self) -> list[str]:
        """List move category IDs."""
        return sorted(self._raw.get("moves", {}).keys())

    def moves(self, category: str) -> list[dict]:
        """Get all moves in a category. Returns raw dicts."""
        cat = self._raw.get("moves", {}).get(category, {})
        return list(cat.get("contents", {}).values())

    # ── Truths ────────────────────────────────────────────────

    def truths(self) -> dict:
        """Get all truths (world-building options). Returns {id: truth_dict}."""
        return dict(self._raw.get("truths", {}))

    # ── Stats and rules ───────────────────────────────────────

    def stats(self) -> dict:
        """Get stat definitions. Returns {stat_id: stat_dict}."""
        return dict(self._raw.get("rules", {}).get("stats", {}))

    def condition_meters(self) -> dict:
        """Get condition meter definitions (health, spirit, supply)."""
        return dict(self._raw.get("rules", {}).get("condition_meters", {}))

    def faction_oracles(self) -> dict[str, OracleTable]:
        """Get faction-related oracle tables."""
        result: dict[str, OracleTable] = {}
        for prefix in ("factions", "faction"):
            for oid in self.oracle_ids_in(prefix):
                table = self._oracles[oid]
                short_id = oid.split("/", 1)[-1]
                result[short_id] = table
        return result

    # ── Raw access ────────────────────────────────────────────

    @property
    def raw(self) -> dict:
        """Access the raw JSON dict (for anything not covered by methods)."""
        return self._raw


_cache: dict[str, Setting] = {}


def load_setting(datasworn_id: str) -> Setting:
    """Load a Datasworn setting by its datasworn_id. Cached after first load.

    Args:
        datasworn_id: the `datasworn_id` value declared in a settings.yaml
                      (e.g. 'classic', 'starforged', 'sundered_isles', 'delve').

    Returns:
        Setting object with query methods.

    Raises:
        FileNotFoundError: if the JSON file is not present (run download_datasworn.py).
    """
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
    """Clear the setting cache. Use after data directory changes."""
    _cache.clear()
