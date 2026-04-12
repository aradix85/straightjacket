#!/usr/bin/env python3
"""NPC stance resolution and information gating."""

from __future__ import annotations

from dataclasses import dataclass

from ..engine_loader import eng
from ..models import GameState, NpcData
from ..npc import get_npc_bond


@dataclass
class NpcStance:
    """Computed stance for one NPC in a specific scene context."""

    npc_id: str
    npc_name: str
    stance: str
    constraint: str


def resolve_npc_stance(game: GameState, npc: NpcData, move_category: str) -> NpcStance:
    """Compute behavioral stance from disposition, bond (connection track), and move category."""
    _e = eng()
    matrix = _e.get_raw("stance_matrix", {})

    disposition = npc.disposition
    bond = get_npc_bond(game, npc.id)

    if bond <= 1:
        bond_range = "low"
    elif bond <= 3:
        bond_range = "mid"
    else:
        bond_range = "high"

    # Normalize move_category for matrix lookup
    cat = move_category
    if cat not in ("combat", "social", "gather_information", "other"):
        cat = "other"

    # Three-level lookup: disposition → bond_range → move_category
    disp_node = matrix.get(disposition, matrix.get("neutral", {}))
    bond_node = disp_node.get(bond_range, disp_node.get("low", {}))
    entry = bond_node.get(cat, bond_node.get("other", {}))

    stance = entry.get("stance", "neutral") if isinstance(entry, dict) else "neutral"
    constraint = entry.get("constraint", "") if isinstance(entry, dict) else ""

    return NpcStance(
        npc_id=npc.id,
        npc_name=npc.name,
        stance=stance,
        constraint=constraint,
    )


def compute_npc_gate(game: GameState, npc: NpcData, current_scene: int, stance: str) -> int:
    """Compute information gate level (0-4) for an NPC."""
    _e = eng()
    gate_cfg = _e.get_raw("information_gate", {})
    points_cfg = gate_cfg.get("points", {})

    first_scene = min((m.scene for m in npc.memory), default=current_scene)
    scenes_known = current_scene - first_scene

    points = 0
    if scenes_known >= 4:
        points += points_cfg.get("scenes_known_4_plus", 2)
    elif scenes_known >= 1:
        points += points_cfg.get("scenes_known_2_3", 1)
    else:
        points += points_cfg.get("scenes_known_1", 0)

    points += npc.gather_count * points_cfg.get("gather_success", 1)

    bond = get_npc_bond(game, npc.id)
    if bond >= 4:
        points += points_cfg.get("bond_4_plus", 2)
    elif bond >= 2:
        points += points_cfg.get("bond_2_3", 1)
    else:
        points += points_cfg.get("bond_1", 0)

    gate = min(4, max(0, points))

    # Stance cap
    caps = gate_cfg.get("stance_caps", {})
    default_cap = gate_cfg.get("default_cap", 4)
    cap = caps.get(stance, default_cap)
    if isinstance(cap, int):
        gate = min(gate, cap)

    return gate
