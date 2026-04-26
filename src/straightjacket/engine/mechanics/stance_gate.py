from __future__ import annotations

from dataclasses import dataclass

from ..engine_loader import eng
from ..models import GameState, NpcData
from ..npc import get_npc_bond


@dataclass
class NpcStance:
    npc_id: str
    npc_name: str
    stance: str
    constraint: str


def resolve_npc_stance(game: GameState, npc: NpcData, move_category: str) -> NpcStance:
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

    entry = matrix[disposition][bond_range][move_category]
    return NpcStance(
        npc_id=npc.id,
        npc_name=npc.name,
        stance=entry.stance,
        constraint=entry.constraint,
    )


def compute_npc_gate(game: GameState, npc: NpcData, current_scene: int, stance: str) -> int:
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

    cap = cfg.stance_caps[stance]
    gate = min(gate, cap)

    return gate
