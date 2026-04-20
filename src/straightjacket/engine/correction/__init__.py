"""Correction subsystem — public API.

Processes ## correction requests: analyse intent (analysis), patch game
state atomically (ops), or restore snapshot and re-narrate (orchestrator).

Consumers import these names from `straightjacket.engine.correction`; the
three-file split is internal layout.
"""

from .analysis import call_correction_brain
from .ops import _apply_correction_ops
from .orchestrator import process_correction

__all__ = ["call_correction_brain", "_apply_correction_ops", "process_correction"]
