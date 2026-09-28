import json
import random
from typing import Any

import pytest

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse
from straightjacket.engine.engine_loader import eng
from straightjacket.engine.models import (
    EngineConfig,
    FactRequest,
    FateResult,
    GameState,
    NarrationEntry,
    ResolvedFact,
    RollResult,
    SceneLogEntry,
)
from tests._helpers import make_npc

_CONFIG = EngineConfig(narration_lang="English")


def _game() -> GameState:
    game = GameState(
        player_name="Kael",
        character_concept="A wandering scholar",
        setting_id="classic",
        setting_genre="dark_fantasy",
        setting_tone="serious_balanced",
        setting_description="A world of fading magic.",
        stats={"edge": 1, "heart": 2, "iron": 1, "shadow": 1, "wits": 2},
    )
    game.resources.momentum = 6
    game.world.current_location = "Abandoned Library"
    game.world.time_of_day = "evening"
    game.world.chaos_factor = 5
    game.npcs = [
        make_npc(id="npc_1", name="Mira", disposition="friendly", description="An archivist."),
        make_npc(id="npc_2", name="Brannoc", disposition="hostile", description="A guard."),
    ]
    game.narrative.scene_count = 3
    game.narrative.narration_history = [
        NarrationEntry(scene=3, prompt_summary="Opening", narration="The library is cold and silent.")
    ]
    game.narrative.session_log = [
        SceneLogEntry(scene=3, scene_type="expected", summary="Opening", move="opening", result="opening")
    ]
    return game


def _fact(
    fact_type: str, about: str = "here", answer: str = "yes", location: str = "Abandoned Library"
) -> ResolvedFact:
    return ResolvedFact(
        about=about, about_name=location, fact_type=fact_type, answer=answer, odds="fifty_fifty", location=location
    )


def _fate(answer: str) -> FateResult:
    return FateResult(answer=answer, odds="fifty_fifty", chaos_factor=5, method="fate_chart", roll=40, question="")


@pytest.fixture
def counted_fate(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    from straightjacket.engine.mechanics import facts

    calls: list[str] = []

    def _resolve(game: Any, odds: str, chaos_factor: int, question: str) -> FateResult:
        calls.append(question)
        return _fate("yes")

    monkeypatch.setattr(facts, "resolve_fate", _resolve)
    return calls


def test_odds_follow_base_score_and_npc_disposition(load_engine: None) -> None:
    from straightjacket.engine.mechanics.facts import fact_odds

    game = _game()
    assert fact_odds(game, FactRequest(fact_type="locked", about="here")) == "fifty_fifty"
    assert fact_odds(game, FactRequest(fact_type="occupied", about="here")) == "unlikely"
    assert fact_odds(game, FactRequest(fact_type="alert", about="npc_2")) == "very_likely"
    assert fact_odds(game, FactRequest(fact_type="alert", about="npc_1")) == "unlikely"


def test_an_unknown_fact_type_raises(load_engine: None) -> None:
    from straightjacket.engine.mechanics.facts import fact_odds

    with pytest.raises(KeyError):
        fact_odds(_game(), FactRequest(fact_type="haunted", about="here"))


def test_a_resolved_fact_is_stored_and_reused(load_engine: None, counted_fate: list[str]) -> None:
    from straightjacket.engine.mechanics.facts import resolve_fact

    game = _game()
    first = resolve_fact(game, FactRequest(fact_type="alert", about="npc_2"))
    second = resolve_fact(game, FactRequest(fact_type="alert", about="npc_2"))

    assert second is first
    assert counted_fate == ["alert:npc_2"]
    assert game.world.facts == [first]
    assert first.about_name == "Brannoc"
    assert first.location == "Abandoned Library"
    assert first.odds == "very_likely"


def test_a_fixed_seed_gives_the_same_answer(load_engine: None) -> None:
    from straightjacket.engine.mechanics.facts import resolve_fact

    answers = []
    for _ in range(2):
        random.seed(7)
        answers.append(resolve_fact(_game(), FactRequest(fact_type="locked", about="here")).answer)
    assert answers[0] == answers[1]


def test_moving_clears_the_facts_and_staying_keeps_them(load_engine: None) -> None:
    from straightjacket.engine.mechanics import update_location

    game = _game()
    game.world.facts = [_fact("locked")]
    update_location(game, "the abandoned library")
    assert len(game.world.facts) == 1
    update_location(game, "Harbor Market")
    assert game.world.facts == []


def test_a_chapter_start_clears_the_facts(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _reset_chapter_mechanics

    game = _game()
    game.world.facts = [_fact("locked")]
    _reset_chapter_mechanics(game)
    assert game.world.facts == []


def test_a_succession_clears_the_facts(load_engine: None) -> None:
    from straightjacket.engine.game.succession import _reset_for_successor

    game = _game()
    game.world.facts = [_fact("locked")]
    _reset_for_successor(game, [], [], [], [])
    assert game.world.facts == []


def test_a_location_correction_clears_the_facts(load_engine: None) -> None:
    from straightjacket.engine.correction.ops import _op_location_edit

    game = _game()
    game.world.facts = [_fact("locked")]
    _op_location_edit(game, {"value": "Abandoned Library"})
    assert len(game.world.facts) == 1
    _op_location_edit(game, {"value": "Harbor Market"})
    assert game.world.facts == []


def test_a_hit_clears_only_the_types_that_say_so(load_engine: None) -> None:
    from straightjacket.engine.mechanics import clear_facts_settled_by_hit

    game = _game()
    locked, alert = _fact("locked"), _fact("alert", about="npc_2")
    game.world.facts = [locked, alert]

    clear_facts_settled_by_hit(game, [locked, alert], "MISS")
    assert game.world.facts == [locked, alert]
    clear_facts_settled_by_hit(game, [locked, alert], "WEAK_HIT")
    assert game.world.facts == [alert]


def test_a_hit_does_not_settle_a_no(load_engine: None) -> None:
    from straightjacket.engine.mechanics import clear_facts_settled_by_hit

    game = _game()
    nothing_useful = _fact("useful", answer="no")
    game.world.facts = [nothing_useful]
    clear_facts_settled_by_hit(game, [nothing_useful], "STRONG_HIT")
    assert game.world.facts == [nothing_useful]


def test_remembered_facts_come_back_only_at_their_own_place(load_engine: None) -> None:
    from straightjacket.engine.mechanics import remember_facts

    game = _game()
    here, elsewhere = _fact("locked"), _fact("useful", location="Harbor Market")
    remember_facts(game, [here, elsewhere])
    assert game.world.facts == [here]


def test_generation_categories_match_the_yaml(load_engine: None) -> None:
    from straightjacket.engine.mechanics.generation import _GENERATORS

    assert set(eng().generation.categories) == set(_GENERATORS)


def test_an_unknown_generation_category_raises(load_engine: None) -> None:
    from straightjacket.engine.mechanics.generation import generate

    with pytest.raises(KeyError, match="Unknown generation category"):
        generate(_game(), "settlement", FactRequest(fact_type="locked", about="here"))


def test_every_fact_input_has_an_implementation(load_engine: None) -> None:
    from straightjacket.engine.mechanics.facts import _INPUTS

    for name, spec in eng().fact_resolution.types.items():
        assert set(spec.inputs) <= set(_INPUTS), name
        if "npc_disposition" in spec.inputs:
            assert spec.subject == "npc", name


def test_a_doublet_queues_a_random_event(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.mechanics import drain_pending_events, fate
    from straightjacket.engine.mechanics.facts import resolve_fact

    original = fate.resolve_fate_chart
    monkeypatch.setattr(fate, "resolve_fate_chart", lambda odds, cf, question: original(odds, cf, question, roll=55))
    drain_pending_events()
    resolve_fact(_game(), FactRequest(fact_type="locked", about="here"))
    events = drain_pending_events()
    assert [e.source for e in events] == ["fate_doublet"]


def test_the_brain_schema_offers_only_known_types_and_subjects(load_engine: None) -> None:
    from straightjacket.engine.ai.schemas import get_brain_output_schema

    facts = get_brain_output_schema(["adventure/face_danger"], [], ["npc_1"], [])["properties"]["undetermined_facts"]
    place, npc = facts["items"]["anyOf"]
    assert place["properties"]["fact_type"]["enum"] == ["locked", "occupied", "useful"]
    assert place["properties"]["about"]["enum"] == ["here"]
    assert npc["properties"]["fact_type"]["enum"] == ["alert", "present"]
    assert npc["properties"]["about"]["enum"] == ["npc_1"]
    assert facts["maxItems"] == eng().fact_resolution.max_per_turn

    alone = get_brain_output_schema(["adventure/face_danger"], [], [], [])["properties"]["undetermined_facts"]
    assert len(alone["items"]["anyOf"]) == 1


def _brain(**overrides: Any) -> dict[str, Any]:
    brain: dict[str, Any] = {
        "type": "action",
        "move": "adventure/face_danger",
        "stat": "wits",
        "approach": "quietly",
        "target_npc": None,
        "dialog_only": False,
        "player_intent": "I force the vault door",
        "world_addition": None,
        "location_change": None,
        "track_name": "Open the vault",
        "track_rank": "dangerous",
        "target_track": None,
        "bonus_id": None,
        "undetermined_facts": [{"fact_type": "locked", "about": "here"}],
        "boasts": [],
    }
    brain.update(overrides)
    return brain


def test_the_brain_rejects_a_fact_about_an_unknown_npc(load_engine: None) -> None:
    from straightjacket.engine.ai.brain import call_brain
    from straightjacket.engine.ai.provider_base import AIUnavailableError
    from tests._mocks import MockProvider

    content = json.dumps(_brain(undetermined_facts=[{"fact_type": "alert", "about": "npc_9"}]))
    with pytest.raises(AIUnavailableError, match="cannot be about"):
        call_brain(MockProvider(response_content=content), _game(), "I slip past the guard")


def test_the_brain_prompt_lists_the_fact_types(load_engine: None) -> None:
    from straightjacket.engine.ai.brain import call_brain
    from tests._mocks import MockProvider

    provider = MockProvider(response_content=json.dumps(_brain()))
    call_brain(provider, _game(), "I force the vault door")
    system = provider.calls[0]["system"]
    assert "<fact_types>" in system
    assert "locked [place]" in system


class _Provider:
    def __init__(self, brain: dict[str, Any]) -> None:
        self.brain = brain
        self.prompts: list[str] = []

    @staticmethod
    def _json(payload: dict[str, Any]) -> AIResponse:
        return AIResponse(content=json.dumps(payload), usage={"input_tokens": 10, "output_tokens": 10})

    def create_message(self, spec: AICallSpec) -> AIResponse:
        props = spec.json_schema.get("properties", {}) if spec.json_schema else {}
        if "correction_source" in props:
            return self._json(
                {
                    "correction_source": "input_misread",
                    "corrected_input": "I force the vault door with my shoulder",
                    "narrator_guidance": "The player used force.",
                    "director_useful": False,
                    "state_ops": [],
                }
            )
        if "move" in props:
            return self._json(self.brain)
        if "new_npcs" in props:
            return self._json(
                {"new_npcs": [], "npc_renames": [], "npc_details": [], "deceased_npcs": [], "lore_npcs": []}
            )
        if "revelation_confirmed" in props:
            return self._json({"revelation_confirmed": False, "reasoning": "Absent."})
        self.prompts.append(str(spec.messages[-1]["content"]))
        return AIResponse(content="Dust drifts through the lamplight.", usage={"input_tokens": 10, "output_tokens": 10})


def _force(monkeypatch: pytest.MonkeyPatch, result: str, scene_roll: int = 10) -> None:
    from straightjacket.engine.game import turn
    from straightjacket.engine.mechanics import scene

    def _roll(stat_name: str, stat_value: int, move: str, momentum: int, adds: int) -> RollResult:
        return RollResult(
            d1=1,
            c1=4,
            c2=5,
            stat_name=stat_name,
            stat_value=stat_value,
            action_score=1 + stat_value,
            result=result,
            move=move,
            match=False,
        )

    monkeypatch.setattr(turn, "roll_action", _roll)
    monkeypatch.setattr(turn, "check_scene", lambda game: scene.check_scene(game, roll=scene_roll))


def test_the_turn_resolves_facts_at_the_place_it_moves_to(
    load_engine: None, stub_emotions: None, counted_fate: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.game import process_turn

    _force(monkeypatch, "MISS")
    provider = _Provider(_brain(location_change="Archive Vault"))
    game, _n, _r, _o, _d = process_turn(provider, _game(), "I force the vault door", _CONFIG)

    assert [(f.fact_type, f.location) for f in game.world.facts] == [("locked", "Archive Vault")]
    assert game.last_turn_snapshot is not None
    assert game.last_turn_snapshot.facts == game.world.facts
    assert '<fact about="Archive Vault" answer="yes">' in provider.prompts[-1]


def test_a_hit_clears_the_fact_but_the_narrator_still_gets_it(
    load_engine: None, stub_emotions: None, counted_fate: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.game import process_turn

    _force(monkeypatch, "STRONG_HIT")
    provider = _Provider(_brain())
    game, _n, _r, _o, _d = process_turn(provider, _game(), "I force the vault door", _CONFIG)

    assert game.world.facts == []
    assert "<facts>" in provider.prompts[-1]


def test_a_doublet_event_reaches_the_same_turn(
    load_engine: None, stub_emotions: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.game import process_turn
    from straightjacket.engine.mechanics import fate

    _force(monkeypatch, "MISS")
    original = fate.resolve_fate_chart
    monkeypatch.setattr(fate, "resolve_fate_chart", lambda odds, cf, question: original(odds, cf, question, roll=55))
    provider = _Provider(_brain())
    process_turn(provider, _game(), "I force the vault door", _CONFIG)

    assert "<random_event" in provider.prompts[-1]


def test_an_interrupt_event_is_shown_once(
    load_engine: None, stub_emotions: None, counted_fate: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.game import process_turn

    _force(monkeypatch, "MISS", scene_roll=2)
    provider = _Provider(_brain(undetermined_facts=[]))
    process_turn(provider, _game(), "I force the vault door", _CONFIG)

    prompt = provider.prompts[-1]
    assert prompt.count("<interrupt_scene") == 1
    assert "<random_event" not in prompt


def test_an_oracle_question_covered_by_a_fact_skips_the_oracle_roll(
    load_engine: None, stub_emotions: None, counted_fate: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.game import process_turn, turn
    from straightjacket.engine.prompt_loader import get_prompt

    _force(monkeypatch, "MISS")

    def _no_oracle(game: Any) -> str:
        raise AssertionError("the oracle table must not be rolled")

    monkeypatch.setattr(turn, "roll_oracle_answer", _no_oracle)
    brain = _brain(
        move="ask_the_oracle",
        stat="none",
        player_intent="Is anyone else in the library?",
        undetermined_facts=[{"fact_type": "occupied", "about": "here"}],
    )
    provider = _Provider(brain)
    process_turn(provider, _game(), "Is anyone else in the library?", _CONFIG)

    prompt = provider.prompts[-1]
    assert '<scene type="oracle"' in prompt
    assert "<facts>" in prompt
    assert get_prompt("task_oracle_facts") in prompt


def test_a_burn_keeps_the_facts_and_clears_them_on_the_better_result(
    load_engine: None, stub_emotions: None, counted_fate: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.game import process_momentum_burn, process_turn

    _force(monkeypatch, "MISS")
    provider = _Provider(_brain())
    game, _n, _r, offer, _d = process_turn(provider, _game(), "I force the vault door", _CONFIG)
    assert offer is not None
    assert [f.fact_type for f in game.world.facts] == ["locked"]

    game, _narration, _director = process_momentum_burn(provider, game, offer, _CONFIG)

    assert game.world.facts == []
    assert "<facts>" in provider.prompts[-1]
    assert counted_fate == ["locked:here"]


def test_a_correction_reuses_the_facts_of_the_turn(
    load_engine: None, stub_emotions: None, counted_fate: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import process_correction
    from straightjacket.engine.game import process_turn

    _force(monkeypatch, "MISS")
    provider = _Provider(_brain())
    game, _n, _r, _o, _d = process_turn(provider, _game(), "I force the vault door", _CONFIG)
    first = list(game.world.facts)

    game, _narration, _offer, _director = process_correction(provider, game, "I meant with force", _CONFIG)

    assert counted_fate == ["locked:here"]
    assert game.world.facts == first
    assert game.last_turn_snapshot is not None
    assert game.last_turn_snapshot.facts == first


def test_facts_survive_a_save_round_trip(load_engine: None) -> None:
    game = _game()
    game.world.facts = [_fact("locked"), _fact("alert", about="npc_2")]
    assert GameState.from_dict(game.to_dict()).world.facts == game.world.facts


def test_a_fact_type_with_an_unknown_subject_raises() -> None:
    from straightjacket.engine.engine_config import parse_engine_yaml
    from straightjacket.engine.engine_loader import _ENGINE_DIR
    from straightjacket.engine.yaml_merge import load_yaml_dir

    data = load_yaml_dir(_ENGINE_DIR, missing_dir_hint="The engine/ directory ships with the repo.")
    data["fact_resolution"]["types"]["locked"]["subject"] = "room"
    with pytest.raises(ValueError, match="subject"):
        parse_engine_yaml(data)
