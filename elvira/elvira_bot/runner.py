"""Session runner: game setup, turn loop, chapter transitions, quality checks."""

from __future__ import annotations

import json
import random as _random
import traceback
from datetime import datetime
from pathlib import Path

import yaml

from straightjacket.engine import (
    EngineConfig,
    GameState,
    create_user,
    delete_save,
    get_provider,
    load_game,
    save_game,
)
from straightjacket.engine.config_loader import VERSION, cfg
from straightjacket.engine.correction import process_correction, process_momentum_burn
from straightjacket.engine.datasworn.settings import list_packages
from straightjacket.engine.game import (
    generate_epilogue,
    process_turn,
    run_deferred_director,
    start_new_chapter,
    start_new_game,
)

from .ai_helpers import ask_bot, build_turn_context, decide_burn_momentum, get_persona
from .creation import roll_character
from .invariants import assert_game_state
from .models import ChapterRecord, NpcSnapshot, SessionLog, TurnRecord, ValidatorRecord
from .quality_checks import (
    check_chapter_continuity,
    check_narration_quality,
    check_npc_spatial_consistency,
)
from .recorder import record_turn

_HERE = Path(__file__).resolve().parent.parent
SEPARATOR = "=" * 62

# Correction test frequency: every N turns, send a ## correction
CORRECTION_TEST_INTERVAL = 8


def load_config(path: Path) -> dict:
    if not path.exists():
        print(f"[ERROR] Config not found: {path}")
        raise SystemExit(1)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_session(bot_cfg: dict, auto_override: bool = False, turns_override: int | None = None) -> SessionLog:
    auto_mode = auto_override or bot_cfg.get("auto_mode", False)
    username = bot_cfg["username"]
    game_cfg = bot_cfg.get("game", {})
    session_cfg = bot_cfg.get("session", {})
    behavior = bot_cfg.get("bot_behavior", {})
    log_cfg = bot_cfg.get("logging", {})

    max_chapters = session_cfg.get("max_chapters", 1)
    max_turns = turns_override or session_cfg.get("max_turns", 20)
    narration_lang = session_cfg.get("narration_lang", "English")
    save_every = session_cfg.get("save_every_n_turns", 5)
    save_out = session_cfg.get("save_name_output", "elvira")
    clean_before = session_cfg.get("clean_before_run", True)
    style = behavior.get("style", "balanced")
    burn_setting = behavior.get("burn_momentum", "auto")
    log_file = Path(log_cfg.get("log_file", "elvira_session.json"))
    print_full = log_cfg.get("print_full_narration", False)
    print_rolls = log_cfg.get("print_roll_details", True)
    do_invariants = log_cfg.get("assert_state_invariants", True)
    full_debug = log_cfg.get("full_debug_log", False)

    provider = get_provider()
    config = EngineConfig(narration_lang=narration_lang)
    create_user(username)

    if clean_before and not game_cfg.get("load_existing") and delete_save(username, save_out):
        print(f"[CLEAN] Deleted previous save '{save_out}'")

    persona = get_persona(style)

    slog = SessionLog(
        started_at=datetime.now().isoformat(),
        config=bot_cfg,
        engine_version=VERSION,
        auto_mode=auto_mode,
        style=style,
        max_chapters=max_chapters,
    )

    # ── Game setup ────────────────────────────────────────────
    print(f"\n{SEPARATOR}")
    print(f"  Straightjacket — Elvira Test Bot — {style.upper()} mode")
    print(f"  Auto: {'YES' if auto_mode else 'NO'} | Turns/ch: {max_turns} | "
          f"Chapters: {max_chapters} | Lang: {narration_lang}")
    print(f"  Engine: v{VERSION} | Provider: {cfg().ai.provider}")
    print(SEPARATOR)

    game, narration, chat_messages = _setup_game(
        provider, config, username, game_cfg, auto_mode, slog)

    slog.character = game.player_name
    slog.location_start = game.world.current_location
    slog.game_context = _game_context_dict(game)
    slog.opening_narration = narration
    _log_opening_validator(game, slog)
    _log_story_blueprint(game, slog)

    # Track NPCs across turns for spatial consistency
    prev_npcs: list[NpcSnapshot] | None = None
    # Track NPCs before chapter transition for continuity checks
    pre_chapter_npcs: list[NpcSnapshot] | None = None
    # Burn statistics
    burns_offered = 0
    burns_taken = 0
    burns_failed = 0

    # ── Chapter loop ──────────────────────────────────────────
    total_turns = 0
    session_ended = False

    for chapter_idx in range(max_chapters):
        chapter_num = game.campaign.chapter_number
        chapter_start = total_turns
        ch_rec = ChapterRecord(chapter=chapter_num, started_at_turn=total_turns + 1)

        if chapter_idx > 0:
            print(f"\n{SEPARATOR}")
            print(f"  CHAPTER {chapter_num} — {game.player_name} at {game.world.current_location}")
            print(SEPARATOR)

        # ── Turn loop ─────────────────────────────────────────
        for _ in range(max_turns):
            total_turns += 1
            print(f"\n{SEPARATOR}\n  TURN {total_turns}/{max_chapters * max_turns}\n{SEPARATOR}")

            # Decide: correction test or normal turn
            is_correction_turn = (
                total_turns > 1
                and total_turns % CORRECTION_TEST_INTERVAL == 0
                and game.last_turn_snapshot is not None
            )

            if is_correction_turn:
                game, narration, turn_rec, session_ended = _play_correction_turn(
                    provider, config, game, narration, total_turns, persona, slog)
            else:
                game, narration, turn_rec, session_ended = _play_turn(
                    provider, config, game, narration, total_turns, persona,
                    style, burn_setting, print_full, print_rolls, do_invariants,
                    slog, prev_npcs)

            # Track burn stats
            if turn_rec.burn_offered:
                burns_offered += 1
                if turn_rec.burn_taken:
                    burns_taken += 1
                if turn_rec.burn_error:
                    burns_failed += 1

            # Update prev_npcs for next turn's spatial check
            prev_npcs = list(turn_rec.npcs)

            slog.turns.append(turn_rec)
            chat_messages.append({"role": "user", "content": turn_rec.action})
            chat_messages.append({"role": "assistant", "content": narration})

            if total_turns % save_every == 0:
                _try_save(game, username, chat_messages, save_out)

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

        # ── Chapter transition ────────────────────────────────
        bp = game.narrative.story_blueprint
        if bp and bp.story_complete and not game.campaign.epilogue_dismissed:
            # Snapshot NPCs before transition for continuity check
            pre_chapter_npcs = [
                NpcSnapshot(id=n.id, name=n.name, status=n.status,
                            disposition=n.disposition, bond=n.bond,
                            memory_count=len(n.memory), last_location=n.last_location)
                for n in game.npcs if n.status in ("active", "background")
            ]

            game, narration, chat_messages, should_break = _chapter_transition(
                provider, config, game, chat_messages, username, save_out,
                chapter_num, chapter_idx, max_chapters, slog)

            # Chapter continuity check
            if not should_break and pre_chapter_npcs:
                cont_issues = check_chapter_continuity(game, pre_chapter_npcs)
                for issue in cont_issues:
                    print(f"  [CONTINUITY] {issue}")
                    slog.chapter_continuity_issues.append(
                        f"Ch{chapter_num}→{chapter_num+1}: {issue}")

            if should_break:
                break
        else:
            break

    # ── Wrap up ───────────────────────────────────────────────
    slog.total_turns = total_turns
    slog.ended_reason = slog.ended_reason if slog.ended_reason != "unknown" else (
        ch_rec.ended_reason if slog.chapters else "complete")
    slog.validator_summary = _aggregate_validator_stats(slog)
    slog.quality_summary = _aggregate_quality_stats(slog)
    slog.burn_stats = {
        "offered": burns_offered,
        "taken": burns_taken,
        "failed": burns_failed,
    }
    slog.final_state = _final_state_dict(game)
    slog.ended_at = datetime.now().isoformat()

    _print_summary(slog, game)
    _try_save(game, username, chat_messages, save_out)

    log_path = _HERE / log_file
    log_path.write_text(json.dumps(slog.to_diagnostic_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  [LOG] Session log written to: {log_path}")

    if full_debug:
        full_path = log_path.with_stem(f"{log_path.stem}_full")
        full_path.write_text(json.dumps(slog.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  [LOG] Full debug log written to: {full_path}")

    return slog


# ── Setup ─────────────────────────────────────────────────────

def _setup_game(provider, config, username, game_cfg, auto_mode, slog):
    if not auto_mode and game_cfg.get("load_existing"):
        save_name = game_cfg.get("save_name", "autosave")
        game, chat_messages = load_game(username, save_name)
        if not game:
            raise SystemExit(f"Save '{save_name}' not found for user '{username}'")
        narration = ""
        for msg in reversed(chat_messages):
            if msg.get("role") == "assistant" and not msg.get("recap"):
                narration = msg.get("content", "")
                break
        print(f"[SETUP] Loaded: {game.player_name} (Ch{game.campaign.chapter_number}, "
              f"Scene {game.narrative.scene_count})")
        return game, narration, chat_messages

    setting_id = game_cfg.get("setting_id", "starforged")
    if auto_mode:
        available = [s for s in list_packages() if s != "delve"] or ["starforged"]
        setting_id = _random.choice(available)

    creation_data = roll_character(setting_id, game_cfg)
    slog.creation_data = creation_data

    try:
        game, narration = start_new_game(provider, creation_data, config, username)
    except Exception as e:
        print(f"[ERROR] start_new_game failed: {e}")
        traceback.print_exc()
        raise SystemExit(1) from e

    print(f"[SETUP] Character: {game.player_name} at {game.world.current_location}")
    return game, narration, [{"role": "assistant", "content": narration}]


# ── Normal turn ───────────────────────────────────────────────

def _play_turn(provider, config, game, narration, turn, persona, style,
               burn_setting, print_full, print_rolls, do_invariants,
               slog, prev_npcs):
    # 1. Bot decides action
    context = build_turn_context(game, narration, turn)
    try:
        action = ask_bot(provider, persona, context, max_tokens=500)
    except Exception as e:
        print(f"[ERROR] Bot decision failed: {e}")
        rec = TurnRecord(turn=turn, chapter=game.campaign.chapter_number, error=str(e))
        return game, narration, rec, True

    print(f"\n  [PLAYER] {action}")

    # 2. Process turn
    try:
        game, narration, roll, burn_info, director_ctx = process_turn(
            provider, game, action, config)
    except Exception as e:
        print(f"[ERROR] process_turn failed: {e}")
        traceback.print_exc()
        rec = TurnRecord(turn=turn, chapter=game.campaign.chapter_number,
                         action=action, error=str(e))
        return game, narration, rec, True

    _print_narration(narration, print_full)
    if roll and print_rolls:
        print(f"  [ROLL] {roll.stat_name.upper()} {roll.stat_value} | "
              f"Action {roll.d1}+{roll.stat_value}={roll.action_score} vs "
              f"[{roll.c1}, {roll.c2}] -> {roll.result}")

    # 3. Record turn state
    rec = record_turn(game, turn, action, narration, roll)

    # 4. Momentum burn
    if burn_info:
        _handle_burn(provider, config, game, burn_info, burn_setting, style, rec)

    # 5. Director
    if director_ctx:
        try:
            run_deferred_director(provider, game, director_ctx)
            rec.director_ran = True
            sl = game.narrative.session_log
            trigger = sl[-1].director_trigger if sl else "?"
            print(f"  [DIRECTOR] Ran — trigger: {trigger}")
        except Exception as e:
            rec.director_error = str(e)

    # 6. State summary
    _print_state(game)

    # 7. Narration quality check
    quality_issues = check_narration_quality(narration)
    if quality_issues:
        rec.narration_quality = quality_issues
        for issue in quality_issues:
            print(f"  [QUALITY] {issue}")
            slog.narration_quality_issues.append(f"Turn {turn}: {issue}")

    # 8. NPC spatial consistency
    spatial_issues = check_npc_spatial_consistency(game, prev_npcs, narration)
    if spatial_issues:
        rec.spatial_issues = spatial_issues
        for issue in spatial_issues:
            print(f"  [SPATIAL] {issue}")
            slog.spatial_issues.append(f"Turn {turn}: {issue}")

    # 9. Invariants
    if do_invariants:
        violations = assert_game_state(game, turn)
        for v in violations:
            print(f"  !!  {v}")
            slog.violations.append(v)
        rec.violations = violations

    # 10. Validator report
    val = rec.validator
    if val and (val.retries > 0 or not val.passed):
        status = "PASS" if val.passed else "FAIL"
        print(f"  [VALIDATOR] {status} after {val.retries} retries")

    return game, narration, rec, False


# ── Correction test turn ──────────────────────────────────────

def _play_correction_turn(provider, config, game, narration, turn, persona, slog):
    """Send a ## correction to stress-test the correction pipeline."""
    print(f"  [CORRECTION TEST] Sending ## correction at turn {turn}")

    # Generate a plausible correction based on recent context
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
            provider, game, correction_text.lstrip("# ").strip(), config)
    except Exception as e:
        print(f"  [CORRECTION] Failed: {e}")
        traceback.print_exc()
        rec = TurnRecord(turn=turn, chapter=game.campaign.chapter_number,
                         action=correction_text, is_correction=True,
                         error=f"correction: {e}")
        slog.correction_tests.append({
            "turn": turn, "correction": correction_text,
            "success": False, "error": str(e),
        })
        return game, narration, rec, False  # don't end session on correction failure

    rec = record_turn(game, turn, correction_text, new_narration, None)
    rec.is_correction = True

    # Quality check on corrected narration
    quality_issues = check_narration_quality(new_narration)
    if quality_issues:
        rec.narration_quality = quality_issues
        for issue in quality_issues:
            slog.narration_quality_issues.append(f"Turn {turn} (correction): {issue}")

    # Director after correction
    if director_ctx:
        try:
            run_deferred_director(provider, game, director_ctx)
            rec.director_ran = True
        except Exception as e:
            rec.director_error = str(e)

    _print_narration(new_narration, full=False)
    _print_state(game)

    # Invariants after correction
    violations = assert_game_state(game, turn)
    if violations:
        rec.violations = violations
        for v in violations:
            print(f"  !!  {v}")
            slog.violations.append(v)

    slog.correction_tests.append({
        "turn": turn, "correction": correction_text,
        "success": True, "violations": violations,
        "quality_issues": quality_issues,
    })
    print("  [CORRECTION TEST] Completed successfully")

    return game, new_narration, rec, False


# ── Momentum burn ─────────────────────────────────────────────

def _handle_burn(provider, config, game, burn_info, burn_setting, style, rec):
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
    print(f"  [BURN] Available ({burn_info['roll'].result} -> "
          f"{burn_info['new_result']}) | Decision: {'BURN' if should_burn else 'skip'}")

    if should_burn:
        try:
            game, narration = process_momentum_burn(
                provider=provider, game=game,
                old_roll=burn_info["roll"],
                new_result=burn_info["new_result"],
                brain_data=burn_info["brain"],
                player_words=burn_info["player_words"],
                config=config,
                pre_snapshot=burn_info["pre_snapshot"],
                chaos_interrupt=burn_info.get("chaos_interrupt"),
            )
            print(f"  [BURN] Re-narrated: {narration.replace(chr(10), ' ')[:180]}...")
        except Exception as e:
            rec.burn_error = str(e)
            print(f"  [BURN] Failed: {e}")


# ── Chapter transition ────────────────────────────────────────

def _chapter_transition(provider, config, game, chat_messages, username,
                        save_out, chapter_num, chapter_idx, max_chapters, slog):
    """Returns (game, narration, chat_messages, should_break)."""
    print(f"\n{SEPARATOR}\n  GENERATING EPILOGUE — Chapter {chapter_num}\n{SEPARATOR}")
    try:
        game, epilogue = generate_epilogue(provider, game, config)
        chat_messages.append({"role": "assistant", "content": epilogue, "epilogue": True})
        _print_narration(epilogue, full=True)
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


# ── Helpers ───────────────────────────────────────────────────

def _print_narration(narration: str, full: bool) -> None:
    if full:
        print(f"\n  [NARRATOR]\n{narration}\n")
    else:
        excerpt = narration.replace("\n", " ").strip()[:220]
        print(f"\n  [NARRATOR] {excerpt}{'...' if len(narration) > 220 else ''}")


def _print_state(game: GameState) -> None:
    res = game.resources
    print(f"  [STATE] H:{res.health} Sp:{res.spirit} Su:{res.supply} "
          f"Mo:{res.momentum} Chaos:{game.world.chaos_factor} "
          f"Scene:{game.narrative.scene_count}")


def _try_save(game, username, chat_messages, save_out) -> None:
    try:
        save_game(game, username, chat_messages, save_out)
        print(f"  [SAVE] Saved to '{save_out}'")
    except Exception as e:
        print(f"  [SAVE] Failed: {e}")


def _game_context_dict(game: GameState) -> dict:
    return {
        "setting_id": game.setting_id,
        "setting_genre": game.setting_genre,
        "setting_tone": game.setting_tone,
        "character_concept": game.character_concept,
        "pronouns": game.pronouns,
        "paths": game.paths,
        "backstory": game.backstory,
        "background_vow": game.background_vow,
        "stats": {"edge": game.edge, "heart": game.heart, "iron": game.iron,
                  "shadow": game.shadow, "wits": game.wits},
    }


def _final_state_dict(game: GameState) -> dict:
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


def _log_opening_validator(game: GameState, slog: SessionLog) -> None:
    if not game.narrative.session_log:
        return
    val = game.narrative.session_log[-1].validator
    if not val:
        return
    slog.opening_validator = ValidatorRecord(
        passed=val.get("passed", True),
        retries=val.get("retries", 0),
        violations=val.get("violations", []),
    )


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


def _aggregate_validator_stats(slog: SessionLog) -> dict:
    total = failed = retried = total_retries = 0
    violation_counts: dict[str, int] = {}
    for t in slog.turns:
        if t.validator:
            total += 1
            if t.validator.retries > 0:
                retried += 1
                total_retries += t.validator.retries
            if not t.validator.passed:
                failed += 1
            for v in t.validator.violations:
                violation_counts[v] = violation_counts.get(v, 0) + 1
    return {
        "turns_checked": total,
        "turns_retried": retried,
        "turns_failed": failed,
        "total_retries": total_retries,
        "top_violations": sorted(violation_counts.items(), key=lambda x: -x[1])[:10],
    }


def _aggregate_quality_stats(slog: SessionLog) -> dict:
    """Aggregate narration quality and spatial issues into pattern counts."""
    quality_counts: dict[str, int] = {}
    for issue in slog.narration_quality_issues:
        # Strip turn prefix to count by type
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


def _print_summary(slog: SessionLog, game: GameState) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  Session complete: {slog.ended_reason}")
    print(f"  Chapters played : {len(slog.chapters)}")
    print(f"  Total turns     : {slog.total_turns}")
    print(f"  Violations      : {len(slog.violations)}")
    print(f"  Final scene     : {game.narrative.scene_count}")
    print(f"  Final health    : {game.resources.health} | spirit: {game.resources.spirit}")

    vs = slog.validator_summary
    if vs.get("turns_checked", 0) > 0:
        print(f"  Validator       : {vs['turns_checked']} checked, {vs['turns_retried']} retried "
              f"({vs['total_retries']} total), {vs['turns_failed']} still failed")
        for violation, count in vs.get("top_violations", [])[:5]:
            print(f"    {count}x: {violation[:100]}")

    qs = slog.quality_summary
    if qs.get("narration_quality_total", 0) > 0:
        print(f"  Narration leaks : {qs['narration_quality_total']}")
        for issue_type, count in qs.get("top_quality_issues", [])[:5]:
            print(f"    {count}x: {issue_type}")

    if qs.get("spatial_issues_total", 0) > 0:
        print(f"  Spatial issues  : {qs['spatial_issues_total']}")

    if qs.get("chapter_continuity_total", 0) > 0:
        print(f"  Continuity      : {qs['chapter_continuity_total']}")

    ct = qs.get("correction_tests_total", 0)
    if ct > 0:
        cf = qs.get("correction_tests_failed", 0)
        print(f"  Corrections     : {ct} tested, {cf} failed")

    bs = slog.burn_stats
    if bs.get("offered", 0) > 0:
        print(f"  Burns           : {bs['offered']} offered, {bs['taken']} taken, {bs['failed']} failed")

    print(SEPARATOR)
