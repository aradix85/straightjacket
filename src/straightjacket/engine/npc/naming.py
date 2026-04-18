#!/usr/bin/env python3
"""NPC name generation via Datasworn oracle tables.

When a setting provides name oracles (oracle_paths.names), engine rolls
names instead of accepting AI-generated ones. No AI call, no generator
framework. Fallback to AI-provided name when setting has no name oracles.
"""

from __future__ import annotations

import random

from ..datasworn.settings import active_package
from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState


def roll_oracle_name(game: GameState) -> str:
    """Roll an NPC name from the active setting's name oracles.

    Rules by number of configured name paths:
    - 0 paths: return "" (caller uses AI-provided name)
    - 1 path: single roll
    - 2 paths: join both with a space (given + family)
    - 3+ paths: 50% chance last-only (callsign), else first two joined

    `oracle_paths.names` is already parent-chain resolved by SettingPackage.
    Oracle data may live in a parent setting's Datasworn JSON; the package
    walks its chain when resolving a path.
    """
    pkg = active_package(game)
    if pkg is None:
        return ""

    paths = pkg.oracle_paths.names
    if not paths:
        return ""

    def roll(path: str) -> str:
        data = pkg.oracle_data_for(path)
        if data is None:
            raise KeyError(f"Oracle '{path}' not found in setting chain for {pkg.id}")
        return data.roll_oracle(path)

    try:
        if len(paths) == 1:
            name = roll(paths[0])
        elif len(paths) == 2:
            name = f"{roll(paths[0])} {roll(paths[1])}"
        else:
            if random.random() < eng().naming.callsign_probability:
                name = roll(paths[-1])
            else:
                name = f"{roll(paths[0])} {roll(paths[1])}"
    except KeyError as e:
        log(f"[NPC name] Oracle roll failed: {e}", level="warning")
        return ""

    return name.strip()
