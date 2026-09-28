import json
from typing import Any

import pytest

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse
from tests.test_momentum_burn import _CONFIG, _brain, _game


class _Provider:
    def __init__(self, *brains: dict[str, Any]) -> None:
        self.brains = list(brains)
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
                    "corrected_input": "I shoulder the vault door",
                    "narrator_guidance": "The player used force, not finesse.",
                    "director_useful": False,
                    "state_ops": [],
                }
            )
        if "move" in props:
            return self._json(self.brains.pop(0) if len(self.brains) > 1 else self.brains[0])
        if "new_npcs" in props:
            return self._json(
                {"new_npcs": [], "npc_renames": [], "npc_details": [], "deceased_npcs": [], "lore_npcs": []}
            )
        if "revelation_confirmed" in props:
            return self._json({"revelation_confirmed": False, "reasoning": "Absent."})
        text = f"Scene text number {len(self.prompts) + 1}. Dust drifts through the lamplight."
        self.prompts.append(str(spec.messages[-1]["content"]))
        return AIResponse(content=text, usage={"input_tokens": 10, "output_tokens": 10})


@pytest.fixture
def dice(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    from straightjacket.engine.game import turn
    from straightjacket.engine.mechanics.consequences import score_action_roll

    counts = {"rolls": 0, "scenes": 0, "scene_roll": 10}
    real_scene = turn.check_scene

    def _roll(stat_name: str, stat_value: int, move: str, momentum: int, adds: int) -> Any:
        counts["rolls"] += 1
        return score_action_roll(3, 4, 6, stat_name, stat_value, move, momentum, adds)

    def _scene(game: Any) -> Any:
        counts["scenes"] += 1
        return real_scene(game, roll=counts["scene_roll"])

    monkeypatch.setattr(turn, "roll_action", _roll)
    monkeypatch.setattr(turn, "check_scene", _scene)
    return counts


def _turn_then_correct(provider: _Provider) -> tuple[Any, Any, str, Any]:
    import copy

    from straightjacket.engine.correction import process_correction
    from straightjacket.engine.game import process_turn

    game, _n, _r, _o, _d = process_turn(provider, _game(), "I slip into the vault", _CONFIG)
    before = copy.deepcopy(game)
    game, narration, offer, _director = process_correction(provider, game, "I meant I use force", _CONFIG)
    return before, game, narration, offer


def test_a_misread_correction_keeps_the_dice_and_scores_the_new_stat(
    load_engine: None, stub_emotions: None, dice: dict[str, int]
) -> None:
    before, game, _narration, _offer = _turn_then_correct(_Provider(_brain(), _brain(stat="iron")))

    assert before.narrative.session_log[-1].result == "WEAK_HIT"
    assert game.narrative.session_log[-1].result == "MISS"
    snap = game.last_turn_snapshot
    assert snap is not None
    assert snap.roll is not None
    assert (snap.roll.d1, snap.roll.c1, snap.roll.c2, snap.roll.stat_name) == (3, 4, 6, "iron")
    assert dice["rolls"] == 1


def test_a_misread_correction_with_the_same_stat_keeps_its_result(
    load_engine: None, stub_emotions: None, dice: dict[str, int]
) -> None:
    _before, game, _narration, _offer = _turn_then_correct(_Provider(_brain(), _brain()))

    last = game.narrative.session_log[-1]
    assert (last.move, last.result) == ("adventure/face_danger", "WEAK_HIT")


def test_a_misread_correction_keeps_the_scene_and_carries_the_correction_to_the_narrator(
    load_engine: None, stub_emotions: None, dice: dict[str, int]
) -> None:
    dice["scene_roll"] = 2
    provider = _Provider(_brain(), _brain(stat="iron"))
    _turn_then_correct(provider)

    assert dice["scenes"] == 1
    assert "<interrupt_scene" in provider.prompts[-1]
    assert "<correction_context>" in provider.prompts[-1]


def test_a_corrected_miss_can_offer_a_burn(load_engine: None, stub_emotions: None, dice: dict[str, int]) -> None:
    _before, _game_after, _narration, offer = _turn_then_correct(_Provider(_brain(), _brain(stat="iron")))

    assert offer is not None
    assert offer.new_result == "WEAK_HIT"


def test_elvira_accepts_a_replayed_turn_and_a_burn(
    load_engine: None, stub_emotions: None, dice: dict[str, int]
) -> None:
    import copy

    from straightjacket.engine.game import process_momentum_burn
    from tests.elvira.elvira_bot.invariants import check_turn_replacement

    before, game, narration, offer = _turn_then_correct(_Provider(_brain(), _brain(stat="iron")))
    assert check_turn_replacement(before, game, narration, 1, "correction", keeps_location=False) == []

    assert offer is not None
    before_burn = copy.deepcopy(game)
    game, narration, _director = process_momentum_burn(_Provider(_brain(stat="iron")), game, offer, _CONFIG)
    assert check_turn_replacement(before_burn, game, narration, 1, "momentum burn", keeps_location=True) == []
