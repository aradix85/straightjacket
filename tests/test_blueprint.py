import random

import pytest

from straightjacket.engine.mechanics.adventure_crafter import (
    BlueprintSeed,
    assemble_blueprint_seed_from_ac,
    assemble_blueprint_seed_kishotenketsu,
    materialize_blueprint,
)
from straightjacket.engine.models_story import NarrativeState


def _voicing(act_count: int, revelations: int = 3, endings: int = 3) -> dict:
    return {
        "central_conflict": "The relic is contested",
        "antagonist_force": "The cult",
        "thematic_thread": "trust",
        "acts": [
            {"title": f"Act {i + 1}", "goal": "g", "mood": "tense", "transition_trigger": "t"} for i in range(act_count)
        ],
        "revelations": [{"content": f"reveal {i + 1}"} for i in range(revelations)],
        "possible_endings": [{"type": "earned", "description": f"end {i + 1}"} for i in range(endings)],
    }


def test_assemble_blueprint_seed_from_ac_is_deterministic_with_fixed_rng(load_engine: None) -> None:
    rng_a = random.Random(42)
    rng_b = random.Random(42)
    narrative_a = NarrativeState()
    narrative_b = NarrativeState()
    seed_a = assemble_blueprint_seed_from_ac(rng_a, narrative_a)
    seed_b = assemble_blueprint_seed_from_ac(rng_b, narrative_b)

    assert seed_a.structure_type == seed_b.structure_type == "3act"
    assert seed_a.themes == seed_b.themes
    assert len(seed_a.acts) == len(seed_b.acts)
    assert [a.phase for a in seed_a.acts] == [a.phase for a in seed_b.acts]


def test_assemble_blueprint_seed_from_ac_act_count_matches_yaml(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng

    rng = random.Random(7)
    narrative = NarrativeState()
    seed = assemble_blueprint_seed_from_ac(rng, narrative)

    assert len(seed.acts) == eng().adventure_crafter.blueprint.acts_three_act


def test_assemble_blueprint_seed_from_ac_phases_from_yaml(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng

    rng = random.Random(7)
    narrative = NarrativeState()
    seed = assemble_blueprint_seed_from_ac(rng, narrative)

    expected_phases = list(eng().adventure_crafter.blueprint.three_act_phases)
    assert [a.phase for a in seed.acts] == expected_phases


def test_assemble_blueprint_seed_from_ac_seeds_plotlines(load_engine: None) -> None:
    rng = random.Random(7)
    narrative = NarrativeState()
    assert narrative.plotlines_list == []

    assemble_blueprint_seed_from_ac(rng, narrative)

    assert any(p.status == "advancement" for p in narrative.plotlines_list)


def test_assemble_blueprint_seed_kishotenketsu_act_count_from_yaml(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng

    rng = random.Random(7)
    narrative = NarrativeState()
    seed = assemble_blueprint_seed_kishotenketsu(rng, narrative)

    assert seed.structure_type == "kishotenketsu"
    assert len(seed.acts) == eng().adventure_crafter.blueprint.acts_kishotenketsu


def test_assemble_blueprint_seed_kishotenketsu_does_not_roll_turning_points(load_engine: None) -> None:
    rng = random.Random(7)
    narrative = NarrativeState()
    seed = assemble_blueprint_seed_kishotenketsu(rng, narrative)

    assert all(act.turning_point is None for act in seed.acts)
    assert seed.revelation_seeds == []


def test_assemble_blueprint_seed_phases_from_yaml_kishotenketsu(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng

    rng = random.Random(7)
    narrative = NarrativeState()
    seed = assemble_blueprint_seed_kishotenketsu(rng, narrative)

    expected = list(eng().adventure_crafter.blueprint.kishotenketsu_phases)
    assert [a.phase for a in seed.acts] == expected


def test_scene_ranges_evenly_split_covers_full_range(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng

    rng = random.Random(7)
    narrative = NarrativeState()
    seed = assemble_blueprint_seed_from_ac(rng, narrative)

    total = list(eng().scene_range_default)
    first_start = seed.acts[0].scene_range[0]
    last_end = seed.acts[-1].scene_range[1]
    assert first_start == total[0]
    assert last_end == total[1]


def test_materialize_blueprint_uses_seed_phases_and_scene_ranges(load_engine: None) -> None:
    rng = random.Random(7)
    narrative = NarrativeState()
    seed = assemble_blueprint_seed_from_ac(rng, narrative)

    bp = materialize_blueprint(seed, _voicing(act_count=len(seed.acts)))

    assert bp.structure_type == "3act"
    assert [a.phase for a in bp.acts] == [a.phase for a in seed.acts]
    assert [a.scene_range for a in bp.acts] == [list(a.scene_range) for a in seed.acts]


def test_materialize_blueprint_uses_voicing_for_setting_fields(load_engine: None) -> None:
    rng = random.Random(7)
    narrative = NarrativeState()
    seed = assemble_blueprint_seed_from_ac(rng, narrative)

    bp = materialize_blueprint(seed, _voicing(act_count=len(seed.acts)))

    assert bp.central_conflict == "The relic is contested"
    assert bp.antagonist_force == "The cult"
    assert bp.thematic_thread == "trust"
    assert bp.acts[0].title == "Act 1"
    assert bp.acts[0].goal == "g"
    assert bp.acts[0].mood == "tense"
    assert bp.acts[0].transition_trigger == "t"


def test_materialize_blueprint_revelations_and_endings_from_voicing(load_engine: None) -> None:
    rng = random.Random(7)
    narrative = NarrativeState()
    seed = assemble_blueprint_seed_from_ac(rng, narrative)

    bp = materialize_blueprint(seed, _voicing(act_count=len(seed.acts)))

    assert len(bp.revelations) == 3
    assert bp.revelations[0].content == "reveal 1"
    assert bp.revelations[0].dramatic_weight in {"low", "medium", "high", "critical"}
    assert len(bp.possible_endings) == 3
    assert bp.possible_endings[0].type == "earned"
    assert bp.possible_endings[0].description == "end 1"


def test_materialize_blueprint_raises_on_act_count_mismatch(load_engine: None) -> None:
    rng = random.Random(7)
    narrative = NarrativeState()
    seed = assemble_blueprint_seed_from_ac(rng, narrative)

    bad_voicing = _voicing(act_count=len(seed.acts) + 1)
    with pytest.raises(ValueError, match="acts"):
        materialize_blueprint(seed, bad_voicing)


def test_materialize_blueprint_raises_on_revelation_count_mismatch(load_engine: None) -> None:
    rng = random.Random(7)
    narrative = NarrativeState()
    seed = assemble_blueprint_seed_from_ac(rng, narrative)

    bad_voicing = _voicing(act_count=len(seed.acts), revelations=2)
    with pytest.raises(ValueError, match="revelations"):
        materialize_blueprint(seed, bad_voicing)


def test_materialize_blueprint_kishotenketsu_path(load_engine: None) -> None:
    rng = random.Random(7)
    narrative = NarrativeState()
    seed = assemble_blueprint_seed_kishotenketsu(rng, narrative)

    bp = materialize_blueprint(seed, _voicing(act_count=len(seed.acts)))

    assert bp.structure_type == "kishotenketsu"
    assert len(bp.acts) == len(seed.acts)
    assert bp.acts[0].phase == seed.acts[0].phase


def test_blueprint_seed_is_frozen_dataclass(load_engine: None) -> None:
    import dataclasses

    rng = random.Random(7)
    narrative = NarrativeState()
    seed = assemble_blueprint_seed_from_ac(rng, narrative)

    assert isinstance(seed, BlueprintSeed)
    with pytest.raises(dataclasses.FrozenInstanceError):
        seed.structure_type = "kishotenketsu"


def test_call_story_architect_no_longer_in_src() -> None:
    import pathlib

    src = pathlib.Path(__file__).parent.parent / "src"
    hits = list(src.rglob("*.py"))
    for f in hits:
        text = f.read_text(encoding="utf-8")
        assert "call_story_architect" not in text, f"call_story_architect still referenced in {f}"
