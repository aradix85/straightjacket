from __future__ import annotations

import json
import time
import random as _random
import traceback
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from straightjacket.engine.ai.provider_base import AIProvider

from straightjacket.engine.ai.api_client import check_configured_models, get_provider
from straightjacket.engine.ai.provider_base import drain_token_log
from straightjacket.engine.ai.sentence_stream import SentenceStream
from straightjacket.engine.models import EngineConfig, GameState
from straightjacket.engine.persistence import delete_save, load_game, save_game
from straightjacket.engine.user_management import create_user
from straightjacket.engine.config_loader import VERSION, model_for_role, provider_for_role
from straightjacket.engine.correction import process_correction
from straightjacket.engine.game.momentum_burn import process_momentum_burn
from straightjacket.engine.datasworn.settings import list_packages
from straightjacket.engine.game import (
    determine_end_reason,
    prepare_succession,
    start_succession_with_character,
    generate_epilogue,
    process_turn,
    run_deferred_director,
    start_new_chapter,
    start_new_game,
)

from .coverage import Coverage, world_view
from .judge import judge_turn
from .report import write_report
from .ai_helpers import ask_bot, build_turn_context, decide_burn_momentum, get_persona
from .creation import roll_character
from .invariants import assert_game_state
from .models import ChapterRecord, NpcSnapshot, SessionLog, TurnRecord
from .quality_checks import (
    check_chapter_continuity,
    check_narration_quality,
    check_npc_spatial_consistency,
)
from .recorder import record_turn
from .display import print_narration, print_state, print_summary

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"
SEPARATOR = "=" * 62


CORRECTION_TEST_INTERVAL = 8


def load_config(path: Path) -> dict:
    if not path.exists():
        print(f"[ERROR] Config not found: {path}")
        raise SystemExit(1)
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_session(bot_cfg: dict, auto_override: bool = False, turns_override: int | None = None) -> SessionLog:
    auto_mode = auto_override or bot_cfg["auto_mode"]
    username = bot_cfg["username"]
    game_cfg = bot_cfg["game"]
    session_cfg = bot_cfg["session"]
    behavior = bot_cfg["bot_behavior"]
    log_cfg = bot_cfg["logging"]

    max_chapters = session_cfg["max_chapters"]
    max_turns = turns_override or session_cfg["max_turns"]
    narration_lang = session_cfg["narration_lang"]
    save_every = session_cfg["save_every_n_turns"]
    save_out = session_cfg["save_name_output"]
    clean_before = session_cfg["clean_before_run"]
    style = behavior["style"]
    burn_setting = behavior["burn_momentum"]
    setting_id = game_cfg["setting_id"]
    log_file_base = Path(log_cfg["log_file"])
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    log_file = log_file_base.with_stem(f"{log_file_base.stem}_{setting_id}_{style}_{timestamp}")
    print_full = log_cfg["print_full_narration"]
    print_rolls = log_cfg["print_roll_details"]
    do_invariants = log_cfg["assert_state_invariants"]
    judge_cfg = bot_cfg["judge"] if bot_cfg["judge"]["enabled"] else None
    prices = bot_cfg["prices"]
    succession_enabled = session_cfg["succession_on_game_over"]
    coverage = Coverage()
    full_debug = log_cfg["full_debug_log"]

    check_configured_models()
    provider = get_provider()
    config = EngineConfig(narration_lang=narration_lang)
    create_user(username)

    if clean_before and not game_cfg["load_existing"] and delete_save(username, save_out):
        print(f"[CLEAN] Deleted previous save '{save_out}'")

    persona = get_persona(style)

    slog = SessionLog(
        config=bot_cfg,
        engine_version=VERSION,
        style=style,
    )

    print(f"\n{SEPARATOR}")
    print(f"  Straightjacket — Elvira Test Bot — {style.upper()} mode")
    print(
        f"  Auto: {'YES' if auto_mode else 'NO'} | Turns/ch: {max_turns} | "
        f"Chapters: {max_chapters} | Lang: {narration_lang}"
    )
    roles = ", ".join(
        f"{role}={provider_for_role(role)}/{model_for_role(role)}" for role in ("narrator", "brain", "director")
    )
    print(f"  Engine: v{VERSION} | {roles}")
    print(SEPARATOR)

    game, narration, chat_messages = _setup_game(provider, config, username, game_cfg, auto_mode, slog)

    _log_story_blueprint(game, slog)

    prev_npcs: list[NpcSnapshot] | None = None

    pre_chapter_npcs: list[NpcSnapshot] | None = None

    burns_offered = 0
    burns_taken = 0
    burns_failed = 0

    total_turns = 0
    session_ended = False

    for chapter_idx in range(max_chapters):
        chapter_num = game.campaign.chapter_number
        chapter_start = total_turns
        ch_rec = ChapterRecord(chapter=chapter_num)

        if chapter_idx > 0:
            print(f"\n{SEPARATOR}")
            print(f"  CHAPTER {chapter_num} — {game.player_name} at {game.world.current_location}")
            print(SEPARATOR)

        prev_action = ""
        for _ in range(max_turns):
            total_turns += 1
            print(f"\n{SEPARATOR}\n  TURN {total_turns}/{max_chapters * max_turns}\n{SEPARATOR}")

            is_correction_turn = (
                total_turns > 1 and total_turns % CORRECTION_TEST_INTERVAL == 0 and game.last_turn_snapshot is not None
            )

            if is_correction_turn:
                game, narration, turn_rec, session_ended = _play_correction_turn(
                    provider, config, game, narration, total_turns, persona, slog
                )
            else:
                game, narration, turn_rec, session_ended = _play_turn(
                    provider,
                    config,
                    game,
                    narration,
                    total_turns,
                    persona,
                    style,
                    burn_setting,
                    print_full,
                    print_rolls,
                    do_invariants,
                    slog,
                    prev_npcs,
                    coverage=coverage,
                    judge_cfg=judge_cfg,
                    max_turns=max_chapters * max_turns,
                    prev_action=prev_action,
                )

            prev_action = turn_rec.action or ""

            if turn_rec.burn_offered:
                burns_offered += 1
                if turn_rec.burn_taken:
                    burns_taken += 1
                if turn_rec.burn_error:
                    burns_failed += 1

            prev_npcs = list(turn_rec.npcs)

            slog.turns.append(turn_rec)
            chat_messages.append({"role": "user", "content": turn_rec.action})
            chat_messages.append({"role": "assistant", "content": narration})

            if total_turns % save_every == 0:
                _save_and_verify(game, username, chat_messages, save_out, slog, coverage)

            if game.game_over and not session_ended and succession_enabled and not slog.succession:
                game, succession_narration = _play_succession(provider, config, game, game_cfg, slog, coverage)
                if "error" not in slog.succession:
                    narration = succession_narration
                    chat_messages.append({"role": "assistant", "content": narration})
                    continue

            if session_ended or game.game_over:
                ch_rec.ended_reason = "game_over" if game.game_over else "engine_error"
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

        bp = game.narrative.story_blueprint
        if bp and bp.story_complete and not game.campaign.epilogue_dismissed:
            pre_chapter_npcs = [
                NpcSnapshot(
                    id=n.id,
                    name=n.name,
                    status=n.status,
                    disposition=n.disposition,
                    memory_count=len(n.memory),
                    last_location=n.last_location,
                )
                for n in game.npcs
                if n.status in ("active", "background")
            ]

            game, narration, chat_messages, should_break = _chapter_transition(
                provider, config, game, chat_messages, username, save_out, chapter_num, chapter_idx, max_chapters, slog
            )

            if not should_break and pre_chapter_npcs:
                cont_issues = check_chapter_continuity(game, pre_chapter_npcs)
                for issue in cont_issues:
                    print(f"  [CONTINUITY] {issue}")
                    slog.chapter_continuity_issues.append(f"Ch{chapter_num}→{chapter_num + 1}: {issue}")

            if should_break:
                break
        else:
            break

    slog.total_turns = total_turns
    slog.ended_reason = (
        slog.ended_reason if slog.ended_reason != "unknown" else (ch_rec.ended_reason if slog.chapters else "complete")
    )
    slog.character = {"name": game.player_name, "concept": game.character_concept, "setting": game.setting_id}
    slog.quality_summary = _aggregate_quality_stats(slog)
    slog.token_summary = _aggregate_token_stats(slog)
    slog.burn_stats = {
        "offered": burns_offered,
        "taken": burns_taken,
        "failed": burns_failed,
    }

    print_summary(slog, game)
    _save_and_verify(game, username, chat_messages, save_out, slog, coverage)
    coverage.hit("burn_offered", burns_offered)
    coverage.hit("burn_taken", burns_taken)
    coverage.hit("correction", len(slog.correction_tests))
    coverage.hit("chapter_transition", max(0, len(slog.chapters) - 1))
    if any(ch.ended_reason == "game_over" for ch in slog.chapters):
        coverage.hit("game_over")
    slog.coverage = coverage.summary()
    report_path = write_report(slog, coverage, RUNS_DIR / f"{log_file.stem}.md", prices)
    print(f"  [REPORT] {report_path}")

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = RUNS_DIR / log_file
    log_path.write_text(json.dumps(slog.to_diagnostic_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  [LOG] Session log written to: {log_path}")

    if full_debug:
        full_path = log_path.with_stem(f"{log_path.stem}_full")
        full_path.write_text(json.dumps(slog.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  [LOG] Full debug log written to: {full_path}")

    return slog


def _setup_game(
    provider: AIProvider, config: EngineConfig, username: str, game_cfg: dict, auto_mode: bool, slog: SessionLog
) -> tuple[GameState, str, list[dict]]:
    if not auto_mode and game_cfg["load_existing"]:
        save_name = game_cfg["save_name"]
        game, chat_messages = load_game(username, save_name)
        if not game:
            raise SystemExit(f"Save '{save_name}' not found for user '{username}'")
        narration = ""
        for msg in reversed(chat_messages):
            if msg.get("role") == "assistant" and not msg.get("recap"):
                narration = msg.get("content", "")
                break
        print(
            f"[SETUP] Loaded: {game.player_name} (Ch{game.campaign.chapter_number}, Scene {game.narrative.scene_count})"
        )
        return game, narration, chat_messages

    setting_id = game_cfg["setting_id"]
    if setting_id == "":
        available = [s for s in list_packages() if s != "delve"]
        setting_id = _random.choice(available)

    creation_data = roll_character(setting_id, game_cfg)

    try:
        game, narration = start_new_game(provider, creation_data, config, username)
    except Exception as e:
        print(f"[ERROR] start_new_game failed: {e}")
        traceback.print_exc()
        raise SystemExit(1) from e

    print(f"[SETUP] Character: {game.player_name} at {game.world.current_location}")
    return game, narration, [{"role": "assistant", "content": narration}]


def _play_turn(
    provider: AIProvider,
    config: EngineConfig,
    game: GameState,
    narration: str,
    turn: int,
    persona: str,
    style: str,
    burn_setting: str,
    print_full: bool,
    print_rolls: bool,
    do_invariants: bool,
    slog: SessionLog,
    prev_npcs: list[NpcSnapshot] | None,
    coverage: Coverage,
    judge_cfg: dict | None,
    max_turns: int,
    prev_action: str = "",
) -> tuple[GameState, str, TurnRecord, bool]:
    context = build_turn_context(
        game, narration, turn, prev_action=prev_action, directive_key=coverage.steer(turn, max_turns)
    )
    try:
        action = ask_bot(provider, persona, context, max_tokens=500)
    except Exception as e:
        print(f"[ERROR] Bot decision failed: {e}")
        rec = TurnRecord(turn=turn, chapter=game.campaign.chapter_number, error=str(e))
        return game, narration, rec, True

    print(f"\n  [PLAYER] {action}")

    before = world_view(game)
    sentences: list[str] = []
    first_at: list[float] = []
    started = time.monotonic()

    def on_sentence(text: str) -> None:
        if not first_at:
            first_at.append(time.monotonic() - started)
        sentences.append(text)

    stream = SentenceStream(on_sentence)
    try:
        game, narration, roll, burn_info, director_ctx = process_turn(provider, game, action, config, stream)
    except Exception as e:
        print(f"[ERROR] process_turn failed: {e}")
        traceback.print_exc()
        rec = TurnRecord(turn=turn, chapter=game.campaign.chapter_number, action=action, error=str(e))
        return game, narration, rec, True

    print_narration(narration, print_full)
    if roll and print_rolls:
        print(
            f"  [ROLL] {roll.stat_name.upper()} {roll.stat_value} | "
            f"Action {roll.d1}+{roll.stat_value}={roll.action_score} vs "
            f"[{roll.c1}, {roll.c2}] -> {roll.result}"
        )

    rec = record_turn(game, turn, action, narration, roll)
    rec.turn_secs = round(time.monotonic() - started, 1)
    _record_stream(rec, stream, sentences, first_at, narration, slog, coverage)
    result = roll.result if roll else None
    match = bool(roll and roll.match)
    coverage.observe_turn(before, world_view(game), result, match, roll.move if roll else "")

    if burn_info:
        _handle_burn(provider, config, game, burn_info, burn_setting, style, rec)

    if director_ctx:
        try:
            run_deferred_director(provider, game, director_ctx)
            rec.director_ran = True
            rec.token_usage.extend(drain_token_log())
            coverage.hit("director")
            sl = game.narrative.session_log
            trigger = sl[-1].director_trigger if sl else "?"
            print(f"  [DIRECTOR] Ran — trigger: {trigger}")
        except Exception as e:
            rec.director_error = str(e)

    print_state(game)

    quality_issues = check_narration_quality(narration)
    if quality_issues:
        rec.narration_quality = quality_issues
        for issue in quality_issues:
            print(f"  [QUALITY] {issue}")
            slog.narration_quality_issues.append(f"Turn {turn}: {issue}")

    spatial_issues = check_npc_spatial_consistency(game, prev_npcs, narration)
    if spatial_issues:
        rec.spatial_issues = spatial_issues
        for issue in spatial_issues:
            print(f"  [SPATIAL] {issue}")
            slog.spatial_issues.append(f"Turn {turn}: {issue}")

    if do_invariants:
        violations = assert_game_state(game, turn)
        for v in violations:
            print(f"  !!  {v}")
            slog.violations.append(v)
        rec.violations = violations

    if judge_cfg:
        rec.judge = judge_turn(provider, judge_cfg, game, action, narration, result, match)
        _print_audit(rec.judge)

    return game, narration, rec, False


def _record_stream(
    rec: TurnRecord,
    stream: SentenceStream,
    sentences: list[str],
    first_at: list[float],
    narration: str,
    slog: SessionLog,
    coverage: Coverage,
) -> None:
    rec.stream_first_sentence_secs = round(first_at[0], 1) if first_at else None
    rec.stream_sentences = len(sentences)
    rec.stream_complete = stream.complete
    rec.stream_matches = _norm(" ".join(sentences)) == _norm(narration)
    if stream.complete:
        coverage.hit("stream_complete")
        if not rec.stream_matches:
            slog.stream_issues.append(f"Turn {rec.turn}: streamed text differs from the final narration")


def _print_audit(verdict: dict) -> None:
    if "overall" in verdict:
        print(f"  [AUDIT] {verdict['overall']}/10: {verdict['weakness']}")
    else:
        print(f"  [AUDIT] no verdict: {verdict['error']}")


def _norm(text: str) -> str:
    return " ".join(text.split())


def _save_and_verify(
    game: GameState, username: str, chat_messages: list[dict], save_out: str, slog: SessionLog, coverage: Coverage
) -> None:
    _try_save(game, username, chat_messages, save_out)
    loaded, _messages = load_game(username, save_out)
    if loaded is None:
        slog.save_roundtrip_issues.append(
            f"scene {game.narrative.scene_count}: save '{save_out}' could not be loaded back"
        )
        return
    before, after = game.to_dict(), loaded.to_dict()
    changed = sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))
    coverage.hit("save_roundtrip")
    if changed:
        slog.save_roundtrip_issues.append(f"scene {game.narrative.scene_count}: save/load changed {', '.join(changed)}")


def _play_succession(
    provider: AIProvider, config: EngineConfig, game: GameState, game_cfg: dict, slog: SessionLog, coverage: Coverage
) -> tuple[GameState, str]:
    coverage.hit("game_over")
    try:
        prepare_succession(game, determine_end_reason(game))
        creation_data = roll_character(game.setting_id, game_cfg)
        game, narration = start_succession_with_character(provider, game, creation_data, config)
    except Exception as e:
        slog.succession = {"error": f"{type(e).__name__}: {e}"[:300]}
        print(f"  [SUCCESSION] Failed: {e}")
        return game, ""
    slog.succession = {"new_character": game.player_name}
    coverage.hit("succession")
    print(f"  [SUCCESSION] Continuing as {game.player_name}")
    return game, narration


def _play_correction_turn(
    provider: AIProvider,
    config: EngineConfig,
    game: GameState,
    narration: str,
    turn: int,
    persona: str,
    slog: SessionLog,
) -> tuple[GameState, str, TurnRecord, bool]:
    print(f"  [CORRECTION TEST] Sending ## correction at turn {turn}")

    correction_prompts = [
        "## I didn't mean to do that — I wanted to just observe, not act",
        "## That's not what I said — I was asking a question, not making a statement",
        "## I wanted to talk to them, not confront them",
        "## I was being cautious, not aggressive",
    ]
    correction_text = _random.choice(correction_prompts)
    print(f"\n  [PLAYER] {correction_text}")

    try:
        game, new_narration, director_ctx = process_correction(
            provider, game, correction_text.lstrip("# ").strip(), config
        )
    except Exception as e:
        print(f"  [CORRECTION] Failed: {e}")
        traceback.print_exc()
        rec = TurnRecord(
            turn=turn,
            chapter=game.campaign.chapter_number,
            action=correction_text,
            is_correction=True,
            error=f"correction: {e}",
        )
        slog.correction_tests.append(
            {
                "turn": turn,
                "correction": correction_text,
                "success": False,
                "error": str(e),
            }
        )
        return game, narration, rec, False

    rec = record_turn(game, turn, correction_text, new_narration, None)
    rec.is_correction = True

    quality_issues = check_narration_quality(new_narration)
    if quality_issues:
        rec.narration_quality = quality_issues
        for issue in quality_issues:
            slog.narration_quality_issues.append(f"Turn {turn} (correction): {issue}")

    if director_ctx:
        try:
            run_deferred_director(provider, game, director_ctx)
            rec.director_ran = True
        except Exception as e:
            rec.director_error = str(e)

    print_narration(new_narration, full=False)
    print_state(game)

    violations = assert_game_state(game, turn)
    if violations:
        rec.violations = violations
        for v in violations:
            print(f"  !!  {v}")
            slog.violations.append(v)

    slog.correction_tests.append(
        {
            "turn": turn,
            "correction": correction_text,
            "success": True,
            "violations": violations,
            "quality_issues": quality_issues,
        }
    )
    print("  [CORRECTION TEST] Completed successfully")

    return game, new_narration, rec, False


def _handle_burn(
    provider: AIProvider,
    config: EngineConfig,
    game: GameState,
    burn_info: dict,
    burn_setting: str,
    style: str,
    rec: TurnRecord,
) -> GameState:
    should_burn = False
    if burn_setting == "always":
        should_burn = True
    elif burn_setting != "never":
        try:
            should_burn = decide_burn_momentum(provider, game, burn_info, style)
        except Exception:
            should_burn = False

    rec.burn_offered = burn_info["new_result"]
    rec.burn_taken = should_burn
    print(
        f"  [BURN] Available ({burn_info['roll'].result} -> "
        f"{burn_info['new_result']}) | Decision: {'BURN' if should_burn else 'skip'}"
    )

    if should_burn:
        try:
            game, narration = process_momentum_burn(
                provider=provider,
                game=game,
                old_roll=burn_info["roll"],
                new_result=burn_info["new_result"],
                brain_data=burn_info["brain"],
                player_words=burn_info["player_words"],
                config=config,
                pre_snapshot=burn_info["pre_snapshot"],
                scene_setup=burn_info.get("scene_setup"),
            )
            print(f"  [BURN] Re-narrated: {narration.replace(chr(10), ' ')[:180]}...")
        except Exception as e:
            rec.burn_error = str(e)
            print(f"  [BURN] Failed: {e}")

    return game


def _chapter_transition(
    provider: AIProvider,
    config: EngineConfig,
    game: GameState,
    chat_messages: list[dict],
    username: str,
    save_out: str,
    chapter_num: int,
    chapter_idx: int,
    max_chapters: int,
    slog: SessionLog,
) -> tuple[GameState, str, list[dict], bool]:
    print(f"\n{SEPARATOR}\n  GENERATING EPILOGUE — Chapter {chapter_num}\n{SEPARATOR}")
    try:
        game, epilogue = generate_epilogue(provider, game, config)
        chat_messages.append({"role": "assistant", "content": epilogue, "epilogue": True})
        print_narration(epilogue, full=True)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"  [EPILOGUE] Failed: {e}")
        print(tb)
        slog.ended_reason = f"epilogue_error: {type(e).__name__}: {e}"
        slog.violations.append(f"CRASH in generate_epilogue: {tb[-500:]}")
        return game, "", chat_messages, True

    save_game(game, username, chat_messages, save_out)

    if chapter_idx + 1 >= max_chapters:
        slog.ended_reason = "max_chapters_reached"
        return game, "", chat_messages, True

    print(f"\n{SEPARATOR}\n  STARTING CHAPTER {chapter_num + 1}\n{SEPARATOR}")
    try:
        game, narration = start_new_chapter(provider, game, config, username)
        chat_messages = [{"role": "assistant", "content": narration}]
        print(f"  [CHAPTER] Chapter {game.campaign.chapter_number} at {game.world.current_location}")
        return game, narration, chat_messages, False
    except Exception as e:
        tb = traceback.format_exc()
        print(f"  [CHAPTER] Failed: {e}")
        print(tb)
        slog.ended_reason = f"chapter_transition_error: {type(e).__name__}: {e}"
        slog.violations.append(f"CRASH in start_new_chapter: {tb[-500:]}")
        return game, "", chat_messages, True


def _try_save(game: GameState, username: str, chat_messages: list[dict], save_out: str) -> None:
    try:
        save_game(game, username, chat_messages, save_out)
        print(f"  [SAVE] Saved to '{save_out}'")
    except Exception as e:
        print(f"  [SAVE] Failed: {e}")


def _log_story_blueprint(game: GameState, slog: SessionLog) -> None:
    bp = game.narrative.story_blueprint
    if not bp:
        return
    slog.story_blueprint = {
        "structure_type": bp.structure_type,
        "central_conflict": bp.central_conflict,
        "thematic_thread": bp.thematic_thread,
        "acts": [a.to_dict() for a in bp.acts],
    }


def _aggregate_quality_stats(slog: SessionLog) -> dict:
    quality_counts: dict[str, int] = {}
    for issue in slog.narration_quality_issues:
        parts = issue.split(": ", 1)
        issue_type = parts[1].split(":")[0] if len(parts) > 1 else issue
        quality_counts[issue_type] = quality_counts.get(issue_type, 0) + 1
    return {
        "narration_quality_total": len(slog.narration_quality_issues),
        "spatial_issues_total": len(slog.spatial_issues),
        "chapter_continuity_total": len(slog.chapter_continuity_issues),
        "correction_tests_total": len(slog.correction_tests),
        "correction_tests_failed": sum(1 for c in slog.correction_tests if not c.get("success")),
        "top_quality_issues": sorted(quality_counts.items(), key=lambda x: -x[1])[:10],
    }


def _aggregate_token_stats(slog: SessionLog) -> dict:
    by_role: dict[str, dict[str, int]] = {}
    total_input = 0
    total_output = 0
    for t in slog.turns:
        for entry in t.token_usage:
            role = str(entry["role"])
            inp = int(entry["input"])
            out = int(entry["output"])
            if role not in by_role:
                by_role[role] = {"calls": 0, "input": 0, "output": 0}
            by_role[role]["calls"] += 1
            by_role[role]["input"] += inp
            by_role[role]["output"] += out
            total_input += inp
            total_output += out
    return {
        "total_input": total_input,
        "total_output": total_output,
        "total": total_input + total_output,
        "by_role": by_role,
    }
