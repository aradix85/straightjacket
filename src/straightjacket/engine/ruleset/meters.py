from __future__ import annotations

from ..models import Resources
from .config import rules


def starting_resources() -> Resources:
    return Resources(
        health=rules().resources.health_start,
        spirit=rules().resources.spirit_start,
        supply=rules().resources.supply_start,
        momentum=rules().momentum.start,
        max_momentum=rules().momentum.max,
    )
