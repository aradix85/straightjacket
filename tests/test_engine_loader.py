import json
import shutil
from collections.abc import Callable
from dataclasses import fields
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from straightjacket.engine import emotions_loader, engine_loader
from straightjacket.engine.config_loader import PROJECT_ROOT
from straightjacket.engine.crafters import config as crafters_config
from straightjacket.engine.crafters.config import crafter
from straightjacket.engine.game import startup
from straightjacket.engine.gamemaster import config as gamemaster_config
from straightjacket.engine.gamemaster import mythic_data
from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.gamemaster.mythic_data import load_mythic
from straightjacket.engine.ruleset import config as ruleset_config
from tests._helpers import change_config


def test_miss_clock_ticks_cover_every_position() -> None:
    assert set(gm().clocks.miss_ticks_by_position) == set(gm().effect_resolver.position_weights)


def test_npc_status_groups_name_only_known_statuses() -> None:
    groups = gm().npc_status_groups
    known = set(gm().enums.npc_statuses)
    for group in fields(groups):
        assert set(getattr(groups, group.name)) <= known, group.name


def test_mythic_data_with_a_value_of_another_type_than_its_field_refuses_to_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = json.loads((PROJECT_ROOT / "data" / "mythic_gme_2e.json").read_text(encoding="utf-8"))
    data["fate_chart"]["fifty_fifty"][4]["yes"] = "50"
    changed = tmp_path / "mythic_gme_2e.json"
    changed.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(mythic_data, "_MYTHIC_DATA_PATH", changed)
    with pytest.raises(ValueError, match=r"mythic_gme_2e\.json\.fate_chart\.fifty_fifty\[4\]\.yes: expected"):
        load_mythic()


def test_dice_sizes_cover_the_tables_they_roll() -> None:
    dice = gm().mythic_dice
    mythic = load_mythic()
    assert max(row.max for row in mythic.event_focus) == dice.event_focus_die
    assert max(row.max for row in mythic.scene_adjustment) == dice.scene_adjustment_die
    assert max(crafter().adventure_crafter.theme_die_table) == crafter().adventure_crafter_dice.theme_die


@pytest.mark.parametrize("gate", ["active_track", "no_active_track"])
def test_a_move_gate_on_a_track_type_that_does_not_exist_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, gate: str
) -> None:
    def gate_on_a_missing_type(section: dict[str, Any]) -> None:
        section["adventure/reach_your_destination"]["available"] = [{gate: "has_journey"}]

    change_config(monkeypatch, tmp_path, ruleset_config, "move_availability", gate_on_a_missing_type)
    with pytest.raises(ValueError, match="'has_journey', which is no track type"):
        ruleset_config.rules()


@pytest.mark.parametrize(
    ("rule", "message"),
    [
        ({"never": False}, "never other than true is not allowed"),
        ({"never": "false"}, "never other than true is not allowed"),
        ({"never": True, "available": []}, "Expected exactly one of: never, available"),
        ({"available": [{"active_track": "vow", "bonded_track": "connection"}]}, "Invalid move_availability condition"),
    ],
    ids=["never_false", "never_as_text", "two_keys", "condition_with_two_keys"],
)
def test_a_move_availability_rule_of_the_wrong_shape_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, rule: dict[str, object], message: str
) -> None:
    def reshape(section: dict[str, Any]) -> None:
        section["adventure/face_danger"] = rule

    change_config(monkeypatch, tmp_path, ruleset_config, "move_availability", reshape)
    with pytest.raises(ValueError, match=message):
        ruleset_config.rules()


_WrongValue = tuple[ModuleType, str, Callable[[dict[str, Any]], None], str]


def _set(*path: str, value: object) -> Callable[[dict[str, Any]], None]:
    def change(section: dict[str, Any]) -> None:
        holder = section
        for key in path[:-1]:
            holder = holder[key]
        holder[path[-1]] = value

    return change


def _unset(*path: str) -> Callable[[dict[str, Any]], None]:
    def change(section: dict[str, Any]) -> None:
        holder = section
        for key in path[:-1]:
            holder = holder[key]
        del holder[path[-1]]

    return change


@pytest.mark.parametrize(
    "case",
    [
        (gamemaster_config, "pacing", _set("director_interval", value="3"), "pacing.director_interval"),
        (gamemaster_config, "pacing", _set("director_interval", value=True), "expected <class 'int'>"),
        (gamemaster_config, "pacing", _set("director_interval", value=None), "got None"),
        (gamemaster_config, "pacing", _set("weak_hit_clock_tick_chance", value="0.5"), "'float'"),
        (gamemaster_config, "pacing", _set("director_interval", value=2.5), "expected <class 'int'>"),
        (gamemaster_config, "pacing", _set("weak_hit_clock_tick_chance", value=True), "'float'"),
        (gamemaster_config, "npc", _set("gate_memory_counts", value={"0": 0}), "gate_memory_counts key"),
        (gamemaster_config, "clocks", _set("miss_ticks_by_position", "risky", value="2"), "position.risky: expected"),
        (gamemaster_config, "stopwords", _set("general", value=["the", 3]), r"stopwords.general\[1\]: expected"),
        (gamemaster_config, "pacing", _unset("director_interval"), "pacing: missing keys .'director_interval'"),
        (gamemaster_config, "stopwords", _set("general", value="the"), "stopwords.general: expected list"),
        (gamemaster_config, "clocks", _set("complication", value=[4]), "complication: expected dict"),
        (gamemaster_config, "clocks", _set("complication", "extra", value=1), "complication: unknown keys .'extra'"),
        (ruleset_config, "boasts", _set("options", value=[]), "boasts.options: expected dict"),
        (
            ruleset_config,
            "move_availability",
            _set("combat/strike", "available", value="in_control"),
            "combat/strike.available: expected list",
        ),
        (
            ruleset_config,
            "move_availability",
            _set("combat/strike", "available", value=[{"combat_pos_in": "in_control"}]),
            "combat_pos_in: expected list",
        ),
        (
            ruleset_config,
            "move_outcomes",
            _set("adventure/face_danger", "strong_hit", value="momentum +1"),
            "adventure/face_danger.effects.strong_hit: expected list",
        ),
        (
            ruleset_config,
            "move_outcomes",
            _set("quest/fulfill_your_vow", "recommit_on_miss", value=1),
            "quest/fulfill_your_vow.recommit_on_miss: expected",
        ),
        (
            ruleset_config,
            "move_outcomes",
            _set("suffer/endure_harm", "handler", value="endure"),
            "suffer/endure_harm: unknown move-outcome handler 'endure'",
        ),
        (
            ruleset_config,
            "move_outcomes",
            _set("suffer/endure_harm", "miss", value=[]),
            "a move with a handler holds handler and params",
        ),
        (
            ruleset_config,
            "move_outcomes",
            _set("suffer/endure_harm", "params", "recovery", value="1"),
            "suffer/endure_harm.params.recovery: expected",
        ),
        (
            ruleset_config,
            "move_outcomes",
            _set("adventure/face_danger", value=3),
            "adventure/face_danger: expected dict",
        ),
        (
            ruleset_config,
            "move_outcomes",
            _set("quest/fulfill_your_vow", "recommit_on_miss", value=None),
            "quest/fulfill_your_vow.recommit_on_miss: expected str",
        ),
        (
            ruleset_config,
            "move_outcomes",
            _unset("suffer/endure_harm", "params", "table"),
            "ruleset.move_outcomes.suffer/endure_harm.params: missing keys .'table'",
        ),
    ],
    ids=[
        "text_for_a_number",
        "flag_for_a_number",
        "nothing_for_a_number",
        "text_for_a_fraction",
        "fraction_for_a_number",
        "flag_for_a_fraction",
        "text_for_a_number_key",
        "text_for_a_number_in_a_mapping",
        "number_in_a_list_of_text",
        "missing_key",
        "text_for_a_list",
        "list_for_a_section",
        "unknown_key_inside_a_section",
        "list_for_a_mapping",
        "text_for_the_conditions",
        "text_for_the_positions",
        "text_for_a_list_of_effects",
        "number_for_an_outcome_text",
        "unknown_handler",
        "effects_beside_a_handler",
        "text_for_a_handler_number",
        "number_for_a_move_outcome",
        "nothing_for_an_outcome_text",
        "missing_handler_parameter",
    ],
)
def test_a_config_value_of_the_wrong_type_stops_loading(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, case: _WrongValue
) -> None:
    layer, section, change, message = case
    change_config(monkeypatch, tmp_path, layer, section, change)
    load = gamemaster_config.gm if layer is gamemaster_config else ruleset_config.rules
    with pytest.raises(ValueError, match=message):
        load()


def test_a_whole_number_serves_where_a_fraction_is_asked(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    change_config(monkeypatch, tmp_path, gamemaster_config, "pacing", _set("weak_hit_clock_tick_chance", value=1))
    assert gamemaster_config.gm().pacing.weak_hit_clock_tick_chance == 1


def test_a_section_no_settings_field_holds_stops_loading(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    change_config(monkeypatch, tmp_path, gamemaster_config, "pacing", lambda _section: None)
    (tmp_path / "gamemaster" / "stray.yaml").write_text("stray: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"gamemaster: unknown keys \['stray'\]"):
        gamemaster_config.gm()


@pytest.mark.parametrize(
    ("layer", "section", "missing"),
    [
        (gamemaster_config, "pacing", "gamemaster: missing keys"),
        (ruleset_config, "move_outcomes", "ruleset: missing keys"),
    ],
    ids=["a_bound_section", "a_section_parsed_by_hand"],
)
def test_a_missing_section_stops_loading(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, layer: ModuleType, section: str, missing: str
) -> None:
    change_config(monkeypatch, tmp_path, layer, section, lambda _section: None)
    (tmp_path / layer.__name__.split(".")[-2] / f"{section}.yaml").unlink()
    load = gamemaster_config.gm if layer is gamemaster_config else ruleset_config.rules
    with pytest.raises(ValueError, match=rf"{missing} \[.*'{section}'"):
        load()


def test_the_startup_check_loads_every_store_before_it_asks_the_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    caches: list[dict[Path, object]] = [{}, {}, {}, {}]
    for store, cache in zip((engine_loader, gamemaster_config, crafters_config, ruleset_config), caches, strict=True):
        monkeypatch.setattr(store, "_cache", cache)
    loaded: list[int] = []
    monkeypatch.setattr(startup, "check_configured_models", lambda: loaded.extend(len(cache) for cache in caches))
    startup.check_startup()
    assert loaded == [1, 1, 1, 1]


def test_a_wrong_value_in_a_store_stops_the_start(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(startup, "check_configured_models", lambda: None)
    change_config(monkeypatch, tmp_path, ruleset_config, "boasts", _set("options", value=[]))
    with pytest.raises(ValueError, match=r"ruleset\.boasts\.options: expected dict"):
        startup.check_startup()


@pytest.mark.parametrize(
    ("file", "text", "message"),
    [
        ("stray.yaml", "stray: 1\n", r"emotions: unknown keys \['stray'\]"),
        ("importance.yaml", "importance:\n  joy: high\n", r"emotions\.importance\.joy: expected <class 'int'>"),
        ("keyword_boosts.yaml", "keyword_boosts:\n  '7':\n  - death\n", r"emotions\.keyword_boosts key: expected"),
    ],
    ids=["unknown_section", "text_for_a_score", "text_for_a_score_key"],
)
def test_an_emotions_file_that_does_not_fit_stops_loading(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, file: str, text: str, message: str
) -> None:
    folder = tmp_path / "emotions"
    shutil.copytree(PROJECT_ROOT / "emotions", folder)
    (folder / file).write_text(text, encoding="utf-8")
    monkeypatch.setattr(emotions_loader, "_EMOTIONS_DIR", folder)
    with pytest.raises(ValueError, match=message):
        emotions_loader.importance_map()
