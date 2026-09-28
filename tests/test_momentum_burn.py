import asyncio
import json
from typing import Any

import pytest

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse
from straightjacket.engine.models import (
    CharacterListEntry,
    EngineConfig,
    GameState,
    NarrationEntry,
    RollResult,
    SceneLogEntry,
    ThreadEntry,
)
from tests._helpers import make_npc

_CONFIG = EngineConfig(narration_lang="English")


def _brain(**overrides: Any) -> dict[str, Any]:
    brain: dict[str, Any] = {
        "type": "action",
        "move": "adventure/face_danger",
        "stat": "wits",
        "approach": "quietly",
        "target_npc": None,
        "dialog_only": False,
        "player_intent": "I slip past Mira into the archive vault",
        "world_addition": None,
        "location_change": "Archive Vault",
        "track_name": "Reach the vault",
        "track_rank": "dangerous",
        "target_track": None,
        "bonus_id": None,
        "undetermined_facts": [],
        "boasts": [],
    }
    brain.update(overrides)
    return brain


class _Provider:
    def __init__(self, brain: dict[str, Any]) -> None:
        self.brain = brain
        self.narrations: list[str] = []
        self.prompts: list[str] = []

    @staticmethod
    def _json(payload: dict[str, Any]) -> AIResponse:
        return AIResponse(content=json.dumps(payload), usage={"input_tokens": 10, "output_tokens": 10})

    def create_message(self, spec: AICallSpec) -> AIResponse:
        props = spec.json_schema.get("properties", {}) if spec.json_schema else {}
        if "move" in props:
            return self._json(self.brain)
        if "new_npcs" in props:
            return self._json(
                {"new_npcs": [], "npc_renames": [], "npc_details": [], "deceased_npcs": [], "lore_npcs": []}
            )
        if "revelation_confirmed" in props:
            return self._json({"revelation_confirmed": False, "reasoning": "Absent."})
        text = f"Scene text number {len(self.narrations) + 1}. Dust drifts through the lamplight."
        self.narrations.append(text)
        self.prompts.append(str(spec.messages[-1]["content"]))
        return AIResponse(content=text, usage={"input_tokens": 10, "output_tokens": 10})


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
    game.npcs = [make_npc(id="npc_1", name="Mira", disposition="friendly", description="An archivist.")]
    game.narrative.scene_count = 3
    game.narrative.narration_history = [
        NarrationEntry(scene=3, prompt_summary="Opening", narration="The library is cold and silent.")
    ]
    game.narrative.session_log = [
        SceneLogEntry(scene=3, scene_type="expected", summary="Opening", move="opening", result="opening")
    ]
    game.narrative.threads = [
        ThreadEntry(id="thread_codex", name="Find the lost codex", thread_type="vow", source="vow", weight=2)
    ]
    game.narrative.characters_list = [CharacterListEntry(id="npc_1", name="Mira", entry_type="npc", weight=1)]
    return game


@pytest.fixture
def forced_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.game import turn
    from straightjacket.engine.mechanics.scene import SceneSetup

    def _roll(stat_name: str, stat_value: int, move: str, momentum: int, adds: int) -> RollResult:
        return RollResult(
            d1=1,
            c1=4,
            c2=5,
            stat_name=stat_name,
            stat_value=stat_value,
            action_score=1 + stat_value,
            result="MISS",
            move=move,
            match=False,
        )

    monkeypatch.setattr(turn, "roll_action", _roll)
    monkeypatch.setattr(turn, "check_scene", lambda _game: SceneSetup(scene_type="expected", chaos_roll=10))


def _turn_then_burn(provider: _Provider, game: GameState) -> tuple[GameState, str, Any]:
    from straightjacket.engine.game import process_momentum_burn, process_turn

    game, _narration, roll, offer, _director = process_turn(
        provider, game, "I slip past Mira into the archive vault", _CONFIG
    )
    assert roll is not None
    assert roll.result == "MISS"
    assert offer is not None
    assert offer.new_result == "STRONG_HIT"
    return process_momentum_burn(provider, game, offer, _CONFIG)


def test_burn_keeps_the_location_and_scene_count_of_the_turn(
    load_engine: None, stub_emotions: None, forced_miss: None
) -> None:
    game, _narration, _director = _turn_then_burn(_Provider(_brain()), _game())

    assert game.world.current_location == "Archive Vault"
    assert game.narrative.scene_count == 4


def test_burn_writes_its_own_log_entries_and_leaves_the_previous_turn(
    load_engine: None, stub_emotions: None, forced_miss: None
) -> None:
    provider = _Provider(_brain())
    game, narration, _director = _turn_then_burn(provider, _game())

    history = game.narrative.narration_history
    assert [h.narration for h in history] == ["The library is cold and silent.", narration]
    log = game.narrative.session_log
    assert [entry.result for entry in log] == ["opening", "STRONG_HIT"]
    assert log[-1].scene == 4
    assert narration == provider.narrations[-1]
    assert "<momentum_burn>" in provider.prompts[-1]


def test_burn_keeps_the_track_the_turn_created(load_engine: None, stub_emotions: None, forced_miss: None) -> None:
    brain = _brain(move="quest/swear_an_iron_vow", stat="heart", track_name="Recover the codex")
    game, _narration, _director = _turn_then_burn(_Provider(brain), _game())

    vows = [t for t in game.progress_tracks if t.track_type == "vow"]
    assert [t.name for t in vows] == ["Recover the codex"]


def test_burn_updates_the_turn_snapshot(load_engine: None, stub_emotions: None, forced_miss: None) -> None:
    from straightjacket.engine.engine_loader import eng

    game, narration, _director = _turn_then_burn(_Provider(_brain()), _game())

    snap = game.last_turn_snapshot
    assert snap is not None
    assert snap.roll is not None
    assert snap.roll.result == "STRONG_HIT"
    assert snap.narration == narration
    assert snap.player_input == "I slip past Mira into the archive vault"
    assert game.resources.momentum == eng().momentum.start + 1


def test_burn_runs_scene_end_bookkeeping_exactly_once(
    load_engine: None, stub_emotions: None, forced_miss: None
) -> None:
    from straightjacket.engine.game import process_turn

    reference, _n, _r, _o, _d = process_turn(
        _Provider(_brain()), _game(), "I slip past Mira into the archive vault", _CONFIG
    )
    game, _narration, _director = _turn_then_burn(_Provider(_brain()), _game())

    assert len(game.narrative.scene_intensity_history) == len(reference.narrative.scene_intensity_history)
    assert [c.weight for c in game.narrative.characters_list] == [c.weight for c in reference.narrative.characters_list]
    assert [t.weight for t in game.narrative.threads] == [t.weight for t in reference.narrative.threads]


def test_restore_reverts_changes_inside_the_story_lists(load_engine: None) -> None:
    game = _game()
    snap = game.snapshot()
    game.narrative.threads[0].weight = 3
    game.narrative.threads[0].active = False
    game.narrative.characters_list[0].weight = 3

    game.restore(snap)

    assert game.narrative.threads[0].weight == 2
    assert game.narrative.threads[0].active is True
    assert game.narrative.characters_list[0].weight == 1


def test_a_burn_at_the_history_cap_keeps_the_earlier_entries(
    load_engine: None, stub_emotions: None, forced_miss: None
) -> None:
    import copy

    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.game import process_momentum_burn, process_turn
    from tests.elvira.elvira_bot.invariants import check_turn_replacement

    game = _game()
    cap = eng().pacing.max_narration_history
    game.narrative.narration_history = [
        NarrationEntry(scene=n, prompt_summary=f"Scene {n}", narration=f"Earlier scene {n}.") for n in range(1, cap + 1)
    ]
    provider = _Provider(_brain())
    game, _n, _r, offer, _d = process_turn(provider, game, "I slip past Mira into the archive vault", _CONFIG)
    assert offer is not None
    before = copy.deepcopy(game)

    game, narration, _director = process_momentum_burn(provider, game, offer, _CONFIG)

    assert check_turn_replacement(before, game, narration, 4, "momentum burn", keeps_location=True) == []


class _FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, msg: dict[str, Any]) -> None:
        self.sent.append(msg)


def test_new_player_input_withdraws_a_pending_burn_offer(
    load_engine: None, stub_emotions: None, forced_miss: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.ai.provider_base import AIUnavailableError
    from straightjacket.engine.game import process_turn
    from straightjacket.web import handlers
    from straightjacket.web.session import Session

    game, _n, _r, offer, _d = process_turn(_Provider(_brain()), _game(), "I slip into the vault", _CONFIG)
    session = Session()
    session.game = game
    session.pending_burn = offer

    def failing_turn(provider: Any, g: Any, text: str, config: Any, stream: Any) -> Any:
        raise AIUnavailableError("narrator: test")

    monkeypatch.setattr(handlers, "process_turn", failing_turn)
    monkeypatch.setattr(handlers, "get_provider", lambda: None)
    monkeypatch.setattr(handlers, "_narration_stream", lambda _ws, _game: (None, []))

    asyncio.run(handlers.handle_player_input(session, _FakeWS(), {"text": "I walk away"}))

    assert session.pending_burn is None
