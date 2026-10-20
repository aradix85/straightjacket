import random

import pytest

from straightjacket.engine.crafters import blueprint as blueprint_module
from straightjacket.engine.crafters.adventure_crafter import PlotPointHit, TurningPoint
from straightjacket.engine.crafters.blueprint import (
    BlueprintSeed,
    assemble_blueprint_seed_from_ac,
    materialize_blueprint,
)
from straightjacket.engine.crafters.config import crafter
from straightjacket.engine.gamemaster.keyed_scenes import has_keyed_scene_from
from tests._helpers import make_game_state


def _voicing(act_count: int, revelations: int | None = None, endings: int = 3) -> dict:
    return {
        "central_conflict": "The relic is contested",
        "antagonist_force": "The cult",
        "thematic_thread": "trust",
        "acts": [
            {"title": f"Act {i + 1}", "goal": "g", "mood": "tense", "transition_trigger": "t"} for i in range(act_count)
        ],
        "revelations": [
            {"content": f"reveal {i + 1}"} for i in range(act_count if revelations is None else revelations)
        ],
        "possible_endings": [{"type": "earned", "description": f"end {i + 1}"} for i in range(endings)],
    }


def _turning_point(*plot_points: tuple[str, str | None]) -> TurningPoint:
    return TurningPoint(
        plot_points=[PlotPointHit(theme="mystery", name=name, special_range=special) for name, special in plot_points],
        plotline="Plotline 1",
        opens_plotline=False,
        concludes_plotline=False,
    )


def test_assemble_blueprint_seed_from_ac_is_deterministic_with_fixed_rng(load_engine: None) -> None:
    seed_a = assemble_blueprint_seed_from_ac(
        random.Random(42), make_game_state(player_name="A", setting_id="starforged")
    )
    seed_b = assemble_blueprint_seed_from_ac(
        random.Random(42), make_game_state(player_name="B", setting_id="starforged")
    )

    assert seed_a.themes == seed_b.themes
    assert [a.phase for a in seed_a.acts] == [a.phase for a in seed_b.acts]
    assert [a.turning_point for a in seed_a.acts] == [a.turning_point for a in seed_b.acts]


def test_every_act_gets_its_own_turning_point(load_engine: None) -> None:
    seed = assemble_blueprint_seed_from_ac(random.Random(7), make_game_state(setting_id="starforged"))

    assert [a.phase for a in seed.acts] == list(crafter().adventure_crafter.blueprint.act_phases)
    assert len({id(a.turning_point) for a in seed.acts}) == len(seed.acts)


def test_assemble_blueprint_seed_from_ac_seeds_plotlines(load_engine: None) -> None:
    game = make_game_state(player_name="Hero", setting_id="starforged")
    assert game.narrative.plotlines_list == []

    assemble_blueprint_seed_from_ac(random.Random(7), game)

    assert any(p.status == "advancement" for p in game.narrative.plotlines_list)


def test_each_acts_revelation_is_seeded_from_its_own_turning_point(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    turning_points = [
        _turning_point(("Conclusion", "conclusion"), ("An Unrelated Detail", None), ("The Plot Thickens", None)),
        _turning_point(("A Quiet Morning", None), ("Another Quiet Morning", None)),
        _turning_point(("Conclusion", "conclusion"), ("Meta", "meta")),
    ]
    monkeypatch.setattr(blueprint_module, "roll_turning_point", lambda *_: turning_points.pop(0))
    game = make_game_state(setting_id="starforged")

    seed = assemble_blueprint_seed_from_ac(random.Random(7), game)

    seeds = [(a.revelation_seed.name if a.revelation_seed else None, a.revelation_trigger) for a in seed.acts]
    assert seeds == [
        ("The Plot Thickens", "ac:The Plot Thickens"),
        ("A Quiet Morning", ""),
        (None, ""),
    ]
    assert has_keyed_scene_from(game.narrative, "ac:The Plot Thickens")


def test_scene_ranges_evenly_split_covers_full_range(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng

    seed = assemble_blueprint_seed_from_ac(random.Random(7), make_game_state(setting_id="starforged"))

    total = list(eng().scene_range_default)
    assert seed.acts[0].scene_range[0] == total[0]
    assert seed.acts[-1].scene_range[1] == total[1]


def test_materialize_blueprint_uses_seed_phases_and_scene_ranges(load_engine: None) -> None:
    seed = assemble_blueprint_seed_from_ac(random.Random(7), make_game_state(setting_id="starforged"))

    bp = materialize_blueprint(seed, _voicing(act_count=len(seed.acts)))

    assert [a.phase for a in bp.acts] == [a.phase for a in seed.acts]
    assert [a.scene_range for a in bp.acts] == [list(a.scene_range) for a in seed.acts]


def test_materialize_blueprint_uses_voicing_for_setting_fields(load_engine: None) -> None:
    seed = assemble_blueprint_seed_from_ac(random.Random(7), make_game_state(setting_id="starforged"))

    bp = materialize_blueprint(seed, _voicing(act_count=len(seed.acts)))

    assert bp.central_conflict == "The relic is contested"
    assert bp.antagonist_force == "The cult"
    assert bp.thematic_thread == "trust"
    assert bp.acts[0].title == "Act 1"
    assert bp.acts[0].goal == "g"
    assert bp.acts[0].mood == "tense"
    assert bp.acts[0].transition_trigger == "t"


def test_materialize_blueprint_gives_each_act_its_revelation(load_engine: None) -> None:
    seed = assemble_blueprint_seed_from_ac(random.Random(7), make_game_state(setting_id="starforged"))

    bp = materialize_blueprint(seed, _voicing(act_count=len(seed.acts)))

    assert [(r.content, r.act_number, r.keyed_scene_source) for r in bp.revelations] == [
        (f"reveal {n}", n, act.revelation_trigger) for n, act in enumerate(seed.acts, start=1)
    ]
    assert bp.revealed == []
    assert len(bp.possible_endings) == 3
    assert bp.possible_endings[0].type == "earned"
    assert bp.possible_endings[0].description == "end 1"


def test_materialize_blueprint_raises_on_act_count_mismatch(load_engine: None) -> None:
    seed = assemble_blueprint_seed_from_ac(random.Random(7), make_game_state(setting_id="starforged"))

    with pytest.raises(ValueError, match="acts"):
        materialize_blueprint(seed, _voicing(act_count=len(seed.acts) + 1))


def test_materialize_blueprint_raises_on_revelation_count_mismatch(load_engine: None) -> None:
    seed = assemble_blueprint_seed_from_ac(random.Random(7), make_game_state(setting_id="starforged"))

    with pytest.raises(ValueError, match="revelations"):
        materialize_blueprint(seed, _voicing(act_count=len(seed.acts), revelations=len(seed.acts) - 1))


def test_blueprint_seed_is_frozen_dataclass(load_engine: None) -> None:
    import dataclasses

    seed = assemble_blueprint_seed_from_ac(random.Random(7), make_game_state(setting_id="starforged"))

    assert isinstance(seed, BlueprintSeed)
    with pytest.raises(dataclasses.FrozenInstanceError):
        seed.themes = []


def test_call_story_architect_no_longer_in_src() -> None:
    import pathlib

    src = pathlib.Path(__file__).parent.parent / "src"
    for f in src.rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        assert "call_story_architect" not in text, f"call_story_architect still referenced in {f}"
