#!/usr/bin/env python3
"""Elvira WebSocket runner: plays the game through the WebSocket server.

Same AI behavior as runner.py (personas, action generation, burn decisions),
but communicates via the WebSocket protocol instead of calling the engine
directly. This tests the full stack: WebSocket → handlers → engine → serializers.

Starts the Starlette server in-process, no separate terminal needed.
After each turn, requests debug_state to get the full GameState for
invariant checks, quality checks, and session recording.

Usage:
    python elvira/elvira.py --ws
    python elvira/elvira.py --ws --auto --turns 10
"""

from __future__ import annotations

import asyncio
import json
import random as _random
from datetime import datetime
from pathlib import Path
from typing import Any

import websockets

from straightjacket.engine.config_loader import VERSION, cfg
from straightjacket.engine.models import GameState

from .ai_helpers import ask_bot, build_turn_context, decide_burn_momentum, get_persona
from .creation import roll_character
from .invariants import assert_game_state
from .models import ChapterRecord, NpcSnapshot, RollRecord, SessionLog, TurnRecord
from .quality_checks import (
    check_chapter_continuity,
    check_narration_quality,
    check_npc_spatial_consistency,
)
from .recorder import record_turn

_HERE = Path(__file__).resolve().parent.parent
SEPARATOR = "=" * 62
CORRECTION_TEST_INTERVAL = 8


# ── WebSocket client ──────────────────────────────────────────

class WsClient:
    """Typed WebSocket client with message buffering."""

    def __init__(self, url: str):
        self.url = url
        self.ws: Any = None
        self._buffer: list[dict] = []

    async def connect(self) -> None:
        self.ws = await websockets.connect(self.url)

    async def close(self) -> None:
        if self.ws:
            await self.ws.close()

    async def send(self, msg: dict) -> None:
        await self.ws.send(json.dumps(msg))

    async def recv(self, timeout: float = 120) -> dict:
        """Receive one JSON message."""
        if self._buffer:
            return self._buffer.pop(0)
        raw = await asyncio.wait_for(self.ws.recv(), timeout=timeout)
        return json.loads(raw)

    async def recv_until(self, msg_type: str, timeout: float = 120) -> dict:
        """Receive until a message of the given type arrives. Buffer others."""
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise TimeoutError(f"Timed out waiting for {msg_type}")
            msg = await self.recv(timeout=remaining)
            if msg.get("type") == msg_type:
                return msg
            self._buffer.append(msg)

    async def drain(self, timeout: float = 2.0) -> list[dict]:
        """Drain all pending messages."""
        msgs = list(self._buffer)
        self._buffer.clear()
        try:
            while True:
                raw = await asyncio.wait_for(self.ws.recv(), timeout=timeout)
                msgs.append(json.loads(raw))
        except TimeoutError:
            pass
        return msgs

    async def collect_turn(self, timeout: float = 180) -> dict[str, Any]:
        """Collect all messages from a turn into a typed dict.

        Reads until 'state' message arrives (the server always sends state last).
        Returns a dict with keys for each message type seen, making downstream
        code explicit about what it reads instead of searching a list.
        """
        result: dict[str, Any] = {
            "narration": None, "replace_narration": None, "roll": None,
            "burn_offer": None, "state": None, "error": None,
            "game_over": False, "story_complete": False, "epilogue": None,
            "chapter_started": None, "other": [],
        }
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                msg = await self.recv(timeout=min(remaining, 5))
            except TimeoutError:
                break
            t = msg.get("type", "")
            if t == "narration":
                result["narration"] = msg
            elif t == "replace_narration":
                result["replace_narration"] = msg
            elif t == "roll":
                result["roll"] = msg.get("data")
            elif t == "burn_offer":
                result["burn_offer"] = msg
            elif t == "state":
                result["state"] = msg.get("data")
                break  # state is always last in the turn sequence
            elif t == "error":
                result["error"] = msg.get("text", "Unknown error")
                break
            elif t == "game_over":
                result["game_over"] = True
            elif t == "story_complete":
                result["story_complete"] = True
            elif t == "epilogue":
                result["epilogue"] = msg
            elif t == "chapter_started":
                result["chapter_started"] = msg
            elif t == "status":
                pass  # progress indicator, ignore
            elif t == "scene_marker":
                pass
            else:
                result["other"].append(msg)
        return result

    async def get_debug_state(self) -> GameState | None:
        """Request and deserialize full GameState from server."""
        await self.send({"type": "debug_state"})
        msg = await self.recv_until("debug_state", timeout=10)
        data = msg.get("data")
        if data is None:
            return None
        return GameState.from_dict(data)


# ── Embedded server ───────────────────────────────────────────

async def _start_server(port: int) -> Any:
    """Start the Starlette server as a background task. Returns the server."""
    import uvicorn
    from straightjacket.web.server import app
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    asyncio.create_task(server.serve())
    await asyncio.sleep(2)  # give it time to bind
    return server


# ── Main session ──────────────────────────────────────────────

async def run_ws_session(bot_cfg: dict, auto_override: bool = False,
                         turns_override: int | None = None) -> SessionLog:
    """Main session loop over WebSocket. Starts server in-process."""
    auto_mode = auto_override or bot_cfg.get("auto_mode", False)
    username = bot_cfg["username"]
    game_cfg = bot_cfg.get("game", {})
    session_cfg = bot_cfg.get("session", {})
    behavior = bot_cfg.get("bot_behavior", {})
    log_cfg = bot_cfg.get("logging", {})

    max_chapters = session_cfg.get("max_chapters", 1)
    max_turns = turns_override or session_cfg.get("max_turns", 20)
    save_every = session_cfg.get("save_every_n_turns", 5)
    save_out = session_cfg.get("save_name_output", "elvira")
    style = behavior.get("style", "balanced")
    burn_setting = behavior.get("burn_momentum", "auto")
    log_file = Path(log_cfg.get("log_file", "elvira_session.json"))
    print_full = log_cfg.get("print_full_narration", False)
    print_rolls = log_cfg.get("print_roll_details", True)
    do_invariants = log_cfg.get("assert_state_invariants", True)
    full_debug = log_cfg.get("full_debug_log", False)

    from straightjacket.engine.ai.api_client import get_provider
    provider = get_provider()
    persona = get_persona(style)

    port = bot_cfg.get("ws_port", cfg().server.port)
    url = f"ws://127.0.0.1:{port}/ws"

    slog = SessionLog(
        started_at=datetime.now().isoformat(),
        config=bot_cfg,
        engine_version=VERSION,
        auto_mode=auto_mode,
        style=style,
        max_chapters=max_chapters,
    )

    print(f"\n{SEPARATOR}")
    print(f"  Straightjacket — Elvira WebSocket Bot — {style.upper()} mode")
    print(f"  Auto: {'YES' if auto_mode else 'NO'} | Turns/ch: {max_turns} | "
          f"Chapters: {max_chapters}")
    print(f"  Engine: v{VERSION} | Server: {url}")
    print(SEPARATOR)

    # Start embedded server
    server = await _start_server(port)
    print(f"[SETUP] Server started on port {port}")

    client = WsClient(url)
    try:
        await client.connect()
    except Exception as e:
        print(f"[ERROR] Cannot connect to {url}: {e}")
        raise SystemExit(1) from e

    await client.drain(timeout=3)

    # ── Create/select player ──────────────────────────────────
    clean_before = session_cfg.get("clean_before_run", True)
    await client.send({"type": "create_player", "name": username})
    msg = await client.recv_until("player_selected", timeout=10)
    print(f"[SETUP] Player: {username}, has_game: {msg.get('has_game')}")

    # Clean old saves if starting fresh
    if clean_before and not game_cfg.get("load_existing"):
        if msg.get("has_game"):
            await client.send({"type": "delete_save", "name": "autosave"})
            await client.drain(timeout=2)
        await client.send({"type": "delete_save", "name": save_out})
        await client.drain(timeout=2)
        # Re-select player to get creation_options instead of stale game
        await client.send({"type": "select_player", "name": username})
        msg = await client.recv_until("player_selected", timeout=10)
        print(f"[CLEAN] Deleted previous saves, has_game: {msg.get('has_game')}")

    # ── Start game ────────────────────────────────────────────
    if not msg.get("has_game"):
        setting_id = game_cfg.get("setting_id", "starforged")
        if auto_mode:
            from straightjacket.engine.datasworn.settings import list_packages
            available = [s for s in list_packages() if s != "delve"] or ["starforged"]
            setting_id = _random.choice(available)

        creation_data = roll_character(setting_id, game_cfg)
        slog.creation_data = creation_data

        await client.send({"type": "start_game", "creation_data": creation_data})
        turn_data = await client.collect_turn(timeout=180)

        if turn_data["error"]:
            print(f"[ERROR] start_game: {turn_data['error']}")
            raise SystemExit(1)

        narration = (turn_data["narration"] or {}).get("text", "")
        print("[SETUP] Game started")
        _print_narration(narration, print_full)
    else:
        messages = msg.get("messages", [])
        narration = ""
        for m in reversed(messages):
            if m.get("role") == "assistant":
                narration = m.get("content", "")
                break
        state = msg.get("state", {})
        print(f"[SETUP] Loaded: {state.get('player_name', '?')} at {state.get('location', '?')}")

    game = await client.get_debug_state()
    if not game:
        print("[ERROR] Could not get game state")
        raise SystemExit(1)

    slog.character = game.player_name
    slog.location_start = game.world.current_location
    slog.opening_narration = narration

    prev_npcs: list[NpcSnapshot] | None = None
    burns_offered = burns_taken = burns_failed = 0
    total_turns = 0
    session_ended = False

    # ── Chapter loop ──────────────────────────────────────────
    for chapter_idx in range(max_chapters):
        chapter_start = total_turns
        ch_rec = ChapterRecord(chapter=game.campaign.chapter_number,
                               started_at_turn=total_turns + 1)

        if chapter_idx > 0:
            print(f"\n{SEPARATOR}\n  CHAPTER {game.campaign.chapter_number}\n{SEPARATOR}")

        for _ in range(max_turns):
            total_turns += 1
            print(f"\n{SEPARATOR}\n  TURN {total_turns}/{max_chapters * max_turns}\n{SEPARATOR}")

            is_correction = (total_turns > 1
                             and total_turns % CORRECTION_TEST_INTERVAL == 0)

            if is_correction:
                narration, rec = await _play_correction(
                    client, provider, game, total_turns, slog)
            else:
                narration, rec, burn = await _play_turn(
                    client, provider, game, narration, total_turns, persona,
                    style, burn_setting, print_full, print_rolls)
                if burn:
                    burns_offered += 1
                    if burn["taken"]:
                        burns_taken += 1
                    if burn.get("error"):
                        burns_failed += 1

            if rec.error:
                session_ended = True
                slog.turns.append(rec)
                break

            # Refresh full state for checks
            game = await client.get_debug_state()
            if not game:
                print("[ERROR] Lost game state")
                rec.error = "debug_state returned None"
                session_ended = True
                slog.turns.append(rec)
                break

            # Re-record with full state
            roll_result = None
            if rec.roll:
                from straightjacket.engine.models import RollResult
                r = rec.roll
                roll_result = RollResult(
                    d1=r.d1, d2=r.d2, c1=r.c1, c2=r.c2,
                    stat_name=r.stat, stat_value=0,
                    action_score=r.total, result=r.result,
                    move="", match=r.match,
                )
            full_rec = record_turn(game, total_turns, rec.action, narration, roll_result)
            full_rec.is_correction = rec.is_correction
            full_rec.burn_offered = rec.burn_offered
            full_rec.burn_taken = rec.burn_taken
            full_rec.burn_error = rec.burn_error

            # Quality checks
            quality = check_narration_quality(narration)
            if quality:
                full_rec.narration_quality = quality
                for q in quality:
                    print(f"  [QUALITY] {q}")
                    slog.narration_quality_issues.append(f"Turn {total_turns}: {q}")

            spatial = check_npc_spatial_consistency(game, prev_npcs, narration)
            if spatial:
                full_rec.spatial_issues = spatial
                for s in spatial:
                    print(f"  [SPATIAL] {s}")
                    slog.spatial_issues.append(f"Turn {total_turns}: {s}")

            if do_invariants:
                violations = assert_game_state(game, total_turns)
                for v in violations:
                    print(f"  !!  {v}")
                    slog.violations.append(v)
                full_rec.violations = violations

            prev_npcs = list(full_rec.npcs)
            slog.turns.append(full_rec)
            _print_state(game)

            if total_turns % save_every == 0:
                await client.send({"type": "save", "name": save_out})
                await client.drain(timeout=2)
                print(f"  [SAVE] Saved to '{save_out}'")

            if game.game_over:
                ch_rec.ended_reason = "game_over"
                session_ended = True
                break
            bp = game.narrative.story_blueprint
            if bp and bp.story_complete and not game.campaign.epilogue_dismissed:
                ch_rec.ended_reason = "story_complete"
                break
        else:
            ch_rec.ended_reason = "max_turns_reached"

        ch_rec.turns_played = total_turns - chapter_start
        slog.chapters.append(ch_rec)
        if session_ended:
            break

        # ── Chapter transition ────────────────────────────────
        bp = game.narrative.story_blueprint
        if bp and bp.story_complete and not game.campaign.epilogue_dismissed:
            narration, game, should_break = await _chapter_transition(
                client, game, chapter_idx, max_chapters, print_full, slog)
            if should_break or not game:
                break
        else:
            break

    # ── Wrap up ───────────────────────────────────────────────
    slog.total_turns = total_turns
    if slog.ended_reason == "unknown":
        slog.ended_reason = ch_rec.ended_reason if slog.chapters else "complete"
    slog.burn_stats = {"offered": burns_offered, "taken": burns_taken, "failed": burns_failed}
    if game:
        slog.final_state = _final_state(game)
    slog.ended_at = datetime.now().isoformat()

    _print_summary(slog, game)

    await client.send({"type": "save", "name": save_out})
    await client.drain(timeout=2)

    log_path = _HERE / log_file
    log_path.write_text(json.dumps(slog.to_diagnostic_dict(), indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"  [LOG] Session log: {log_path}")

    if full_debug:
        full_path = log_path.with_stem(f"{log_path.stem}_full")
        full_path.write_text(json.dumps(slog.to_dict(), indent=2, ensure_ascii=False),
                             encoding="utf-8")
        print(f"  [LOG] Full debug log: {full_path}")

    await client.close()
    server.should_exit = True
    await asyncio.sleep(0.5)
    return slog


# ── Turn handlers ─────────────────────────────────────────────

async def _play_turn(client: WsClient, provider, game: GameState,
                     narration: str, turn: int, persona: str,
                     style: str, burn_setting: str,
                     print_full: bool, print_rolls: bool,
                     ) -> tuple[str, TurnRecord, dict | None]:
    """Play one turn. Returns (narration, partial_record, burn_data)."""
    context = build_turn_context(game, narration, turn)
    try:
        action = ask_bot(provider, persona, context, max_tokens=500)
    except Exception as e:
        print(f"[ERROR] Bot decision failed: {e}")
        return narration, TurnRecord(turn=turn, error=str(e)), None

    print(f"\n  [PLAYER] {action}")
    await client.send({"type": "player_input", "text": action})
    td = await client.collect_turn()

    if td["error"]:
        print(f"  [ERROR] {td['error']}")
        return narration, TurnRecord(turn=turn, action=action, error=td["error"]), None

    new_narration = (td["narration"] or {}).get("text", "")
    _print_narration(new_narration, print_full)

    rec = TurnRecord(turn=turn, chapter=game.campaign.chapter_number, action=action)
    roll_data = td["roll"]
    if roll_data and print_rolls:
        print(f"  [ROLL] {roll_data.get('move_label', '?')} "
              f"({roll_data.get('stat_label', '?')} {roll_data.get('stat_value', '?')}) "
              f"→ {roll_data.get('result_label', '?')}")
    if roll_data:
        rec.roll = RollRecord(
            stat=roll_data.get("stat_name", ""),
            d1=roll_data.get("d1", 0), d2=roll_data.get("d2", 0),
            total=roll_data.get("action_score", 0),
            c1=roll_data.get("c1", 0), c2=roll_data.get("c2", 0),
            result=roll_data.get("result", ""), match=roll_data.get("match", False),
        )

    burn_data = None
    if td["burn_offer"]:
        burn_data = await _handle_burn(client, provider, game, td["burn_offer"],
                                       burn_setting, style, rec)

    return new_narration, rec, burn_data


async def _play_correction(client: WsClient, provider, game: GameState,
                           turn: int, slog: SessionLog) -> tuple[str, TurnRecord]:
    """Send a correction. Returns (narration, partial_record)."""
    corrections = [
        "I didn't mean to do that — I wanted to just observe, not act",
        "That's not what I said — I was asking a question, not making a statement",
        "I wanted to talk to them, not confront them",
        "I was being cautious, not aggressive",
    ]
    text = _random.choice(corrections)
    print(f"  [CORRECTION TEST] ## {text}")

    await client.send({"type": "correction", "text": text})
    td = await client.collect_turn()

    rec = TurnRecord(turn=turn, chapter=game.campaign.chapter_number,
                     action=f"## {text}", is_correction=True)

    if td["error"]:
        rec.error = f"correction: {td['error']}"
        print(f"  [CORRECTION] Failed: {td['error']}")
        slog.correction_tests.append({"turn": turn, "correction": text,
                                       "success": False, "error": td["error"]})
        return "", rec

    narration = (td["replace_narration"] or {}).get("text", "")
    _print_narration(narration, full=False)
    slog.correction_tests.append({"turn": turn, "correction": text, "success": True})
    print("  [CORRECTION TEST] Completed")
    return narration, rec


async def _handle_burn(client: WsClient, provider, game: GameState,
                       burn_offer: dict, burn_setting: str, style: str,
                       rec: TurnRecord) -> dict:
    """Decide and execute momentum burn."""
    # Build a burn_info-compatible dict for decide_burn_momentum.
    # The prompt only reads current_result, new_result, momentum — all available.
    current = burn_offer.get("current", "MISS")
    upgrade = burn_offer.get("upgrade", "WEAK_HIT")
    cost = burn_offer.get("cost", 0)

    should_burn = False
    if burn_setting == "always":
        should_burn = True
    elif burn_setting != "never":
        try:
            compat_info = {
                "roll": type("_R", (), {"result": current})(),
                "new_result": upgrade,
            }
            should_burn = decide_burn_momentum(provider, game, compat_info, style)
        except Exception:
            should_burn = False

    rec.burn_offered = upgrade
    rec.burn_taken = should_burn
    print(f"  [BURN] {current} → {upgrade} (cost {cost}) | "
          f"{'BURN' if should_burn else 'skip'}")

    await client.send({"type": "burn_momentum", "accept": should_burn})
    error = ""
    if should_burn:
        td = await client.collect_turn()
        if td["error"]:
            error = td["error"]
            rec.burn_error = error
            print(f"  [BURN] Failed: {error}")
        elif td["replace_narration"]:
            print("  [BURN] Re-narrated")

    return {"taken": should_burn, "error": error}


async def _chapter_transition(client: WsClient, game: GameState,
                              chapter_idx: int, max_chapters: int,
                              print_full: bool,
                              slog: SessionLog) -> tuple[str, GameState | None, bool]:
    """Epilogue + new chapter. Returns (narration, game, should_break)."""
    print(f"\n{SEPARATOR}\n  GENERATING EPILOGUE\n{SEPARATOR}")
    await client.send({"type": "generate_epilogue"})
    td = await client.collect_turn(timeout=180)
    if td["error"]:
        print(f"  [EPILOGUE] Failed: {td['error']}")
        slog.ended_reason = f"epilogue_error: {td['error']}"
        return "", None, True
    if td["epilogue"]:
        _print_narration(td["epilogue"].get("text", ""), full=True)

    if chapter_idx + 1 >= max_chapters:
        slog.ended_reason = "max_chapters_reached"
        return "", game, True

    print(f"\n{SEPARATOR}\n  STARTING NEW CHAPTER\n{SEPARATOR}")
    await client.send({"type": "new_chapter"})
    td = await client.collect_turn(timeout=180)
    if td["error"]:
        print(f"  [CHAPTER] Failed: {td['error']}")
        slog.ended_reason = f"chapter_error: {td['error']}"
        return "", None, True

    ch_msg = td["chapter_started"]
    narration = ch_msg.get("narration", "") if ch_msg else ""
    _print_narration(narration, print_full)

    new_game = await client.get_debug_state()
    return narration, new_game, False


# ── Helpers ───────────────────────────────────────────────────

def _print_narration(narration: str, full: bool) -> None:
    if full:
        print(f"\n  [NARRATOR]\n{narration}\n")
    else:
        excerpt = narration.replace("\n", " ").strip()[:220]
        print(f"\n  [NARRATOR] {excerpt}{'...' if len(narration) > 220 else ''}")


def _print_state(game: GameState) -> None:
    r = game.resources
    print(f"  [STATE] H:{r.health} Sp:{r.spirit} Su:{r.supply} "
          f"Mo:{r.momentum} Chaos:{game.world.chaos_factor} "
          f"Scene:{game.narrative.scene_count}")


def _final_state(game: GameState) -> dict:
    return {
        "character": game.player_name,
        "chapter": game.campaign.chapter_number,
        "location": game.world.current_location,
        "scene": game.narrative.scene_count,
        "health": game.resources.health,
        "spirit": game.resources.spirit,
        "supply": game.resources.supply,
        "momentum": game.resources.momentum,
        "chaos": game.world.chaos_factor,
        "npcs": len(game.npcs),
        "active_clocks": len([c for c in game.world.clocks if not c.fired]),
    }


def _print_summary(slog: SessionLog, game: GameState | None) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  Session complete: {slog.ended_reason}")
    print(f"  Chapters played : {len(slog.chapters)}")
    print(f"  Total turns     : {slog.total_turns}")
    print(f"  Violations      : {len(slog.violations)}")
    if game:
        print(f"  Final scene     : {game.narrative.scene_count}")
        print(f"  Final health    : {game.resources.health} | spirit: {game.resources.spirit}")
    bs = slog.burn_stats
    if bs.get("offered", 0) > 0:
        print(f"  Burns           : {bs['offered']} offered, {bs['taken']} taken, {bs['failed']} failed")
    if slog.narration_quality_issues:
        print(f"  Quality issues  : {len(slog.narration_quality_issues)}")
    if slog.spatial_issues:
        print(f"  Spatial issues  : {len(slog.spatial_issues)}")
    if slog.correction_tests:
        failed = sum(1 for c in slog.correction_tests if not c.get("success"))
        print(f"  Corrections     : {len(slog.correction_tests)} tested, {failed} failed")
    print(SEPARATOR)
