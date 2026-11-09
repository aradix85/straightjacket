from __future__ import annotations

import asyncio
import html
import json
import logging
import random as _random
import re
import time
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any
from unittest import mock

import uvicorn
import websockets

from straightjacket.engine.ai.api_client import check_configured_models, get_provider
from straightjacket.engine.config_loader import VERSION, cfg
from straightjacket.engine.models import GameState
from straightjacket.web import handlers
from straightjacket.web.server import app
from tests.elvira.elvira_bot.ai_helpers import (
    ask_bot,
    build_turn_context,
    configure_bot,
    get_persona,
)
from tests.elvira.elvira_bot.console import say
from tests.elvira.elvira_bot.coverage import Coverage
from tests.elvira.elvira_bot.creation import roll_character
from tests.elvira.elvira_bot.display import print_narration, print_state, print_summary
from tests.elvira.elvira_bot.models import ChapterRecord, TurnRecord
from tests.elvira.elvira_bot.recorder import record_turn
from tests.elvira.elvira_bot.runner import (
    SEPARATOR,
    SESSION_ENDINGS,
    RunState,
    _EventCapture,
    _norm,
    aggregate_token_stats,
    burn_stats,
    check_turn,
    decide_burn,
    is_correction_turn,
    new_session_log,
    session_settings,
    story_complete,
    write_logs,
)
from tests.elvira.elvira_bot.tokens import TokenMeter

if TYPE_CHECKING:
    from tests.elvira.elvira_bot.models import SessionLog
    from tests.elvira.elvira_bot.runner import SessionSettings


class WsClient:
    def __init__(self, url: str) -> None:
        self.url = url
        self.ws: Any = None
        self._buffer: list[dict[str, Any]] = []

    async def connect(self) -> None:
        self.ws = await websockets.connect(self.url)

    async def close(self) -> None:
        if self.ws:
            await self.ws.close()

    async def send(self, msg: dict[str, Any]) -> None:
        await self.ws.send(json.dumps(msg))

    async def recv(self) -> dict[str, Any]:
        if self._buffer:
            return self._buffer.pop(0)
        msg: dict[str, Any] = json.loads(await self.ws.recv())
        return msg

    async def recv_until(self, msg_type: str) -> dict[str, Any]:
        for i, buffered in enumerate(self._buffer):
            if buffered.get("type") == msg_type:
                return self._buffer.pop(i)
        while True:
            msg: dict[str, Any] = json.loads(await self.ws.recv())
            if msg.get("type") == msg_type:
                return msg
            self._buffer.append(msg)

    async def drain(self, quiet: float) -> list[dict[str, Any]]:
        msgs = list(self._buffer)
        self._buffer.clear()
        try:
            while True:
                async with asyncio.timeout(quiet):
                    raw = await self.ws.recv()
                msgs.append(json.loads(raw))
        except TimeoutError:
            pass
        return msgs

    async def collect_turn(self, until: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "narration": None,
            "replace_narration": None,
            "burn_offer": None,
            "error": None,
            "game_over": False,
            "story_complete": False,
            "epilogue": None,
            "chapter_started": None,
            "sentences": [],
            "other": [],
        }
        started = time.monotonic()
        deadline = asyncio.get_running_loop().time() + _TURN_SECONDS
        while True:
            try:
                async with asyncio.timeout_at(deadline):
                    msg = await self.recv()
            except TimeoutError:
                break
            t = msg.get("type", "")
            if t == "error":
                result["error"] = msg["text"]
                break
            _file_message(result, t, msg, started)
            if t == until:
                break
        return result

    async def get_debug_state(self) -> GameState | None:
        await self.send({"type": "debug_state"})
        async with asyncio.timeout(10):
            msg = await self.recv_until("debug_state")
        data = msg.get("data")
        if data is None:
            return None
        return GameState.from_dict(data)


_TURN_SECONDS = 180
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()
_KEPT_MESSAGES = frozenset({"narration", "replace_narration", "burn_offer", "epilogue", "chapter_started"})
_FLAG_MESSAGES = frozenset({"game_over", "story_complete"})
_IGNORED_MESSAGES = frozenset({"status", "scene_marker", "turn_complete"})


def _file_message(result: dict[str, Any], msg_type: str, msg: dict[str, Any], started: float) -> None:
    if msg_type == "narration_sentence":
        result["sentences"].append((time.monotonic() - started, msg["text"]))
    elif msg_type in _KEPT_MESSAGES:
        result[msg_type] = msg
    elif msg_type in _FLAG_MESSAGES:
        result[msg_type] = True
    elif msg_type not in _IGNORED_MESSAGES:
        result["other"].append(msg)


@dataclass
class _WsRun(RunState):
    client: WsClient


async def _start_server(port: int) -> Any:
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve())
    _BACKGROUND_TASKS.add(serve_task)
    serve_task.add_done_callback(_BACKGROUND_TASKS.discard)

    for _ in range(100):
        await asyncio.sleep(0.05)
        if server.started:
            return server
        if serve_task.done():
            msg = f"Server on port {port} stopped during startup: {serve_task.exception()}"
            raise RuntimeError(msg)
    msg = f"Server failed to start on port {port} within 5s"
    raise RuntimeError(msg)


async def run_ws_session(bot_cfg: dict[str, Any], *, auto_override: bool, turns_override: int | None) -> SessionLog:
    without_scenario = {**bot_cfg, "session": {**bot_cfg["session"], "scenario": ""}}
    settings = session_settings(without_scenario, auto_override=auto_override, turns_override=turns_override)

    check_configured_models()
    configure_bot(bot_cfg["ai"])
    provider = TokenMeter(get_provider())
    mock.patch.object(handlers, "get_provider", return_value=provider).start()
    persona = get_persona(settings.style)

    port = bot_cfg.get("ws_port", cfg().server.port)
    url = f"ws://127.0.0.1:{port}/ws"

    slog = new_session_log(bot_cfg, settings)
    events = _EventCapture(bot_cfg["logging"]["event_prefixes"])
    logging.getLogger("rpg_engine").addHandler(events)

    say(f"\n{SEPARATOR}")
    say(f"  Straightjacket — Elvira WebSocket Bot — {settings.style.upper()} mode")
    auto = "YES" if settings.auto_mode else "NO"
    say(f"  Auto: {auto} | Turns/ch: {settings.max_turns} | Chapters: {settings.max_chapters}")
    say(f"  Engine: v{VERSION} | Server: {url}")
    say(SEPARATOR)

    server = await _start_server(port)
    say(f"[SETUP] Server started on port {port}")
    client = await _connect(url)
    game, narration = await _open_game(client, settings)
    run = _WsRun(
        settings=settings,
        client=client,
        provider=provider,
        persona=persona,
        slog=slog,
        coverage=Coverage(),
        events=events,
        game=game,
        narration=narration,
        total_turns=0,
        prev_npcs=None,
    )
    await _play_chapters(run)
    await _finish(run)

    await client.close()
    server.should_exit = True
    await asyncio.sleep(0.5)
    return slog


async def _connect(url: str) -> WsClient:
    client = WsClient(url)
    try:
        await client.connect()
    except Exception as e:
        say(f"[ERROR] Cannot connect to {url}: {e}")
        raise SystemExit(1) from e
    await client.drain(quiet=3)
    return client


async def _open_game(client: WsClient, settings: SessionSettings) -> tuple[GameState, str]:
    msg = await _select_player(client, settings)
    if not msg.get("has_game"):
        narration = await _start_game(client, settings)
    else:
        narration = next(
            (m.get("content", "") for m in reversed(msg.get("messages", [])) if m.get("role") == "assistant"), ""
        )
        say("[SETUP] Loaded game, fetching state via debug endpoint")
    game = await client.get_debug_state()
    if not game:
        say("[ERROR] Could not get game state")
        raise SystemExit(1)
    return game, narration


async def _select_player(client: WsClient, settings: SessionSettings) -> dict[str, Any]:
    await client.send({"type": "create_player", "name": settings.username})
    async with asyncio.timeout(10):
        msg = await client.recv_until("player_selected")
    say(f"[SETUP] Player: {settings.username}, has_game: {msg.get('has_game')}")
    if not settings.clean_before or settings.game_cfg["load_existing"]:
        return msg
    if msg.get("has_game"):
        await client.send({"type": "delete_save", "name": "autosave"})
        await client.drain(quiet=2)
    await client.send({"type": "delete_save", "name": settings.save_out})
    await client.drain(quiet=2)
    await client.send({"type": "select_player", "name": settings.username})
    async with asyncio.timeout(10):
        msg = await client.recv_until("player_selected")
    say(f"[CLEAN] Deleted previous saves, has_game: {msg.get('has_game')}")
    return msg


async def _start_game(client: WsClient, settings: SessionSettings) -> str:
    creation_data = roll_character(settings.game_cfg["setting_id"], settings.game_cfg)
    await client.send({"type": "start_game", "creation_data": creation_data})
    turn_data = await client.collect_turn("narration")
    if turn_data["error"]:
        say(f"[ERROR] start_game: {turn_data['error']}")
        raise SystemExit(1)
    narration: str = (turn_data["narration"] or {}).get("text", "")
    say("[SETUP] Game started")
    print_narration(narration, full=settings.print_full)
    return narration


async def _play_chapters(run: _WsRun) -> None:
    for chapter_idx in range(run.settings.max_chapters):
        ch_rec = await _play_chapter(run, chapter_idx)
        run.slog.chapters.append(ch_rec)
        if ch_rec.ended_reason in SESSION_ENDINGS or not story_complete(run.game):
            return
        if await _chapter_transition(run, chapter_idx):
            return


async def _play_chapter(run: _WsRun, chapter_idx: int) -> ChapterRecord:
    ch_rec = ChapterRecord(chapter=run.game.campaign.chapter_number)
    chapter_start = run.total_turns
    if chapter_idx > 0:
        say(f"\n{SEPARATOR}\n  CHAPTER {ch_rec.chapter}\n{SEPARATOR}")
    ch_rec.ended_reason = await _play_chapter_turns(run)
    ch_rec.turns_played = run.total_turns - chapter_start
    return ch_rec


async def _play_chapter_turns(run: _WsRun) -> str:
    for _ in range(run.settings.max_turns):
        rec = await _play_next_turn(run)
        if rec.stream_complete:
            run.coverage.hit("stream_complete")
            if not rec.stream_matches:
                run.slog.stream_issues.append(f"Turn {run.total_turns}: streamed text differs from the final narration")
        if run.total_turns == 1 and not rec.error:
            await _probe_queries(run.client, run.slog)
        if not await _fetch_state(run, rec):
            return "engine_error"
        await _keep_turn(run, rec)
        if run.game.game_over:
            return "game_over"
        if story_complete(run.game):
            return "story_complete"
    return "max_turns_reached"


async def _play_next_turn(run: _WsRun) -> TurnRecord:
    run.total_turns += 1
    turn = run.total_turns
    say(f"\n{SEPARATOR}\n  TURN {turn}/{run.settings.planned_turns}\n{SEPARATOR}")
    if is_correction_turn(turn, run.game):
        run.narration, rec = await _play_correction(run.client, run.game, turn, run.slog)
    else:
        run.narration, rec = await _play_turn(run, turn)
    return rec


async def _fetch_state(run: _WsRun, rec: TurnRecord) -> bool:
    if rec.error:
        run.slog.turns.append(rec)
        return False
    game = await run.client.get_debug_state()
    if not game:
        say("[ERROR] Lost game state")
        rec.error = "debug_state returned None"
        run.slog.turns.append(rec)
        return False
    run.game = game
    return True


async def _keep_turn(run: _WsRun, rec: TurnRecord) -> None:
    s, game, turn = run.settings, run.game, run.total_turns
    full_rec = replace(
        record_turn(game, turn, rec.action, run.narration, None),
        token_usage=run.provider.drain(),
        is_correction=rec.is_correction,
        burn_offered=rec.burn_offered,
        burn_taken=rec.burn_taken,
        burn_error=rec.burn_error,
        turn_secs=rec.turn_secs,
        stream_sentences=rec.stream_sentences,
        stream_first_sentence_secs=rec.stream_first_sentence_secs,
        stream_complete=rec.stream_complete,
        stream_matches=rec.stream_matches,
    )
    check_turn(game, run.narration, turn, run.prev_npcs, do_invariants=s.do_invariants, slog=run.slog, rec=full_rec)
    run.prev_npcs = list(full_rec.npcs)
    run.slog.turns.append(full_rec)
    print_state(game)
    if turn % s.save_every == 0:
        await run.client.send({"type": "save", "name": s.save_out})
        await run.client.drain(quiet=2)
        say(f"  [SAVE] Saved to '{s.save_out}'")


async def _finish(run: _WsRun) -> None:
    slog, coverage, s = run.slog, run.coverage, run.settings
    slog.total_turns = run.total_turns
    if slog.ended_reason == "unknown":
        slog.ended_reason = slog.chapters[-1].ended_reason if slog.chapters else "complete"
    slog.burn_stats = burn_stats(slog)
    slog.token_summary = aggregate_token_stats(slog)

    print_summary(slog, run.game)

    await run.client.send({"type": "save", "name": s.save_out})
    await run.client.drain(quiet=2)

    coverage.hit("burn_offered", slog.burn_stats["offered"])
    coverage.hit("burn_taken", slog.burn_stats["taken"])
    coverage.hit("correction", len(slog.correction_tests))
    logging.getLogger("rpg_engine").removeHandler(run.events)
    slog.engine_warnings = list(run.events.warnings)
    slog.coverage = coverage.summary()
    write_logs(slog, coverage, s)


async def _play_turn(run: _WsRun, turn: int) -> tuple[str, TurnRecord]:
    client, game, narration = run.client, run.game, run.narration
    context = build_turn_context(game, narration, turn)
    try:
        action = ask_bot(run.persona, context, max_tokens=500)
    except Exception as e:
        say(f"[ERROR] Bot decision failed: {e}")
        return narration, TurnRecord(turn=turn, error=str(e))

    say(f"\n  [PLAYER] {action}")
    started = time.monotonic()
    await client.send({"type": "player_input", "text": action})
    td = await client.collect_turn("turn_complete")

    if td["error"]:
        say(f"  [ERROR] {td['error']}")
        return narration, TurnRecord(turn=turn, action=action, error=td["error"])

    new_narration = (td["narration"] or {}).get("text", "")
    print_narration(new_narration, full=run.settings.print_full)

    rec = TurnRecord(turn=turn, chapter=game.campaign.chapter_number, action=action)
    rec.turn_secs = round(time.monotonic() - started, 1)
    sentences = td["sentences"]
    rec.stream_sentences = len(sentences)
    rec.stream_first_sentence_secs = round(sentences[0][0], 1) if sentences else None
    rec.stream_complete = bool((td["narration"] or {}).get("stream_complete"))
    rec.stream_matches = _norm(" ".join(text for _, text in sentences)) == _norm(_plain(new_narration))

    if td["burn_offer"]:
        await _handle_burn(run, td["burn_offer"], rec)

    return new_narration, rec


async def _play_correction(client: WsClient, game: GameState, turn: int, slog: SessionLog) -> tuple[str, TurnRecord]:
    corrections = [
        "I didn't mean to do that — I wanted to just observe, not act",
        "That's not what I said — I was asking a question, not making a statement",
        "I wanted to talk to them, not confront them",
        "I was being cautious, not aggressive",
    ]
    text = _random.choice(corrections)
    say(f"  [CORRECTION TEST] ## {text}")

    await client.send({"type": "correction", "text": text})
    td = await client.collect_turn("turn_complete")

    rec = TurnRecord(turn=turn, chapter=game.campaign.chapter_number, action=f"## {text}", is_correction=True)

    if td["error"]:
        rec.error = f"correction: {td['error']}"
        say(f"  [CORRECTION] Failed: {td['error']}")
        slog.correction_tests.append({"turn": turn, "correction": text, "success": False, "error": td["error"]})
        return "", rec

    narration = (td["replace_narration"] or {}).get("text", "")
    print_narration(narration, full=False)
    slog.correction_tests.append({"turn": turn, "correction": text, "success": True})
    say("  [CORRECTION TEST] Completed")
    return narration, rec


async def _handle_burn(run: _WsRun, burn_offer: dict[str, Any], rec: TurnRecord) -> None:
    client = run.client
    current = burn_offer["current"]
    upgrade = burn_offer["upgrade"]
    cost = burn_offer["cost"]

    should_burn = decide_burn(run.settings, run.game, current, upgrade)

    rec.burn_offered = upgrade
    rec.burn_taken = should_burn
    say(f"  [BURN] {current} → {upgrade} (cost {cost}) | {'BURN' if should_burn else 'skip'}")

    await client.send({"type": "burn_momentum", "accept": should_burn})
    td = await client.collect_turn("turn_complete")
    if td["error"]:
        rec.burn_error = td["error"]
        say(f"  [BURN] Failed: {td['error']}")
        async with asyncio.timeout(120):
            await client.recv_until("burn_offer")
        await client.send({"type": "burn_momentum", "accept": False})
        await client.collect_turn("turn_complete")
    elif td["replace_narration"]:
        say("  [BURN] Re-narrated")


async def _chapter_transition(run: _WsRun, chapter_idx: int) -> bool:
    client, slog = run.client, run.slog
    say(f"\n{SEPARATOR}\n  GENERATING EPILOGUE\n{SEPARATOR}")
    await client.send({"type": "generate_epilogue"})
    td = await client.collect_turn("epilogue")
    if td["error"]:
        say(f"  [EPILOGUE] Failed: {td['error']}")
        slog.ended_reason = f"epilogue_error: {td['error']}"
        return True
    if td["epilogue"]:
        print_narration(td["epilogue"].get("text", ""), full=True)

    if chapter_idx + 1 >= run.settings.max_chapters:
        slog.ended_reason = "max_chapters_reached"
        return True

    say(f"\n{SEPARATOR}\n  STARTING NEW CHAPTER\n{SEPARATOR}")
    await client.send({"type": "new_chapter"})
    td = await client.collect_turn("chapter_started")
    if td["error"]:
        say(f"  [CHAPTER] Failed: {td['error']}")
        slog.ended_reason = f"chapter_error: {td['error']}"
        return True

    ch_msg = td["chapter_started"]
    run.narration = ch_msg.get("narration", "") if ch_msg else ""
    print_narration(run.narration, full=run.settings.print_full)

    new_game = await client.get_debug_state()
    if new_game is None:
        return True
    run.game = new_game
    return False


def _plain(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]*>", "", fragment))


async def _probe_queries(client: WsClient, slog: SessionLog) -> None:
    for query in ("status_query", "tracks_query", "threats_query"):
        await client.send({"type": query})
        async with asyncio.timeout(30):
            answer = await client.recv_until("status")
        if not str(answer.get("text", "")).strip():
            slog.query_issues.append(f"{query}: empty answer")
    await client.send({"type": "recap"})
    while True:
        async with asyncio.timeout(180):
            msg = await client.recv()
        if msg.get("type") == "recap":
            if not str(msg.get("text", "")).strip():
                slog.query_issues.append("recap: empty answer")
            return
        if msg.get("type") == "error":
            slog.query_issues.append(f"recap: {msg.get('text')}")
            return
