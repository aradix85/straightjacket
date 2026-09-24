from __future__ import annotations

from pathlib import Path

import yaml

from straightjacket.engine.ai.metadata import apply_narrator_metadata
from straightjacket.engine.director import _process_npc_reflection
from straightjacket.engine.engine_loader import eng
from straightjacket.engine.models import GameState, NpcData, Resources
from tests._helpers import make_game_state, make_npc, make_npc_reflection

REPO_ROOT = Path(__file__).resolve().parent.parent


def _game_with(npc: NpcData) -> GameState:
    game = make_game_state()
    game.npcs = [npc]
    return game


def _profiled_npc(status: str, needs_reflection: bool) -> NpcData:
    npc = make_npc(id="npc_1", name="Mira", status=status, agenda="Keep the archive sealed", instinct="Strikes first")
    npc.needs_reflection = needs_reflection
    return npc


def test_compel_strong_hit_does_not_mark_bond() -> None:
    raw = (REPO_ROOT / "engine" / "move_outcomes.yaml").read_text(encoding="utf-8")
    outcomes = yaml.safe_load(raw)["move_outcomes"]
    for key in ("adventure/compel", "relationship/compel"):
        assert not [effect for effect in outcomes[key]["strong_hit"] if effect.startswith("bond")], key


def test_momentum_reset_follows_impacts_and_stops_at_reset_floor(load_engine: None) -> None:
    cfg = eng().momentum
    resources = Resources.from_config()
    for max_momentum, expected in {10: 2, 9: 1, 8: 0, 7: 0, 6: 0}.items():
        resources.max_momentum = max_momentum
        resources.momentum = 5
        resources.reset_momentum(reset_floor=cfg.reset_floor, reset_value=cfg.start, max_cap=cfg.max)
        assert resources.momentum == expected, max_momentum


def test_reflection_for_deceased_npc_is_rejected(load_engine: None) -> None:
    npc = _profiled_npc("deceased", needs_reflection=True)
    game = _game_with(npc)
    before = len(npc.memory)
    assert _process_npc_reflection(game, make_npc_reflection(npc_id="npc_1"), set()) is None
    assert len(npc.memory) == before


def test_reflection_for_npc_the_engine_did_not_select_is_rejected(load_engine: None) -> None:
    npc = _profiled_npc("active", needs_reflection=False)
    game = _game_with(npc)
    before = len(npc.memory)
    assert _process_npc_reflection(game, make_npc_reflection(npc_id="npc_1"), set()) is None
    assert len(npc.memory) == before


def test_duplicate_reflection_in_one_response_is_applied_once(load_engine: None) -> None:
    npc = _profiled_npc("active", needs_reflection=True)
    game = _game_with(npc)
    done: set[str] = set()
    first = _process_npc_reflection(game, make_npc_reflection(npc_id="npc_1"), done)
    assert first == "npc_1"
    done.add(first)
    after_first = len(npc.memory)
    assert _process_npc_reflection(game, make_npc_reflection(npc_id="npc_1"), done) is None
    assert len(npc.memory) == after_first


def test_npc_introduced_and_killed_in_the_same_scene_is_marked_deceased(load_engine: None) -> None:
    game = make_game_state()
    game.npcs = []
    metadata = {
        "npc_renames": [],
        "new_npcs": [{"name": "Mara Voss", "description": "A courier in a grey coat", "disposition": "neutral"}],
        "npc_details": [],
        "deceased_npcs": [{"npc_id": "Mara Voss"}],
        "lore_npcs": [],
    }
    apply_narrator_metadata(game, metadata, scene_present_ids=set(), world_addition="")
    mara = next(n for n in game.npcs if n.name == "Mara Voss")
    assert mara.status == "deceased"
