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
    matrix = eng().get_raw("stance_matrix")

    disposition = npc.disposition
    bond = get_npc_bond(game, npc.id)

    if bond <= 1:
        bond_range = "low"
    elif bond <= 3:
        bond_range = "mid"
    else:
        bond_range = "high"

    cat = move_category if move_category in ("combat", "social", "gather_information", "other") else "other"

    entry = matrix[disposition][bond_range][cat]
    return NpcStance(
        npc_id=npc.id,
        npc_name=npc.name,
        stance=entry["stance"],
        constraint=entry["constraint"],
    )


def compute_npc_gate(game: GameState, npc: NpcData, current_scene: int, stance: str) -> int:
    """Compute information gate level (0-4) for an NPC."""
    _e = eng()
    cfg = _e.information_gate
    p = cfg.points

    first_scene = min((m.scene for m in npc.memory), default=current_scene)
    scenes_known = current_scene - first_scene

    points = 0
    if scenes_known >= 4:
        points += p.scenes_known_4_plus
    elif scenes_known >= 1:
        points += p.scenes_known_2_3
    else:
        points += p.scenes_known_1

    points += npc.gather_count * p.gather_success

    bond = get_npc_bond(game, npc.id)
    if bond >= 4:
        points += p.bond_4_plus
    elif bond >= 2:
        points += p.bond_2_3
    else:
        points += p.bond_1

    gate = min(4, max(0, points))

    # Stance cap
    cap = cfg.stance_caps.get(stance, cfg.default_cap)
    gate = min(gate, cap)

    return gate
