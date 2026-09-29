import pytest

from straightjacket.engine.engine_loader import eng
from straightjacket.engine.mechanics.facts import find_fact, settle_facts_by_miss
from straightjacket.engine.mechanics.move_effects import _oracle_table, has_story_complication
from straightjacket.engine.mechanics.move_outcome import resolve_move_outcome
from straightjacket.engine.models import GameState, ResolvedFact, RollResult
from straightjacket.engine.prompt_action import build_action_prompt
from tests._helpers import make_brain_result, make_game_state, make_npc


def _game(setting_id: str = "starforged") -> GameState:
    game = make_game_state(player_name="Ash", setting_id=setting_id, setting_genre=setting_id)
    game.world.current_location = "The Docks"
    game.narrative.scene_count = 3
    game.narrative.story_blueprint = None
    return game


def _useful(answer: str) -> ResolvedFact:
    return ResolvedFact(
        about=eng().fact_resolution.place_reference,
        about_name="The Docks",
        fact_type="useful",
        answer=answer,
        odds="fifty_fifty",
        location="The Docks",
    )


def _roll(result: str) -> RollResult:
    return RollResult(
        d1=2,
        c1=5,
        c2=6,
        stat_name="wits",
        stat_value=1,
        action_score=3,
        result=result,
        move="adventure/gather_information",
        match=False,
    )


def _prompt(game: GameState, result: str, target: str | None = None) -> str:
    brain = make_brain_result(move="adventure/gather_information", stat="wits", target_npc=target)
    return build_action_prompt(game, brain, _roll(result), [], [], player_words="search", consequence_sentences=[])


def test_an_information_miss_turns_useful_to_no(load_engine: None) -> None:
    game = _game()
    earlier = _useful("yes")
    game.world.facts.append(earlier)
    facts = settle_facts_by_miss(game, [earlier], "adventure/gather_information", "MISS")
    assert [(f.fact_type, f.answer) for f in facts] == [("useful", "no")]
    assert find_fact(game, earlier.about, "useful") is facts[0]
    assert earlier.answer == "yes"


def test_an_information_miss_settles_the_place_even_when_nobody_asked(load_engine: None) -> None:
    game = _game()
    facts = settle_facts_by_miss(game, [], "adventure/gather_information", "MISS")
    assert [(f.fact_type, f.answer, f.about_name) for f in facts] == [("useful", "no", "The Docks")]
    assert game.world.facts == facts


def test_the_settled_facts_reach_the_narrator(load_engine: None) -> None:
    game = _game()
    facts = settle_facts_by_miss(game, [], "adventure/gather_information", "MISS")
    brain = make_brain_result(move="adventure/gather_information", stat="wits")
    prompt = build_action_prompt(
        game, brain, _roll("MISS"), [], [], player_words="search", consequence_sentences=[], facts=facts
    )
    assert eng().fact_resolution.types["useful"].description in prompt


@pytest.mark.parametrize(
    ("move", "result"), [("adventure/face_danger", "MISS"), ("adventure/gather_information", "WEAK_HIT")]
)
def test_other_moves_and_hits_leave_useful_alone(load_engine: None, move: str, result: str) -> None:
    game = _game()
    earlier = _useful("yes")
    game.world.facts.append(earlier)
    assert settle_facts_by_miss(game, [earlier], move, result) == [earlier]
    assert game.world.facts == [earlier]


@pytest.mark.parametrize("result", ["MISS", "WEAK_HIT"])
def test_the_target_npc_volunteers_nothing_on_a_miss(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, result: str
) -> None:
    from straightjacket.engine import prompt_shared

    monkeypatch.setattr(prompt_shared, "compute_npc_gate", lambda *_: 4)
    game = _game()
    game.npcs.append(make_npc(id="npc_1", name="Kira", disposition="friendly"))
    expected = 0 if result == "MISS" else eng().information_gate.fact_budget_by_gate[4]
    assert f'fact_budget="{expected}"' in _prompt(game, result, target="npc_1")


def test_story_complication_only_where_the_setting_has_it(load_engine: None) -> None:
    assert has_story_complication(_game("starforged"))
    assert has_story_complication(_game("sundered_isles"))
    assert not has_story_complication(_game("classic"))


def _complication_rows(game: GameState) -> set[str]:
    table = _oracle_table(game, eng().pay_the_price.match_miss_oracle_path)
    assert table is not None
    return {row.text for row in table.rows if not row.oracle_rolls}


def _rolled_rows(consequence: str) -> list[str]:
    return [row for row in consequence.split("; ") if not row.startswith("Roll ")]


def test_a_matched_miss_rolls_a_story_complication_instead_of_pay_the_price(load_engine: None) -> None:
    game = _game("starforged")
    rows = _complication_rows(game)
    outcome = resolve_move_outcome(game, "adventure/face_danger", "MISS", match=True)
    assert outcome.pay_the_price
    assert all(row in rows for row in _rolled_rows(outcome.consequences[-1]))


@pytest.mark.parametrize(("setting_id", "match"), [("starforged", False), ("classic", True)])
def test_other_misses_pay_the_price(load_engine: None, setting_id: str, match: bool) -> None:
    game = _game(setting_id)
    rows = _complication_rows(_game("starforged"))
    for _ in range(20):
        outcome = resolve_move_outcome(game, "adventure/face_danger", "MISS", match=match)
        assert outcome.pay_the_price
        assert not any(row in rows for row in _rolled_rows(outcome.consequences[-1]))


@pytest.mark.parametrize("result", ["MISS", "WEAK_HIT"])
def test_the_narrator_gets_no_npc_knowledge_on_a_miss(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, result: str
) -> None:
    from straightjacket.engine import prompt_shared

    monkeypatch.setattr(prompt_shared, "compute_npc_gate", lambda *_: 4)
    game = _game()
    npc = make_npc(id="npc_1", name="Kira", disposition="friendly")
    npc.description = "A dockhand with tar-black hands."
    npc.agenda = "Sell the ledger to the harbour guild"
    npc.instinct = "Goes quiet and watches"
    npc.secrets = ["She burned the manifest herself"]
    game.npcs.append(npc)
    prompt = _prompt(game, result, target="npc_1")
    knowledge = ("Sell the ledger" in prompt, "burned the manifest" in prompt)
    assert knowledge == ((False, False) if result == "MISS" else (True, True))
    assert "Goes quiet and watches" in prompt
    if result == "MISS":
        assert "tar-black hands" in prompt


def _hidden_sources_game() -> GameState:
    from tests._helpers import make_act, make_blueprint, make_revelation

    game = _game()
    game.narrative.scene_count = 5
    game.narrative.story_blueprint = make_blueprint(
        acts=[make_act()],
        revelations=[make_revelation(content="The harbourmaster sold the route", dramatic_weight="high")],
    )
    game.narrative.director_guidance.narrator_guidance = "Let Kira name the buyer"
    return game


@pytest.mark.parametrize("result", ["MISS", "WEAK_HIT"])
def test_director_guidance_and_revelations_wait_for_a_hit(load_engine: None, result: str) -> None:
    prompt = _prompt(_hidden_sources_game(), result)
    shown = ("Let Kira name the buyer" in prompt, "sold the route" in prompt)
    assert shown == ((False, False) if result == "MISS" else (True, True))


@pytest.mark.parametrize("result", ["MISS", "WEAK_HIT"])
def test_everyone_present_withholds_on_a_miss(load_engine: None, monkeypatch: pytest.MonkeyPatch, result: str) -> None:
    from straightjacket.engine import prompt_shared
    from tests._helpers import make_memory

    monkeypatch.setattr(prompt_shared, "compute_npc_gate", lambda *_: 4)
    game = _game()
    target = make_npc(id="npc_1", name="Kira", disposition="friendly")
    bystander = make_npc(id="npc_2", name="Oren", disposition="friendly")
    bystander.memory = [make_memory(scene=2, event="Saw the courier leave by the east gate", importance=8)]
    game.npcs += [target, bystander]
    brain = make_brain_result(move="adventure/gather_information", stat="wits", target_npc="npc_1")
    prompt = build_action_prompt(
        game, brain, _roll(result), [], [], player_words="ask", consequence_sentences=[], activated_npcs=[bystander]
    )
    held = eng().information_gate.miss_stance.stance
    withheld = (
        f'<target_npc name="Kira" stance="{held}"' in prompt,
        f'<activated_npc name="Oren" stance="{held}"' in prompt,
        "east gate" not in prompt,
    )
    assert withheld == ((True, True, True) if result == "MISS" else (False, False, False))


def test_only_place_facts_can_be_settled_by_a_miss() -> None:
    from straightjacket.engine.engine_config import _build_fact_resolution

    raw = {
        "place_reference": "here",
        "max_per_turn": 2,
        "information_miss_settles": {"alert": "yes"},
        "types": {
            "alert": {
                "subject": "npc",
                "description": "on guard",
                "base_score": 0,
                "inputs": {},
                "cleared_by_hit": False,
            }
        },
    }
    with pytest.raises(ValueError, match="not a place fact type"):
        _build_fact_resolution(raw)
