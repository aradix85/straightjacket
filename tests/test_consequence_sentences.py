import pytest

from straightjacket.engine.models import (
    BrainResult,
    ClockEvent,
    Consequence,
    GameState,
    RollResult,
    consequence,
)
from straightjacket.engine.prompt_action import build_action_prompt
from straightjacket.engine.ruleset.consequences import (
    generate_consequence_sentences,
    pick_template,
    resolve_consequence_sentence,
)
from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
from tests._helpers import action_prompt_kwargs, make_brain_result, make_game_state, make_npc


def _game() -> GameState:
    game = make_game_state(player_name="Ash", setting_id="starforged", setting_genre="starforged")
    game.world.current_location = "The Docks"
    game.narrative.scene_count = 3
    return game


def _brain(target: str | None = None) -> BrainResult:
    return make_brain_result(
        move="adventure/face_danger", stat="edge", player_intent="climb the wall", target_npc=target
    )


def _roll(result: str = "MISS") -> RollResult:
    return RollResult(
        d1=2,
        c1=8,
        c2=9,
        stat_name="edge",
        stat_value=2,
        action_score=7,
        result=result,
        move="adventure/face_danger",
        match=False,
    )


def test_pick_template_returns_string() -> None:
    result = pick_template("health_light")
    assert isinstance(result, str)
    assert len(result) > 0


def test_pick_template_unknown_key_raises() -> None:
    with pytest.raises(KeyError):
        pick_template("nonexistent_key")


@pytest.mark.parametrize(
    ("cons", "npc", "must_contain"),
    [
        (consequence("track_loss", track="health", n=1), "", "Ash"),
        (consequence("track_loss", track="health", n=2), "", "Ash"),
        (consequence("track_loss", track="spirit", n=1), "", ""),
        (consequence("track_loss", track="supply", n=1), "", ""),
        (consequence("momentum_change", n=-2), "", ""),
        (consequence("track_gain", track="health", n=1), "", ""),
        (consequence("bond_progress", name="Kira", n=2), "", "Kira"),
        (consequence("disposition_shift", name="Kira", old="wary", new="neutral"), "", "Kira"),
    ],
)
def test_resolve_consequence_produces_sentence(cons: Consequence, npc: str, must_contain: str) -> None:
    sentence = resolve_consequence_sentence(cons, "Ash", npc, "The Docks")
    assert sentence != ""
    assert "{" not in sentence
    if must_contain:
        assert must_contain in sentence


@pytest.mark.parametrize("kind", ["gather_information", "compel", "make_a_connection"])
def test_a_complication_is_told_as_a_sentence_naming_the_player(kind: str) -> None:
    sentence = resolve_consequence_sentence(consequence("complication", kind=kind), "Ash", "", "")
    assert "Ash" in sentence
    assert "{" not in sentence


@pytest.mark.parametrize(
    "cons",
    [
        consequence("mark_progress", n=2),
        consequence("experience_reward"),
        consequence("legacy_reward", track="bonds"),
        consequence("chained_move", move="Test Your Bond", result="MISS"),
        consequence("oracle_result", table="Pay the Price", result="A bond is tested, health -1"),
        consequence("track_loss", track="companion_health", n=1),
    ],
)
def test_a_consequence_without_a_sentence_of_its_own_is_not_told_as_one(cons: Consequence) -> None:
    assert resolve_consequence_sentence(cons, "Ash", "Kira", "") == ""


def test_an_impact_is_labelled_and_told_by_its_rulesets_label(load_engine: None) -> None:
    game = _game()
    game.resources.meters["health"] = 0
    game.impacts = ["wounded"]
    result = resolve_move_outcome(game, "suffer/endure_harm", "MISS", target_npc_id=None, match=False)
    marked = [c for c in result.consequences if c.kind == "mark_impact"]
    assert [c.label for c in marked] == ["mark permanently harmed"]
    assert "permanently harmed" in resolve_consequence_sentence(marked[0], "Ash", "", "")


def test_a_momentum_change_labels_its_sign() -> None:
    assert (consequence("momentum_change", n=2).label, consequence("momentum_change", n=-1).label) == (
        "momentum +2",
        "momentum -1",
    )


def test_generate_sentences_from_consequences() -> None:
    sentences = generate_consequence_sentences(
        [consequence("track_loss", track="health", n=2), consequence("momentum_change", n=-3)], [], _game(), _brain()
    )
    assert len(sentences) == 2
    assert all(isinstance(s, str) and len(s) > 0 for s in sentences)


def test_generate_sentences_with_clock_events() -> None:
    clock_events = [ClockEvent(clock="Looming storm", trigger="The storm breaks", autonomous=False, triggered=False)]
    sentences = generate_consequence_sentences([], clock_events, _game(), _brain())
    assert len(sentences) >= 1


def test_generate_sentences_with_triggered_clock() -> None:
    clock_events = [ClockEvent(clock="Vault heist", trigger="The vault opens", autonomous=False, triggered=True)]
    sentences = generate_consequence_sentences([], clock_events, _game(), _brain())
    assert any("Vault heist" in s or "vault" in s.lower() for s in sentences)


def test_generate_sentences_empty_returns_empty() -> None:
    sentences = generate_consequence_sentences([], [], _game(), _brain())
    assert sentences == []


def test_generate_sentences_with_npc_target() -> None:
    game = _game()
    game.npcs.append(make_npc(id="npc_1", name="Kira", disposition="distrustful"))
    sentences = generate_consequence_sentences(
        [consequence("disposition_shift", name="Kira", old="distrustful", new="wary")], [], game, _brain(target="npc_1")
    )
    assert len(sentences) >= 1
    assert any("Kira" in s for s in sentences)


def test_consequence_tags_in_prompt() -> None:
    game = _game()
    game.narrative.story_blueprint = None
    sentences = ["The hit is bad. Ash feels something give.", "Whatever advantage Ash had, it's gone."]
    prompt = build_action_prompt(
        game,
        _brain(),
        _roll("MISS"),
        [consequence("track_loss", track="health", n=2), consequence("momentum_change", n=-3)],
        [],
        **action_prompt_kwargs(player_words="climb the wall", consequence_sentences=sentences),
    )
    assert "<consequence>" in prompt
    assert "The hit is bad" in prompt
    assert "Whatever advantage" in prompt


def test_no_consequence_tags_when_empty() -> None:
    game = _game()
    game.narrative.story_blueprint = None
    prompt = build_action_prompt(
        game,
        _brain(),
        _roll("STRONG_HIT"),
        [],
        [],
        **action_prompt_kwargs(player_words="climb the wall"),
    )
    assert "</consequence>" not in prompt


def test_task_mentions_consequence_weaving() -> None:
    game = _game()
    game.narrative.story_blueprint = None
    prompt = build_action_prompt(
        game,
        _brain(),
        _roll("MISS"),
        [consequence("track_loss", track="health", n=1)],
        [],
        **action_prompt_kwargs(player_words="climb", consequence_sentences=["Pain flares."]),
    )
    assert "<consequence>" in prompt.lower()
