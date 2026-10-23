import asyncio
from typing import Any

import pytest

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse
from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.models import (
    GameState,
    NarrationEntry,
)
from straightjacket.engine.ruleset.config import rules
from tests._creation import OPENING_TEXT, TurnProvider, brain_answer, force_result, library_game


@pytest.fixture
def forced_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    force_result(monkeypatch, "MISS")


def _turn_then_burn(provider: TurnProvider, game: GameState) -> tuple[GameState, str, Any]:
    from straightjacket.engine.game import process_momentum_burn, process_turn

    _narration, roll, offer, _director = process_turn(
        provider, game, "I slip past Mira into the archive vault", stream=None
    )
    assert roll is not None
    assert roll.result == "MISS"
    assert offer is not None
    assert offer.new_result == "STRONG_HIT"
    narration, director = process_momentum_burn(provider, game, offer)
    return game, narration, director


def test_burn_keeps_the_location_and_scene_count_of_the_turn(load_engine: None, forced_miss: None) -> None:
    game, _narration, _director = _turn_then_burn(TurnProvider(brain_answer()), library_game())

    assert game.world.current_location == "Archive Vault"
    assert game.narrative.scene_count == 2


def test_burn_writes_its_own_log_entries_and_leaves_the_previous_turn(load_engine: None, forced_miss: None) -> None:
    provider = TurnProvider(brain_answer())
    game, narration, _director = _turn_then_burn(provider, library_game())

    history = game.narrative.narration_history
    assert [h.narration for h in history] == [OPENING_TEXT, narration]
    log = game.narrative.session_log
    assert [entry.result for entry in log] == ["opening", "STRONG_HIT"]
    assert log[-1].scene == 2
    assert narration == provider.narrations[-1]
    assert "<momentum_burn>" in provider.prompts[-1]


def test_burn_keeps_the_track_the_turn_created(load_engine: None, forced_miss: None) -> None:
    brain = brain_answer(move="quest/swear_an_iron_vow", stat="heart", track_name="Recover the codex")
    game, _narration, _director = _turn_then_burn(TurnProvider(brain), library_game())

    vows = [t for t in game.progress_tracks if t.track_type == "vow"]
    assert [t.name for t in vows] == ["Keep the archive whole", "Recover the codex"]


def test_burn_updates_the_turn_snapshot(load_engine: None, forced_miss: None) -> None:

    game, narration, _director = _turn_then_burn(TurnProvider(brain_answer()), library_game())

    snap = game.last_turn_snapshot
    assert snap is not None
    assert snap.roll is not None
    assert snap.roll.result == "STRONG_HIT"
    assert snap.narration == narration
    assert snap.player_input == "I slip past Mira into the archive vault"
    assert game.resources.meters["momentum"] == rules().momentum.start + 1


def test_burn_runs_scene_end_bookkeeping_exactly_once(load_engine: None, forced_miss: None) -> None:
    from straightjacket.engine.game import process_turn

    reference = library_game()
    _n, _r, _o, _d = process_turn(
        TurnProvider(brain_answer()), reference, "I slip past Mira into the archive vault", stream=None
    )
    game, _narration, _director = _turn_then_burn(TurnProvider(brain_answer()), library_game())

    assert len(game.narrative.scene_intensity_history) == len(reference.narrative.scene_intensity_history)
    assert [c.weight for c in game.narrative.characters_list] == [c.weight for c in reference.narrative.characters_list]
    assert [t.weight for t in game.narrative.threads] == [t.weight for t in reference.narrative.threads]


def test_restore_reverts_changes_inside_the_story_lists(load_engine: None) -> None:
    game = library_game()
    snap = game.snapshot()
    game.narrative.threads[0].weight = 3
    game.narrative.threads[0].active = False
    game.narrative.characters_list[0].weight = 3

    game.restore(snap)

    assert game.narrative.threads[0].weight == 2
    assert game.narrative.threads[0].active is True
    assert game.narrative.characters_list[0].weight == 1


def test_a_burn_at_the_history_cap_keeps_the_earlier_entries(load_engine: None, forced_miss: None) -> None:
    import copy

    from straightjacket.engine.game import process_momentum_burn, process_turn
    from tests.elvira.elvira_bot.invariants import check_turn_replacement

    game = library_game()
    cap = gm().pacing.max_narration_history
    game.narrative.narration_history = [
        NarrationEntry(scene=n, prompt_summary=f"Scene {n}", narration=f"Earlier scene {n}.") for n in range(1, cap + 1)
    ]
    provider = TurnProvider(brain_answer())
    _n, _r, offer, _d = process_turn(provider, game, "I slip past Mira into the archive vault", stream=None)
    assert offer is not None
    before = copy.deepcopy(game)

    narration, _director = process_momentum_burn(provider, game, offer)

    assert check_turn_replacement(before, game, narration, 2, "momentum burn", keeps_location=True) == []


class _FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, msg: dict[str, Any]) -> None:
        self.sent.append(msg)


def test_new_player_input_withdraws_a_pending_burn_offer(
    load_engine: None, forced_miss: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.ai.provider_base import AIUnavailableError
    from straightjacket.engine.game import process_turn
    from straightjacket.web import handlers
    from straightjacket.web.session import new_session

    game = library_game()
    _n, _r, offer, _d = process_turn(TurnProvider(brain_answer()), game, "I slip into the vault", stream=None)
    session = new_session()
    session.game = game
    session.pending_burn = offer

    def failing_turn(provider: Any, g: Any, text: str, config: Any, stream: Any) -> Any:
        raise AIUnavailableError("narrator: test")

    monkeypatch.setattr(handlers, "process_turn", failing_turn)
    monkeypatch.setattr(handlers, "get_provider", lambda: None)

    asyncio.run(handlers.handle_player_input(session, _FakeWS(), {"text": "I walk away"}))

    assert session.pending_burn is None


class _FlakyNarrator(TurnProvider):
    def __init__(self, *brains: dict[str, Any]) -> None:
        super().__init__(*brains)
        self.narrator_down = False

    def create_message(self, spec: AICallSpec) -> AIResponse:
        if self.narrator_down and spec.log_role == "narrator":
            raise ConnectionError("narrator unreachable")
        return super().create_message(spec)


def _session(monkeypatch: pytest.MonkeyPatch, tmp_path: Any, provider: TurnProvider) -> Any:
    from straightjacket.engine.ruleset import move_outcome
    from straightjacket.web import handlers
    from straightjacket.web.session import new_session
    from tests._creation import fixed_roll

    for target in (
        "straightjacket.engine.config_loader.USERS_DIR",
        "straightjacket.engine.user_management.USERS_DIR",
    ):
        monkeypatch.setattr(target, tmp_path)
    monkeypatch.setattr(move_outcome, "roll_action", fixed_roll("MISS"))
    monkeypatch.setattr(handlers, "get_provider", lambda: provider)
    session = new_session()
    session.player = "Kael"
    session.take_game(library_game(), [])
    return session


def _play(session: Any, text: str) -> _FakeWS:
    from straightjacket.web import handlers

    ws = _FakeWS()
    asyncio.run(handlers.handle_player_input(session, ws, {"text": text}))
    return ws


def _dying(session: Any) -> None:
    from straightjacket.engine.ruleset.suffer import start_dying_clock

    game = session.game
    game.resources.meters["health"] = 0
    start_dying_clock(game)
    game.world.clocks[-1].filled = 1


def _dying_on_a_miss(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any, provider: TurnProvider
) -> tuple[Any, _FakeWS, TurnProvider]:
    session = _session(monkeypatch, tmp_path, provider)
    _dying(session)
    ws = _play(session, "I press on")
    assert session.game.end_reason == "death"
    return session, ws, provider


_HEAL = brain_answer(move="adventure/heal", stat="wits", player_intent="I bind my wounds", location_change=None)
_PRESS_ON = brain_answer(location_change=None)


def _types(ws: _FakeWS) -> list[str]:
    return [m["type"] for m in ws.sent]


def test_a_game_over_turn_offers_the_burn_before_it_announces_the_end(
    load_engine: None, forced_miss: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    from straightjacket.web import handlers

    session, ws, _provider = _dying_on_a_miss(monkeypatch, tmp_path, TurnProvider(_HEAL))

    assert [t for t in _types(ws) if t in ("burn_offer", "game_over")] == ["burn_offer"]
    assert len(session.game.campaign.predecessors) == 1

    asyncio.run(handlers.handle_burn_momentum(session, ws, {"accept": False}))

    assert _types(ws)[-2:] == ["game_over", "turn_complete"]
    assert (len(session.game.campaign.predecessors), session.game.campaign.pending_succession) == (1, True)


def test_a_burn_that_saves_the_character_leaves_no_predecessor(
    load_engine: None, forced_miss: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.persistence import load_game
    from straightjacket.web import handlers

    session, ws, _provider = _dying_on_a_miss(monkeypatch, tmp_path, TurnProvider(_HEAL))

    asyncio.run(handlers.handle_burn_momentum(session, ws, {"accept": True}))

    game = session.game
    assert (game.game_over, game.campaign.predecessors, game.campaign.pending_succession) == (False, [], False)
    assert "game_over" not in _types(ws)
    saved, _messages = load_game("Kael", eng().persistence.default_save_name)
    assert saved is not None
    assert saved.to_dict() == game.to_dict()


def test_a_burn_that_does_not_save_the_character_archives_them_once(
    load_engine: None, forced_miss: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    from straightjacket.web import handlers

    session, ws, _provider = _dying_on_a_miss(monkeypatch, tmp_path, TurnProvider(_PRESS_ON))

    asyncio.run(handlers.handle_burn_momentum(session, ws, {"accept": True}))

    game = session.game
    assert game.end_reason == "death"
    [record] = game.campaign.predecessors
    assert record.player_name == "Kael"
    assert game.campaign.pending_succession
    assert _types(ws)[-2:] == ["game_over", "turn_complete"]


def test_a_failed_burn_is_rolled_back_and_offered_again(
    load_engine: None, forced_miss: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    from straightjacket.web import handlers

    provider = _FlakyNarrator(_HEAL)
    session, _ws, _provider = _dying_on_a_miss(monkeypatch, tmp_path, provider)
    offer = session.pending_burn
    before = session.game.to_dict()
    provider.narrator_down = True
    ws = _FakeWS()

    asyncio.run(handlers.handle_burn_momentum(session, ws, {"accept": True}))

    assert _types(ws)[-2:] == ["error", "burn_offer"]
    assert session.pending_burn is offer
    assert session.game.to_dict() == before


def test_a_game_that_is_over_answers_input_and_corrections_with_what_stands(
    load_engine: None, forced_miss: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    from straightjacket.web import handlers

    session, _ws, provider = _dying_on_a_miss(monkeypatch, tmp_path, TurnProvider(_HEAL))
    before, calls = session.game.to_dict(), len(provider.calls)

    standing = _FakeWS()
    asyncio.run(handlers.handle_player_input(session, standing, {"text": "I stand up"}))
    asyncio.run(handlers.handle_correction(session, standing, {"text": "I meant to run"}))
    assert _types(standing) == ["burn_offer", "burn_offer"]

    asyncio.run(handlers.handle_burn_momentum(session, standing, {"accept": False}))
    ended = _FakeWS()
    asyncio.run(handlers.handle_player_input(session, ended, {"text": "I stand up"}))
    asyncio.run(handlers.handle_correction(session, ended, {"text": "I meant to run"}))
    assert _types(ended) == ["game_over", "game_over"]
    assert (session.game.to_dict(), len(provider.calls)) == (before, calls)


def test_a_reload_drops_a_standing_burn_and_shows_the_end_while_a_reconnect_offers_it_again(
    load_engine: None, forced_miss: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    from straightjacket.web import handlers, server

    session, _ws, _provider = _dying_on_a_miss(monkeypatch, tmp_path, TurnProvider(_HEAL))
    monkeypatch.setattr(server, "_session", session)

    reconnected = _FakeWS()
    asyncio.run(server._send_initial_state(reconnected))
    assert _types(reconnected)[-2:] == ["player_selected", "burn_offer"]

    reloaded = _FakeWS()
    asyncio.run(handlers.handle_select_player(session, reloaded, {"name": "Kael"}))
    assert _types(reloaded) == ["player_selected", "game_over"]
    assert session.pending_burn is None


def test_a_correction_that_replays_the_turn_into_death_prepares_the_succession_once(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    from straightjacket.web import handlers
    from tests._creation import force_result

    force_result(monkeypatch, "STRONG_HIT")
    session = _session(monkeypatch, tmp_path, TurnProvider(_HEAL, _PRESS_ON))
    _dying(session)
    _play(session, "I bind my wounds")
    assert not session.game.game_over
    ws = _FakeWS()

    asyncio.run(handlers.handle_correction(session, ws, {"text": "I meant to press on"}))

    assert session.game.end_reason == "death"
    assert (len(session.game.campaign.predecessors), session.game.campaign.pending_succession) == (1, True)
    assert _types(ws)[-2:] == ["burn_offer", "turn_complete"]

    asyncio.run(handlers.handle_burn_momentum(session, ws, {"accept": False}))

    assert _types(ws)[-2:] == ["game_over", "turn_complete"]
    assert len(session.game.campaign.predecessors) == 1


def test_a_failed_correction_leaves_the_burn_offer_standing(
    load_engine: None, forced_miss: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    from straightjacket.web import handlers

    provider = _FlakyNarrator(_PRESS_ON)
    session = _session(monkeypatch, tmp_path, provider)
    _play(session, "I slip into the vault")
    offer = session.pending_burn
    assert offer is not None
    provider.narrator_down = True
    ws = _FakeWS()

    asyncio.run(handlers.handle_correction(session, ws, {"text": "I meant to climb"}))

    assert _types(ws)[-2:] == ["error", "burn_offer"]
    assert session.pending_burn is offer


def test_retiring_withdraws_a_standing_burn_offer(
    load_engine: None, forced_miss: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    from straightjacket.web import handlers

    session = _session(monkeypatch, tmp_path, TurnProvider(_PRESS_ON))
    _play(session, "I slip into the vault")
    assert session.pending_burn is not None
    ws = _FakeWS()

    asyncio.run(handlers.handle_retire(session, ws, {}))

    assert (session.pending_burn, _types(ws)) == (None, ["game_over"])


def test_what_the_player_chose_between_a_turn_and_its_burn_or_correction_stays(
    load_engine: None, forced_miss: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    from straightjacket.web import handlers

    session = _session(monkeypatch, tmp_path, TurnProvider(_PRESS_ON))
    session.game.campaign.xp = 10
    _play(session, "I slip into the vault")
    ws = _FakeWS()
    asyncio.run(handlers.handle_advance_asset(session, ws, {"kind": "new", "asset_id": "cave_lion"}))
    asyncio.run(handlers.handle_dismiss_epilogue(session, ws, {}))

    asyncio.run(handlers.handle_burn_momentum(session, ws, {"accept": True}))
    asyncio.run(handlers.handle_correction(session, ws, {"text": "I meant to climb"}))

    campaign = session.game.campaign
    assert "cave_lion" in session.game.assets
    assert (campaign.xp_spent, campaign.epilogue_dismissed) == (3, True)
