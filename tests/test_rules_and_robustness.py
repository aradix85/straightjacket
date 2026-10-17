from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from straightjacket.engine.ai.metadata import apply_narrator_metadata
from straightjacket.engine.director import _process_npc_reflection
from straightjacket.engine.engine_loader import eng
from straightjacket.engine.models import GameState, NpcData, Resources
from tests._helpers import make_game_state, make_memory, make_npc, make_npc_reflection

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
    assert _process_npc_reflection(game, "npc_1", make_npc_reflection()) is None
    assert len(npc.memory) == before


def test_reflection_for_npc_the_engine_did_not_select_is_rejected(load_engine: None) -> None:
    npc = _profiled_npc("active", needs_reflection=False)
    game = _game_with(npc)
    before = len(npc.memory)
    assert _process_npc_reflection(game, "npc_1", make_npc_reflection()) is None
    assert len(npc.memory) == before


def test_npc_introduced_and_killed_in_the_same_scene_is_marked_deceased(load_engine: None) -> None:
    game = make_game_state(setting_id="classic")
    game.npcs = []
    metadata = {
        "npc_renames": [],
        "new_npcs": [{"name": "Mara Voss", "description": "A courier in a grey coat", "disposition": "neutral"}],
        "npc_details": [],
        "deceased_npcs": [{"npc_id": "Mara Voss"}],
        "lore_npcs": [],
    }
    apply_narrator_metadata(game, metadata, scene_present_ids=set(), world_addition="")
    mara = next(n for n in game.npcs if "Mara Voss" in n.aliases)
    assert mara.status == "deceased"


def test_a_figure_matched_by_description_keeps_the_named_npc_name(load_engine: None) -> None:
    game = make_game_state()
    game.world.current_location = "quarry road"
    game.npcs = [
        make_npc(
            id="npc_3",
            name="Corrin Hale",
            status="active",
            description="One of the two riders, he rides north by the quarry road in a warden's grey cloak.",
            last_location="quarry road",
        )
    ]
    metadata = {
        "npc_renames": [],
        "new_npcs": [
            {
                "name": "Warden archer",
                "description": "A man in a warden's grey cloak, his sleeves crusted with frost-rimed mud.",
                "disposition": "hostile",
            }
        ],
        "npc_details": [],
        "deceased_npcs": [],
        "lore_npcs": [],
    }
    apply_narrator_metadata(game, metadata, scene_present_ids=set(), world_addition="")
    [hale] = game.npcs
    assert hale.name == "Corrin Hale"
    assert "Warden archer" in hale.aliases


def test_an_npc_called_by_part_of_its_name_stays_one_npc(load_engine: None) -> None:
    game = make_game_state()
    game.npcs = [make_npc(id="npc_1", name="Kira Vance", description="A pilot.")]
    metadata = {
        "npc_renames": [],
        "new_npcs": [{"name": "Kira", "description": "A pilot.", "disposition": "neutral"}],
        "npc_details": [],
        "deceased_npcs": [],
        "lore_npcs": [],
    }
    apply_narrator_metadata(game, metadata, scene_present_ids=set(), world_addition="")
    [kira] = game.npcs
    assert kira.name == "Kira Vance"


@pytest.mark.parametrize(("label", "count"), [("Second deckhand", 2), ("Lunging deckhand", 1)])
def test_an_npc_the_engine_named_is_matched_only_by_its_own_label(load_engine: None, label: str, count: int) -> None:
    game = make_game_state(setting_id="classic")
    nerissa = make_npc(id="npc_4", name="Nerissa Ashcroft", name_rolled=True, aliases=["Lunging deckhand"])
    game.npcs = [nerissa]
    metadata = {
        "npc_renames": [],
        "new_npcs": [{"name": label, "description": "", "disposition": "hostile"}],
        "npc_details": [],
        "deceased_npcs": [],
        "lore_npcs": [],
    }
    apply_narrator_metadata(game, metadata, scene_present_ids=set(), world_addition="")
    assert nerissa.name == "Nerissa Ashcroft"
    assert len(game.npcs) == count


def _detail(npc_id: str, full_name: str) -> dict:
    return {
        "npc_renames": [],
        "new_npcs": [],
        "npc_details": [{"npc_id": npc_id, "full_name": full_name, "description": ""}],
        "deceased_npcs": [],
        "lore_npcs": [],
    }


def test_a_name_revealed_for_an_unnamed_figure_is_taken(load_engine: None) -> None:
    game = make_game_state()
    memory = [make_memory(scene=1, event="A voice on the comm", emotional_weight="neutral", importance=3)]
    game.npcs = [make_npc(id="npc_2", name="Unnamed woman on the comm", status="lore", memory=memory)]
    apply_narrator_metadata(game, _detail("npc_2", "Kestrel Vane"), scene_present_ids=set(), world_addition="")
    [kestrel] = game.npcs
    assert kestrel.name == "Kestrel Vane"
    assert "Unnamed woman on the comm" in kestrel.aliases


def test_blueprint_voicing_fixes_the_counts_in_its_schema_and_asks_again_once(load_engine: None) -> None:
    import json
    import random

    from straightjacket.engine.ai.blueprint_voicing import call_blueprint_voicing
    from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse
    from straightjacket.engine.mechanics.adventure_crafter import assemble_blueprint_seed_from_ac
    from tests.test_integration import _make_game

    game = _make_game()
    seed = assemble_blueprint_seed_from_ac(random.Random(1), game)
    blueprint = eng().adventure_crafter.blueprint

    def voicing(endings: int) -> str:
        return json.dumps(
            {
                "central_conflict": "A drowned city wants its name back",
                "antagonist_force": "The tide-priests",
                "thematic_thread": "Memory as debt",
                "acts": [{"title": "t", "goal": "g", "mood": "m", "transition_trigger": "x"} for _ in seed.acts],
                "revelations": [{"content": "r"} for _ in range(blueprint.revelations_per_blueprint)],
                "possible_endings": [{"type": "t", "description": "d"} for _ in range(endings)],
            }
        )

    class Scripted:
        def __init__(self, *replies: str) -> None:
            self.replies = list(replies)
            self.specs: list[AICallSpec] = []

        def create_message(self, spec: AICallSpec) -> AIResponse:
            self.specs.append(spec)
            return AIResponse(content=self.replies.pop(0) if len(self.replies) > 1 else self.replies[0])

    good = Scripted(voicing(blueprint.possible_endings_per_blueprint))
    result = call_blueprint_voicing(good, game, seed)
    assert result is not None
    assert len(good.specs) == 1
    props = good.specs[0].json_schema["properties"]
    for key, count in (
        ("acts", len(seed.acts)),
        ("revelations", blueprint.revelations_per_blueprint),
        ("possible_endings", blueprint.possible_endings_per_blueprint),
    ):
        assert (props[key]["minItems"], props[key]["maxItems"]) == (count, count)

    short = Scripted(voicing(blueprint.possible_endings_per_blueprint - 1))
    assert call_blueprint_voicing(short, game, seed) is None
    assert len(short.specs) == blueprint.voicing_count_retries + 1
    assert "wrong number of entries" in short.specs[-1].messages[-1]["content"]

    corrected = Scripted(
        voicing(blueprint.possible_endings_per_blueprint - 1), voicing(blueprint.possible_endings_per_blueprint)
    )
    assert call_blueprint_voicing(corrected, game, seed) is not None
    assert [m["role"] for m in corrected.specs[-1].messages] == ["user", "assistant", "user"]
