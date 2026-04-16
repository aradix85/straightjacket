#!/usr/bin/env python3
"""NPC name generation via Datasworn oracle tables.

When a setting provides name oracles (oracle_paths.names), engine rolls
names instead of accepting AI-generated ones. No AI call, no generator
framework. Fallback to AI-provided name when setting has no name oracles.
"""

from __future__ import annotations

import random

from ..datasworn.settings import SettingPackage, active_package
from ..logging_util import log
from ..models import GameState


def roll_oracle_name(game: GameState) -> str:
    """Roll an NPC name from the active setting's name oracles.

    Rules by number of configured name paths:
    - 0 paths: return "" (caller uses AI-provided name)
    - 1 path: single roll
    - 2 paths: join both with a space (given + family)
    - 3+ paths: 50% chance last-only (callsign), else first two joined

    Paths and oracle data may come from a parent setting (e.g. Delve → Classic).
    """
    pkg = active_package(game)
    if pkg is None:
        return ""

    # Walk up parent chain to find the package that owns name oracles
    source_pkg: SettingPackage | None = pkg
    while source_pkg is not None and not source_pkg.oracle_paths.names:
        source_pkg = source_pkg._parent
    if source_pkg is None:
        return ""

    paths = source_pkg.oracle_paths.names
    data = source_pkg.data

    try:
        if len(paths) == 1:
            name = data.roll_oracle(paths[0])
        elif len(paths) == 2:
            name = f"{data.roll_oracle(paths[0])} {data.roll_oracle(paths[1])}"
        else:
            if random.random() < 0.5:
                name = data.roll_oracle(paths[-1])
            else:
                name = f"{data.roll_oracle(paths[0])} {data.roll_oracle(paths[1])}"
    except KeyError as e:
        log(f"[NPC name] Oracle roll failed: {e}", level="warning")
        return ""

    return name.strip()
