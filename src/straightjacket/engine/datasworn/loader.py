#!/usr/bin/env python3
"""Datasworn JSON loader.

Reads compiled Datasworn JSON files and provides typed access to:
- Oracle tables (d100 rolls with min/max/text rows)
- Assets (paths, companions, deeds, modules, vehicles)
- Moves (player actions with triggers and outcomes)
- Truths (world-building options)
- Character creation data (backstory prompts, names, background assets)
- Faction oracles

The loader is setting-agnostic. Each setting (Classic, Starforged,
Sundered Isles, Delve) produces the same interface. Delve is an
expansion (type: "expansion") that layers on top of Classic.

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
from pathlib import Path

from ..config_loader import PROJECT_ROOT
from ..logging_util import log

# DATA DIRECTORY

_DATA_DIR = PROJECT_ROOT / "data"

# Map setting IDs to JSON filenames
_SETTING_FILES = {
    "classic": "classic.json",
    "delve": "delve.json",
    "starforged": "starforged.json",
    "sundered_isles": "sundered_isles.json",
}


def data_dir() -> Path:
    """Return the data directory path."""
    return _DATA_DIR


def extract_title(obj: dict, fallback: str = "") -> str:
    """Extract display title from a Datasworn object.

    Handles three formats:
      {"title": {"canonical": "...", "standard": "..."}}  — Starforged
      {"title": "string"}                                  — some objects
      {"title": None} or missing                           — Classic assets (use key)
    """
    title_raw = obj.get("title")
    if isinstance(title_raw, dict):
        return str(title_raw.get("canonical") or title_raw.get("standard") or fallback)
    if isinstance(title_raw, str) and title_raw:
        return title_raw
    # Fallback: derive from _id or use the provided fallback
    obj_id = obj.get("_id", "")
    if obj_id:
        # "classic/assets/path/alchemist" → "Alchemist"
        return obj_id.rsplit("/", 1)[-1].replace("_", " ").title()
    return fallback


def list_available() -> list[str]:
    """Return IDs of settings whose JSON files are present."""
    return [sid for sid, fname in _SETTING_FILES.items() if (_DATA_DIR / fname).exists()]


# ORACLE TABLE


@dataclass
class OracleRow:
    """Single row in an oracle table."""

    min: int
    max: int
    text: str
    # Some rows reference other oracle tables (e.g. "Roll twice")
    oracle_rolls: list | None = None

    def __str__(self):
        return self.text


@dataclass
class OracleTable:
    """A rollable d100 (or dN) oracle table."""

    id: str
    title: str
    rows: list[OracleRow] = field(default_factory=list)
    # Parent collection path for navigation
    collection_path: str = ""

    def roll(self) -> OracleRow:
        """Roll on this table and return the matching row."""
        if not self.rows:
            raise ValueError(f"Oracle table '{self.id}' has no rows")
        # Determine die size from max value of last row
        die_max = self.rows[-1].max
        result = random.randint(1, die_max)
        for row in self.rows:
            if row.min <= result <= row.max:
                return row
        # Fallback: return last row (should not happen with valid data)
        return self.rows[-1]

    def roll_text(self) -> str:
        """Roll and return just the text."""
        return self.roll().text

    def __len__(self):
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

    def _load_oracles(self):
        """Parse all oracle tables into OracleTable objects, recursively."""
        for coll_id, coll in self._raw.get("oracles", {}).items():
            self._load_oracle_collection(coll_id, coll)

    def _load_oracle_collection(self, path: str, coll: dict):
        """Recursively load oracle tables from a collection."""
        # Direct tables in this collection
        for table_id, table_data in (coll.get("contents") or {}).items():
            full_id = f"{path}/{table_id}"
            self._oracles[full_id] = self._parse_oracle_table(full_id, table_data, path)

        # Sub-collections (recursive)
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
        return OracleTable(
            id=full_id,
            title=title,
            rows=rows,
            collection_path=collection_path,
        )

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

    # ── Character creation data ───────────────────────────────

    def backstory_prompts(self) -> OracleTable | None:
        """Get backstory prompts oracle (Starforged: campaign_launch/backstory_prompts)."""
        t = self.oracle("campaign_launch/backstory_prompts")
        if t:
            return t
        # Sundered Isles: character/backstory or getting_underway/*
        t = self.oracle("character/backstory")
        if t:
            return t
        # Classic: not available as a dedicated oracle
        return None

    def name_tables(self) -> dict[str, OracleTable]:
        """Get character name oracle tables. Returns {table_id: OracleTable}."""
        result = {}
        # Starforged: characters/name/given, characters/name/family_name, characters/name/callsign
        for oid in self.oracle_ids_in("characters/name"):
            table = self._oracles[oid]
            # Use the last segment as key
            short_id = oid.rsplit("/", 1)[-1]
            result[short_id] = table
        # Sundered Isles: character/name/*
        if not result:
            for oid in self.oracle_ids_in("character/name"):
                table = self._oracles[oid]
                short_id = oid.rsplit("/", 1)[-1]
                result[short_id] = table
        # Classic: characters/name (if it exists as a sub-collection)
        if not result:
            for oid in self.oracle_ids():
                if "name" in oid and "character" in oid:
                    table = self._oracles[oid]
                    short_id = oid.rsplit("/", 1)[-1]
                    result[short_id] = table
        return result

    def faction_oracles(self) -> dict[str, OracleTable]:
        """Get faction-related oracle tables."""
        result = {}
        for prefix in ("factions", "faction"):
            for oid in self.oracle_ids_in(prefix):
                table = self._oracles[oid]
                short_id = oid.split("/", 1)[-1]  # strip first segment
                result[short_id] = table
        return result

    # ── Raw access ────────────────────────────────────────────

    @property
    def raw(self) -> dict:
        """Access the raw JSON dict (for anything not covered by methods)."""
        return self._raw


_cache: dict[str, Setting] = {}


def load_setting(setting_id: str) -> Setting:
    """Load a Datasworn setting by ID. Cached after first load.

    Args:
        setting_id: One of 'classic', 'delve', 'starforged', 'sundered_isles'.

    Returns:
        Setting object with query methods.

    Raises:
        FileNotFoundError: if the JSON file is not present (run download_datasworn.py).
        KeyError: if the setting_id is not recognized.
    """
    if setting_id in _cache:
        return _cache[setting_id]

    if setting_id not in _SETTING_FILES:
        raise KeyError(f"Unknown setting '{setting_id}'. Available: {list(_SETTING_FILES.keys())}")

    path = _DATA_DIR / _SETTING_FILES[setting_id]
    if not path.exists():
        raise FileNotFoundError(f"Datasworn JSON not found: {path}\nRun: python data/download_datasworn.py")

    log(f"[Datasworn] Loading {setting_id} from {path.name}")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    setting = Setting(raw)
    _cache[setting_id] = setting

    oracle_count = len(setting.oracle_ids())
    asset_count = sum(len(setting.assets(c)) for c in setting.asset_categories())
    log(f"[Datasworn] {setting_id}: {oracle_count} oracle tables, {asset_count} assets, {len(setting.truths())} truths")

    return setting


def clear_cache():
    """Clear the setting cache. Use after data directory changes."""
    _cache.clear()
