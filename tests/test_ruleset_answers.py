import pytest

from straightjacket.engine.gamemaster import questions
from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.ruleset import answers
from straightjacket.engine.ruleset.progress import menace_total_boxes
from tests._helpers import make_game_state, make_npc, make_progress_track, make_scene_log_entry, make_threat


def test_the_game_package_installs_the_ironsworn_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    from straightjacket.engine import game

    monkeypatch.setattr(questions, "_answers", None)
    importlib.reload(game)
    assert questions.answers() is answers


def test_without_installed_answers_the_game_master_cannot_ask(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(questions, "_answers", None)
    with pytest.raises(RuntimeError, match="No ruleset answers"):
        questions.answers()


@pytest.mark.parametrize(
    ("result", "outcome"),
    [
        ("STRONG_HIT", "success"),
        ("WEAK_HIT", "partial"),
        ("MISS", "failure"),
        ("dialog", "dialog"),
        ("opening", "opening"),
    ],
)
def test_a_result_reaches_the_game_master_as_its_outcome(load_engine: None, result: str, outcome: str) -> None:
    assert questions.outcome_of(result) == outcome


def test_a_label_the_ruleset_does_not_know_raises(load_engine: None) -> None:
    with pytest.raises(KeyError):
        questions.outcome_of("MATCH")


def test_the_narrator_is_told_the_rulesets_own_result_names(load_engine: None) -> None:
    from straightjacket.engine.prompt_blocks import task_action
    from straightjacket.engine.prompt_loader import _ensure_loaded

    names = answers.results_by_outcome()
    assert names == {"success": "STRONG_HIT", "partial": "WEAK_HIT", "failure": "MISS"}
    templates = _ensure_loaded()
    for key in ("narrator_system", "task_action"):
        assert not any(name in templates[key] for name in names.values()), key
    assert names["success"] in task_action()


def test_the_ruleset_says_which_threats_are_active_and_which_overcome_ones_press_on(load_engine: None) -> None:
    from straightjacket.engine.ruleset.threats import active_threats, overcome_threats, overcome_under_pressure

    game = make_game_state(player_name="Test")
    active = make_threat(id="t_active", name="Raiders")
    pressing = make_threat(id="t_pressing", name="Storm", status="overcome")
    pressing.menace_ticks = pressing.max_menace_ticks
    quiet = make_threat(id="t_quiet", name="Wolves", status="overcome")
    game.threats = [active, pressing, quiet]
    assert [t.id for t in active_threats(game)] == ["t_active"]
    assert [t.id for t in overcome_threats(game)] == ["t_pressing", "t_quiet"]
    assert [(e.threat_id, e.source) for e in overcome_under_pressure(game)] == [
        ("t_pressing", "overcome_under_pressure")
    ]


@pytest.mark.parametrize(
    ("value", "level"), [(0, "critical"), (1, "critical"), (2, "low"), (3, "steady"), (5, "steady")]
)
def test_strain_is_a_level_per_meter(load_engine: None, value: int, level: str) -> None:
    game = make_game_state(player_name="Test")
    game.resources.meters["health"] = value
    assert answers.strain(game) == [level, "steady", "steady"]


@pytest.mark.parametrize(
    ("move", "result", "gained"),
    [
        ("adventure/secure_an_advantage", "WEAK_HIT", True),
        ("adventure/secure_an_advantage", "MISS", False),
        ("adventure/face_danger", "STRONG_HIT", False),
    ],
)
def test_an_advantage_is_gained_by_a_hit_on_an_advantage_move(
    load_engine: None, move: str, result: str, gained: bool
) -> None:
    game = make_game_state(player_name="Test")
    game.narrative.session_log.append(make_scene_log_entry(scene=1, move=move, result=result))
    assert answers.gained_advantage(game) is gained


@pytest.mark.parametrize(
    ("move", "gathers"),
    [
        ("adventure/gather_information", True),
        ("adventure/secure_an_advantage", False),
        ("dialog", False),
    ],
)
def test_only_the_information_moves_gather_information(load_engine: None, move: str, gathers: bool) -> None:
    assert answers.gathers_information(move) is gathers


def test_closeness_is_the_connection_s_filled_boxes(load_engine: None) -> None:
    game = make_game_state(player_name="Test")
    game.npcs = [make_npc(id="npc_1", name="Kira")]
    game.progress_tracks.append(
        make_progress_track(id="connection_npc_1", name="Kira", track_type="connection", ticks=12)
    )
    assert answers.closeness(game, "npc_1") == 3
    assert answers.closeness(game, "npc_2") == 0


def test_a_danger_is_open_while_its_threat_is_active_and_not_full(load_engine: None) -> None:
    game = make_game_state(player_name="Test")
    full = make_threat(id="t_full", name="Full")
    full.menace_ticks = full.max_menace_ticks
    game.threats = [make_threat(id="t_open", name="Open"), full]
    dangers = {d.id: d for d in answers.dangers(game)}
    assert dangers["t_open"].open
    assert not dangers["t_full"].open
    assert dangers["t_full"].progress == menace_total_boxes(full)


def test_the_game_master_s_time_for_a_place_change_is_its_own(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.world import resolve_time_progression

    assert resolve_time_progression("combat/strike", has_location_change=True) == gm().location.change_time
    assert resolve_time_progression("recover/resupply", has_location_change=False) == "moderate"
    assert resolve_time_progression("quest/swear_an_iron_vow", has_location_change=False) == "short"
