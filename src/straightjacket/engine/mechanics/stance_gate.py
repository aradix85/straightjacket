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
    """Compute behavioral stance from disposition, bond (connection track), and move category.

    The stance_matrix in engine.yaml must contain every combination of
    disposition × bond_range × category. Missing entries are a yaml error,
    not a runtime fallback. Unknown move_category is normalised to 'other'.
    """
    matrix = eng().stance_matrix
    buckets = eng().stance_bond_buckets

    disposition = npc.disposition
    bond = get_npc_bond(game, npc.id)

    if bond <= buckets.low_max:
        bond_range = "low"
    elif bond <= buckets.mid_max:
        bond_range = "mid"
    else:
        bond_range = "high"

    cat = move_category if move_category in ("combat", "social", "gather_information", "other") else "other"

    entry = matrix[disposition][bond_range][cat]
    return NpcStance(
        npc_id=npc.id,
        npc_name=npc.name,
        stance=entry.stance,
        constraint=entry.constraint,
    )


def compute_npc_gate(game: GameState, npc: NpcData, current_scene: int, stance: str) -> int:
    """Compute information gate level (0-4) for an NPC."""
    _e = eng()
    cfg = _e.information_gate
    p = cfg.points
    b = cfg.buckets

    first_scene = min((m.scene for m in npc.memory), default=current_scene)
    scenes_known = current_scene - first_scene

    points = 0
    if scenes_known >= b.scenes_known_high_min:
        points += p.scenes_known_4_plus
    elif scenes_known >= b.scenes_known_mid_min:
        points += p.scenes_known_2_3
    else:
        points += p.scenes_known_1

    points += npc.gather_count * p.gather_success

    bond = get_npc_bond(game, npc.id)
    if bond >= b.bond_high_min:
        points += p.bond_4_plus
    elif bond >= b.bond_mid_min:
        points += p.bond_2_3
    else:
        points += p.bond_1

    gate = min(cfg.gate_max, max(cfg.gate_min, points))

    # Stance cap
    cap = cfg.stance_caps[stance]
    gate = min(gate, cap)

    return gate
