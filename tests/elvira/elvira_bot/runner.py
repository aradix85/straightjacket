from __future__ import annotations

import copy
import json
import logging
import random as _random
import time
import traceback
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from typing_extensions import override

from straightjacket.engine.ai.api_client import get_provider
from straightjacket.engine.ai.provider_base import AIUnavailableError
from straightjacket.engine.ai.sentence_stream import SentenceStream
from straightjacket.engine.config_loader import VERSION, model_for_role, narration_language, provider_for_role
from straightjacket.engine.correction import process_correction
from straightjacket.engine.game import (
    check_startup,
    generate_epilogue,
    prepare_succession,
    process_momentum_burn,
    process_turn,
    run_deferred_director,
    start_new_chapter,
    start_new_game,
    start_succession_with_character,
)
from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.gamemaster.questions import install_answers
from straightjacket.engine.persistence import delete_save, load_game, save_game
from straightjacket.engine.ruleset import answers as ironsworn
from straightjacket.engine.setting.packages import list_packages, load_package
from straightjacket.engine.user_management import create_user
from tests.elvira.elvira_bot.ai_helpers import (
    ask_bot,
    available_styles,
    bot_label,
    build_turn_context,
    configure_bot,
    decide_burn_momentum,
    get_persona,
)
from tests.elvira.elvira_bot.console import say
from tests.elvira.elvira_bot.coverage import Coverage, world_view
from tests.elvira.elvira_bot.creation import roll_character
from tests.elvira.elvira_bot.display import print_narration, print_state, print_summary
from tests.elvira.elvira_bot.faults import NarratorOutage
from tests.elvira.elvira_bot.fixed_results import fixed_result
from tests.elvira.elvira_bot.invariants import assert_game_state, check_turn_replacement
from tests.elvira.elvira_bot.judge import consequences_in, judge_turn, revelation_in
from tests.elvira.elvira_bot.models import ChapterRecord, SessionLog, TurnRecord
from tests.elvira.elvira_bot.quality_checks import (
    check_chapter_continuity,
    check_narration_quality,
    check_npc_spatial_consistency,
)
from tests.elvira.elvira_bot.recorder import record_turn, snapshot_npcs
from tests.elvira.elvira_bot.report import write_report
from tests.elvira.elvira_bot.scenarios import fixed_result_of_turn, prepare_scenario
from tests.elvira.elvira_bot.tokens import TokenMeter

if TYPE_CHECKING:
    from straightjacket.engine.ai.provider_base import AIProvider
    from straightjacket.engine.game import (
        BurnOffer,
        DirectorCall,
    )
    from straightjacket.engine.models import GameState, RollResult, TurnSnapshot
    from tests.elvira.elvira_bot.coverage import WorldView
    from tests.elvira.elvira_bot.models import NpcSnapshot

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"
SEPARATOR = "=" * 62


CORRECTION_TEST_INTERVAL = 8


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        say(f"[ERROR] Config not found: {path}")
        raise SystemExit(1)
    with path.open(encoding="utf-8") as f:
        config: dict[str, Any] = yaml.safe_load(f)
    return config


def selectable_settings() -> list[str]:
    return [s for s in list_packages() if load_package(s).playable]


def _role_label(role: str) -> str:
    return f"{role}={provider_for_role(role)}/{model_for_role(role)}"


@dataclass(frozen=True)
class SessionSettings:
    auto_mode: bool
    username: str
    game_cfg: dict[str, Any]
    max_chapters: int
    max_turns: int
    save_every: int
    save_out: str
    clean_before: bool
    style: str
    burn_setting: str
    scenario_name: str
    scenario: dict[str, Any] | None
    inject_turn: int
    log_file: Path
    print_full: bool
    print_rolls: bool
    do_invariants: bool
    judge_cfg: dict[str, Any] | None
    prices: dict[str, Any]
    succession_enabled: bool
    full_debug: bool

    @property
    def planned_turns(self) -> int:
        return self.max_chapters * self.max_turns


@dataclass
class RunState:
    settings: SessionSettings
    provider: TokenMeter
    persona: str
    slog: SessionLog
    coverage: Coverage
    events: _EventCapture
    game: GameState
    narration: str
    total_turns: int
    prev_npcs: list[NpcSnapshot] | None


@dataclass
class _Run(RunState):
    chat_messages: list[dict[str, Any]]


class _StreamCapture:
    def __init__(self) -> None:
        self.sentences: list[str] = []
        self.first_at: float | None = None
        self.started = time.monotonic()
        self.stream = SentenceStream(self._on_sentence)

    def _on_sentence(self, text: str) -> None:
        if self.first_at is None:
            self.first_at = time.monotonic() - self.started
        self.sentences.append(text)


@dataclass
class _Played:
    narration: str
    roll: RollResult | None
    burn_offer: BurnOffer | None
    director_ctx: DirectorCall | None
    world_before: WorldView
    warnings_before: int
    capture: _StreamCapture


SESSION_ENDINGS = frozenset({"game_over", "engine_error"})


def session_settings(bot_cfg: dict[str, Any], *, auto_override: bool, turns_override: int | None) -> SessionSettings:
    session_cfg, behavior, log_cfg = bot_cfg["session"], bot_cfg["bot_behavior"], bot_cfg["logging"]
    style = behavior["style"] or _random.choice(available_styles())
    scenario_name, scenario = _scenario_spec(bot_cfg)
    setting_id = _setting_of(bot_cfg["game"], scenario)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    return SessionSettings(
        auto_mode=auto_override or bot_cfg["auto_mode"],
        username=bot_cfg["username"],
        game_cfg={**bot_cfg["game"], "setting_id": setting_id},
        max_chapters=session_cfg["max_chapters"],
        max_turns=turns_override or session_cfg["max_turns"],
        save_every=session_cfg["save_every_n_turns"],
        save_out=session_cfg["save_name_output"],
        clean_before=session_cfg["clean_before_run"],
        style=style,
        burn_setting=behavior["burn_momentum"],
        scenario_name=scenario_name,
        scenario=scenario,
        inject_turn=session_cfg["inject_ai_failure_turn"],
        log_file=_log_stem(Path(log_cfg["log_file"]), setting_id, style, scenario_name, timestamp),
        print_full=log_cfg["print_full_narration"],
        print_rolls=log_cfg["print_roll_details"],
        do_invariants=log_cfg["assert_state_invariants"],
        judge_cfg=bot_cfg["judge"] if bot_cfg["judge"]["enabled"] else None,
        prices=bot_cfg["prices"],
        succession_enabled=session_cfg["succession_on_game_over"],
        full_debug=log_cfg["full_debug_log"],
    )


def new_session_log(bot_cfg: dict[str, Any], settings: SessionSettings) -> SessionLog:
    return SessionLog(
        config={
            **bot_cfg,
            "game": settings.game_cfg,
            "bot_behavior": {**bot_cfg["bot_behavior"], "style": settings.style},
        },
        engine_version=VERSION,
        style=settings.style,
    )


def run_session(bot_cfg: dict[str, Any], *, auto_override: bool, turns_override: int | None) -> SessionLog:
    install_answers(ironsworn)
    settings = session_settings(bot_cfg, auto_override=auto_override, turns_override=turns_override)
    coverage = Coverage()
    events = _EventCapture(bot_cfg["logging"]["event_prefixes"])
    logging.getLogger("rpg_engine").addHandler(events)

    check_startup()
    configure_bot(bot_cfg["ai"])
    provider = TokenMeter(get_provider())
    create_user(settings.username)
    if settings.clean_before and not settings.game_cfg["load_existing"]:
        delete_save(settings.username, settings.save_out)
    persona = get_persona(settings.style)

    slog = new_session_log(bot_cfg, settings)
    _print_banner(settings)
    game, narration, chat_messages = _setup_game(
        provider, settings.username, settings.game_cfg, auto_mode=settings.auto_mode
    )
    run = _Run(
        settings=settings,
        provider=provider,
        persona=persona,
        slog=slog,
        coverage=coverage,
        events=events,
        game=game,
        narration=narration,
        chat_messages=chat_messages,
        total_turns=0,
        prev_npcs=None,
    )
    _log_story_blueprint(game, slog)
    _apply_scenario(game, settings.scenario_name, settings.scenario, slog)
    if game.game_over and settings.succession_enabled:
        _continue_by_succession(run)
    _play_chapters(run)
    _finish(run)
    return slog


def _print_banner(settings: SessionSettings) -> None:
    say(f"\n{SEPARATOR}")
    say(f"  Straightjacket — Elvira Test Bot — {settings.game_cfg['setting_id']}, {settings.style}")
    say(
        f"  Auto: {'YES' if settings.auto_mode else 'NO'} | Turns/ch: {settings.max_turns} | "
        f"Chapters: {settings.max_chapters} | Lang: {narration_language()}"
    )
    roles = ", ".join(_role_label(role) for role in ("narrator", "brain", "director"))
    say(f"  Engine: v{VERSION} | {roles}")
    judges = " and judges" if settings.judge_cfg else ""
    say(f"  Elvira: {bot_label()} plays{judges} | Injected AI failure on turn {settings.inject_turn}")
    say(SEPARATOR)


def story_complete(game: GameState) -> bool:
    bp = game.narrative.story_blueprint
    return bool(bp and bp.story_complete and not game.campaign.epilogue_dismissed)


def _continue_by_succession(run: _Run) -> bool:
    run.game, narration = _play_succession(run.provider, run.game, run.settings.game_cfg, run.slog, run.coverage)
    if "error" in run.slog.succession:
        return False
    run.narration = narration
    run.chat_messages.append({"role": "assistant", "content": narration})
    return True


def _play_chapters(run: _Run) -> None:
    for chapter_idx in range(run.settings.max_chapters):
        ch_rec = _play_chapter(run, chapter_idx)
        run.slog.chapters.append(ch_rec)
        if ch_rec.ended_reason in SESSION_ENDINGS or not story_complete(run.game):
            return
        if _next_chapter(run, chapter_num=ch_rec.chapter, chapter_idx=chapter_idx):
            return


def _play_chapter(run: _Run, chapter_idx: int) -> ChapterRecord:
    ch_rec = ChapterRecord(chapter=run.game.campaign.chapter_number)
    chapter_start = run.total_turns
    if chapter_idx > 0:
        say(f"\n{SEPARATOR}")
        say(f"  CHAPTER {ch_rec.chapter} — {run.game.player_name} at {run.game.world.current_location}")
        say(SEPARATOR)
    ch_rec.ended_reason = _play_chapter_turns(run)
    ch_rec.turns_played = run.total_turns - chapter_start
    return ch_rec


def _play_chapter_turns(run: _Run) -> str:
    prev_action = ""
    for _ in range(run.settings.max_turns):
        turn_rec, session_ended = _play_next_turn(run, prev_action)
        prev_action = turn_rec.action or ""
        _keep_turn(run, turn_rec)
        if not session_ended and _succession_due(run) and _continue_by_succession(run):
            continue
        if session_ended or run.game.game_over:
            return "game_over" if run.game.game_over else "engine_error"
        if story_complete(run.game):
            return "story_complete"
    return "max_turns_reached"


def _succession_due(run: _Run) -> bool:
    return run.game.game_over and run.settings.succession_enabled and not run.slog.succession


def _play_next_turn(run: _Run, prev_action: str) -> tuple[TurnRecord, bool]:
    run.total_turns += 1
    turn = run.total_turns
    say(f"\n{SEPARATOR}\n  TURN {turn}/{run.settings.planned_turns}\n{SEPARATOR}")
    if is_correction_turn(turn, run.game):
        return _play_correction_turn(run, turn), False
    return _play_turn(run, turn, prev_action)


def _keep_turn(run: _Run, turn_rec: TurnRecord) -> None:
    run.prev_npcs = list(turn_rec.npcs)
    run.slog.turns.append(turn_rec)
    run.chat_messages.append({"role": "user", "content": turn_rec.action})
    run.chat_messages.append({"role": "assistant", "content": run.narration})
    s = run.settings
    if run.total_turns % s.save_every == 0:
        _save_and_verify(run.game, s.username, run.chat_messages, s.save_out, slog=run.slog, coverage=run.coverage)


def _next_chapter(run: _Run, *, chapter_num: int, chapter_idx: int) -> bool:
    pre_chapter_npcs = [n for n in snapshot_npcs(run.game) if n.status in gm().npc_status_groups.in_play]
    should_break = _chapter_transition(run, chapter_num=chapter_num, chapter_idx=chapter_idx)
    if not should_break and pre_chapter_npcs:
        for issue in check_chapter_continuity(run.game, pre_chapter_npcs):
            say(f"  [CONTINUITY] {issue}")
            run.slog.chapter_continuity_issues.append(f"Ch{chapter_num}→{chapter_num + 1}: {issue}")
    return should_break


def is_correction_turn(turn: int, game: GameState) -> bool:
    return turn > 1 and turn % CORRECTION_TEST_INTERVAL == 0 and game.last_turn_snapshot is not None


def decide_burn(settings: SessionSettings, game: GameState, current: str, upgrade: str) -> bool:
    if settings.burn_setting == "always":
        return True
    if settings.burn_setting == "never":
        return False
    try:
        return decide_burn_momentum(game, current, upgrade, settings.style)
    except Exception:
        return False


def burn_stats(slog: SessionLog) -> dict[str, int]:
    offered = [t for t in slog.turns if t.burn_offered]
    return {
        "offered": len(offered),
        "taken": sum(1 for t in offered if t.burn_taken),
        "failed": sum(1 for t in offered if t.burn_error),
    }


def _finish(run: _Run) -> None:
    slog, coverage, game, s = run.slog, run.coverage, run.game, run.settings
    slog.total_turns = run.total_turns
    slog.ended_reason = (
        slog.ended_reason
        if slog.ended_reason != "unknown"
        else (slog.chapters[-1].ended_reason if slog.chapters else "complete")
    )
    slog.character = {"name": game.player_name, "concept": game.character_concept, "setting": game.setting_id}
    slog.quality_summary = _aggregate_quality_stats(slog)
    slog.token_summary = aggregate_token_stats(slog)
    slog.burn_stats = burn_stats(slog)

    print_summary(slog, game)
    _save_and_verify(game, s.username, run.chat_messages, s.save_out, slog=slog, coverage=coverage)
    coverage.hit("burn_offered", slog.burn_stats["offered"])
    coverage.hit("burn_taken", slog.burn_stats["taken"])
    coverage.hit("correction", len(slog.correction_tests))
    coverage.hit("chapter_transition", max(0, len(slog.chapters) - 1))
    if any(ch.ended_reason == "game_over" for ch in slog.chapters):
        coverage.hit("game_over")
    slog.coverage = coverage.summary()
    _finish_scenario(slog, coverage)
    logging.getLogger("rpg_engine").removeHandler(run.events)
    slog.engine_warnings = list(run.events.warnings)
    write_logs(slog, coverage, s)


def write_logs(slog: SessionLog, coverage: Coverage, settings: SessionSettings) -> None:
    report_path = write_report(slog, coverage, RUNS_DIR / f"{settings.log_file.stem}.md", settings.prices)
    say(f"  [REPORT] {report_path}")

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = RUNS_DIR / settings.log_file
    log_path.write_text(json.dumps(slog.to_diagnostic_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    say(f"  [LOG] Session log written to: {log_path}")

    if settings.full_debug:
        full_path = log_path.with_stem(f"{log_path.stem}_full")
        full_path.write_text(json.dumps(slog.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        say(f"  [LOG] Full debug log written to: {full_path}")


def _setup_game(
    provider: AIProvider, username: str, game_cfg: dict[str, Any], *, auto_mode: bool
) -> tuple[GameState, str, list[dict[str, Any]]]:
    if not auto_mode and game_cfg["load_existing"]:
        save_name = game_cfg["save_name"]
        game, chat_messages = load_game(username, save_name)
        if not game:
            missing = f"Save '{save_name}' not found for user '{username}'"
            raise SystemExit(missing)
        narration = ""
        for msg in reversed(chat_messages):
            if msg.get("role") == "assistant" and not msg.get("recap"):
                narration = msg.get("content", "")
                break
        say(
            f"[SETUP] Loaded: {game.player_name} (Ch{game.campaign.chapter_number}, Scene {game.narrative.scene_count})"
        )
        return game, narration, chat_messages

    creation_data = roll_character(game_cfg["setting_id"], game_cfg)

    try:
        game, narration = start_new_game(provider, creation_data)
    except Exception as e:
        say(f"[ERROR] start_new_game failed: {e}")
        traceback.print_exc()
        raise SystemExit(1) from e

    say(f"[SETUP] Character: {game.player_name} at {game.world.current_location}")
    return game, narration, [{"role": "assistant", "content": narration}]


def _play_turn(run: _Run, turn: int, prev_action: str) -> tuple[TurnRecord, bool]:
    s = run.settings
    directive_key = _directive(s.scenario, run.coverage, turn, s.planned_turns)
    context = build_turn_context(run.game, run.narration, turn, prev_action=prev_action, directive_key=directive_key)
    try:
        action = ask_bot(run.persona, context, max_tokens=500)
    except Exception as e:
        say(f"[ERROR] Bot decision failed: {e}")
        return TurnRecord(turn=turn, chapter=run.game.campaign.chapter_number, error=str(e)), True

    say(f"\n  [PLAYER] {action}")
    run.events.lines.clear()
    played = _engine_turn(run, turn, action)
    if isinstance(played, TurnRecord):
        return played, not played.rolled_back
    return _record_played_turn(run, turn, action, played), False


def _engine_turn(run: _Run, turn: int, action: str) -> _Played | TurnRecord:
    game = run.game
    inject_failure = turn == run.settings.inject_turn
    fixed = fixed_result_of_turn(run.settings.scenario, turn)
    warnings_before = len(run.events.warnings)
    world_before = world_view(game)
    capture = _StreamCapture()
    snapshot, last_snapshot, before_state = game.snapshot(), game.last_turn_snapshot, game.to_dict()
    run.provider.narrator_prompt = ""
    turn_provider = NarratorOutage(run.provider) if inject_failure else run.provider
    try:
        with fixed_result(fixed) if fixed else nullcontext():
            narration, roll, burn_offer, director_ctx = process_turn(turn_provider, game, action, capture.stream)
    except AIUnavailableError as e:
        _restore(game, snapshot, last_snapshot)
        rec = TurnRecord(
            turn=turn,
            chapter=game.campaign.chapter_number,
            action=action,
            rolled_back=True,
            token_usage=run.provider.drain(),
        )
        _check_rollback(game, before_state, turn, e, injected=inject_failure, slog=run.slog, coverage=run.coverage)
        if inject_failure:
            del run.events.warnings[warnings_before:]
        return rec
    except Exception as e:
        say(f"[ERROR] process_turn failed: {e}")
        traceback.print_exc()
        return TurnRecord(turn=turn, chapter=game.campaign.chapter_number, action=action, error=str(e))
    return _Played(
        narration=narration,
        roll=roll,
        burn_offer=burn_offer,
        director_ctx=director_ctx,
        world_before=world_before,
        warnings_before=warnings_before,
        capture=capture,
    )


def _record_played_turn(run: _Run, turn: int, action: str, played: _Played) -> TurnRecord:
    game, s, roll = run.game, run.settings, played.roll
    previous_narration = run.narration
    print_narration(played.narration, full=s.print_full)
    if roll and s.print_rolls:
        say(
            f"  [ROLL] {roll.stat_name.upper()} {roll.stat_value} | "
            f"Action {roll.d1}+{roll.stat_value}={roll.action_score} vs "
            f"[{roll.c1}, {roll.c2}] -> {roll.result}"
        )

    rec = record_turn(game, turn, action, played.narration, roll)
    rec.turn_secs = round(time.monotonic() - played.capture.started, 1)
    _record_stream(rec, played.capture, played.narration, slog=run.slog, coverage=run.coverage)
    result, played_move = game.narrative.session_log[-1].result, game.narrative.session_log[-1].move
    match = bool(roll and roll.match)
    run.coverage.observe_turn(
        played.world_before, world_view(game), result, match=match, move=roll.move if roll else ""
    )
    narration, result = _burn_and_direct(run, rec, turn, played, result)

    print_state(game)
    check_turn(game, narration, turn, run.prev_npcs, do_invariants=s.do_invariants, slog=run.slog, rec=rec)
    rec.engine_events = list(run.events.lines)
    rec.engine_warnings = run.events.warnings[played.warnings_before :]
    run.coverage.observe_events(rec.engine_events)

    rec.revelation = revelation_in(run.provider.narrator_prompt)
    if s.judge_cfg:
        rec.judge = judge_turn(
            s.judge_cfg,
            game,
            action,
            narration,
            result,
            match=match,
            previous=previous_narration,
            move_id=played_move,
            revelation=rec.revelation,
            consequences=consequences_in(run.provider.narrator_prompt),
        )
        _print_audit(rec.judge)
    run.narration = narration
    return rec


def _burn_and_direct(run: _Run, rec: TurnRecord, turn: int, played: _Played, result: str) -> tuple[str, str]:
    narration, director_ctx = played.narration, played.director_ctx
    if played.burn_offer:
        narration, director_ctx = _handle_burn(run, played.burn_offer, narration, director_ctx, rec=rec, turn=turn)
        if rec.burn_taken and not rec.burn_error:
            result = played.burn_offer.new_result
    if director_ctx:
        try:
            run_deferred_director(run.provider, run.game, director_ctx)
            rec.director_ran = True
            run.coverage.hit("director")
            say("  [DIRECTOR] Ran")
        except Exception as e:
            rec.director_error = str(e)
    rec.token_usage = run.provider.drain()
    return narration, result


def check_turn(
    game: GameState,
    narration: str,
    turn: int,
    prev_npcs: list[NpcSnapshot] | None,
    *,
    do_invariants: bool,
    slog: SessionLog,
    rec: TurnRecord,
) -> None:
    quality_issues = check_narration_quality(narration)
    if quality_issues:
        rec.narration_quality = quality_issues
        for issue in quality_issues:
            say(f"  [QUALITY] {issue}")
            slog.narration_quality_issues.append(f"Turn {turn}: {issue}")

    spatial_issues = check_npc_spatial_consistency(game, prev_npcs, narration)
    if spatial_issues:
        rec.spatial_issues = spatial_issues
        for issue in spatial_issues:
            say(f"  [SPATIAL] {issue}")
            slog.spatial_issues.append(f"Turn {turn}: {issue}")

    if do_invariants:
        violations = assert_game_state(game, turn)
        for v in violations:
            say(f"  !!  {v}")
            slog.violations.append(v)
        rec.violations = violations


def _scenario_spec(bot_cfg: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    name = bot_cfg["session"]["scenario"]
    return name, (bot_cfg["scenarios"][name] if name else None)


def _setting_of(game_cfg: dict[str, Any], scenario: dict[str, Any] | None) -> str:
    if scenario is not None and "setting" in scenario:
        return str(scenario["setting"])
    return str(game_cfg["setting_id"]) or _random.choice(selectable_settings())


def _log_stem(base: Path, setting_id: str, style: str, scenario_name: str, timestamp: str) -> Path:
    parts = [base.stem, setting_id, style, *([scenario_name] if scenario_name else []), timestamp]
    return base.with_stem("_".join(parts))


def _apply_scenario(game: GameState, name: str, spec: dict[str, Any] | None, slog: SessionLog) -> None:
    if spec is None:
        return
    notes = prepare_scenario(game, spec)
    slog.scenario = {"name": name, "prepared": notes, "expect": list(spec["expect"])}
    say(f"  [SCENARIO] {name}: {'; '.join(notes) or 'nothing to prepare'}")


def _directive(spec: dict[str, Any] | None, coverage: Coverage, turn: int, max_turns: int) -> str | None:
    if spec is not None and "directive" in spec:
        directives: list[str] = spec["directive"]
        return directives[min(turn, len(directives)) - 1]
    return coverage.steer(turn, max_turns)


def _finish_scenario(slog: SessionLog, coverage: Coverage) -> None:
    if not slog.scenario:
        return
    exercised = set(coverage.exercised())
    slog.scenario["reached"] = [t for t in slog.scenario["expect"] if t in exercised]
    slog.scenario["missed"] = [t for t in slog.scenario["expect"] if t not in exercised]


def _restore(game: GameState, snapshot: TurnSnapshot, last_snapshot: TurnSnapshot | None) -> None:
    game.restore(snapshot)
    game.last_turn_snapshot = last_snapshot


def _check_rollback(
    game: GameState,
    before_state: dict[str, Any],
    turn: int,
    error: AIUnavailableError,
    *,
    injected: bool,
    slog: SessionLog,
    coverage: Coverage,
) -> None:
    after_state = game.to_dict()
    changed = sorted(key for key in before_state if before_state[key] != after_state[key])
    if not injected:
        slog.rollback_issues.append(f"Turn {turn}: AI unavailable ({error}); turn rolled back, play continued")
    if changed:
        slog.rollback_issues.append(f"Turn {turn}: rollback left {', '.join(changed)} changed")
    else:
        coverage.hit("ai_failure_rollback")
    kind = "Injected" if injected else "Real"
    say(f"  [ROLLBACK] {kind} AI failure: {error}; state restored{' with differences' if changed else ''}")


def _record_stream(
    rec: TurnRecord, capture: _StreamCapture, narration: str, *, slog: SessionLog, coverage: Coverage
) -> None:
    rec.stream_first_sentence_secs = round(capture.first_at, 1) if capture.first_at is not None else None
    rec.stream_sentences = len(capture.sentences)
    rec.stream_complete = capture.stream.complete
    rec.stream_matches = _norm(" ".join(capture.sentences)) == _norm(narration)
    if capture.stream.complete:
        coverage.hit("stream_complete")
        if not rec.stream_matches:
            slog.stream_issues.append(f"Turn {rec.turn}: streamed text differs from the final narration")


def _print_audit(verdict: dict[str, Any]) -> None:
    if "overall" in verdict:
        say(f"  [AUDIT] {verdict['overall']}/10: {verdict['weakness']}")
    else:
        say(f"  [AUDIT] no verdict: {verdict['error']}")


class _EventCapture(logging.Handler):
    def __init__(self, prefixes: list[str]) -> None:
        super().__init__()
        self.prefixes = tuple(prefixes)
        self.lines: list[str] = []
        self.warnings: list[str] = []

    @override
    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if message.startswith(self.prefixes):
            self.lines.append(message)
        if record.levelno >= logging.WARNING:
            self.warnings.append(f"{record.levelname}: {message}")


def _norm(text: str) -> str:
    return " ".join(text.split())


def _save_and_verify(
    game: GameState,
    username: str,
    chat_messages: list[dict[str, Any]],
    save_out: str,
    *,
    slog: SessionLog,
    coverage: Coverage,
) -> None:
    _try_save(game, username, chat_messages, save_out)
    try:
        loaded, _messages = load_game(username, save_out)
    except Exception as e:
        slog.save_roundtrip_issues.append(
            f"scene {game.narrative.scene_count}: save '{save_out}' failed to load: {type(e).__name__}: {e}"
        )
        return
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
    provider: AIProvider, game: GameState, game_cfg: dict[str, Any], slog: SessionLog, coverage: Coverage
) -> tuple[GameState, str]:
    coverage.hit("game_over")
    try:
        prepare_succession(game)
        creation_data = roll_character(game.setting_id, game_cfg)
        narration = start_succession_with_character(provider, game, creation_data)
    except Exception as e:
        slog.succession = {"error": f"{type(e).__name__}: {e}"[:300]}
        say(f"  [SUCCESSION] Failed: {e}")
        return game, ""
    slog.succession = {"new_character": game.player_name}
    coverage.hit("succession")
    say(f"  [SUCCESSION] Continuing as {game.player_name}")
    return game, narration


def _play_correction_turn(run: _Run, turn: int) -> TurnRecord:
    provider, game, slog = run.provider, run.game, run.slog
    say(f"  [CORRECTION TEST] Sending ## correction at turn {turn}")

    correction_prompts = [
        "## I didn't mean to do that — I wanted to just observe, not act",
        "## That's not what I said — I was asking a question, not making a statement",
        "## I wanted to talk to them, not confront them",
        "## I was being cautious, not aggressive",
    ]
    correction_text = _random.choice(correction_prompts)
    say(f"\n  [PLAYER] {correction_text}")

    before = copy.deepcopy(game)
    try:
        new_narration, _burn_offer, director_ctx = process_correction(
            provider, game, correction_text.lstrip("# ").strip()
        )
    except Exception as e:
        say(f"  [CORRECTION] Failed: {e}")
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
        return rec

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
    rec.token_usage = provider.drain()

    print_narration(new_narration, full=False)
    print_state(game)

    violations = assert_game_state(game, turn)
    violations += check_turn_replacement(before, game, new_narration, turn, "correction", keeps_location=False)
    if violations:
        rec.violations = violations
        for v in violations:
            say(f"  !!  {v}")
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
    say("  [CORRECTION TEST] Completed successfully")
    run.narration = new_narration
    return rec


def _handle_burn(
    run: _Run,
    offer: BurnOffer,
    narration: str,
    director_ctx: DirectorCall | None,
    *,
    rec: TurnRecord,
    turn: int,
) -> tuple[str, DirectorCall | None]:
    provider, game, slog = run.provider, run.game, run.slog
    should_burn = decide_burn(run.settings, game, offer.roll.result, offer.new_result)

    rec.burn_offered = offer.new_result
    rec.burn_taken = should_burn
    say(
        f"  [BURN] Available ({offer.roll.result} -> "
        f"{offer.new_result}) | Decision: {'BURN' if should_burn else 'skip'}"
    )

    if should_burn:
        before = copy.deepcopy(game)
        snapshot, last_snapshot = game.snapshot(), copy.deepcopy(game.last_turn_snapshot)
        try:
            narration, director_ctx = process_momentum_burn(provider, game, offer)
            say(f"  [BURN] Re-narrated: {narration.replace(chr(10), ' ')[:180]}...")
        except Exception as e:
            _restore(game, snapshot, last_snapshot)
            rec.burn_error = str(e)
            say(f"  [BURN] Failed: {e}")
            return narration, director_ctx
        violations = check_turn_replacement(before, game, narration, turn, "momentum burn", keeps_location=True)
        snap_roll = game.last_turn_snapshot.roll if game.last_turn_snapshot else None
        if snap_roll is None or snap_roll.result != offer.new_result:
            violations.append(f"[TURN {turn}] momentum burn: turn snapshot does not hold the burned result")
        if game.narrative.session_log and game.narrative.session_log[-1].result != offer.new_result:
            violations.append(f"[TURN {turn}] momentum burn: last session log entry is not the burned result")
        for v in violations:
            say(f"  !!  {v}")
            slog.violations.append(v)
        rec.violations.extend(violations)

    return narration, director_ctx


def _chapter_transition(run: _Run, *, chapter_num: int, chapter_idx: int) -> bool:
    provider, game, slog = run.provider, run.game, run.slog
    say(f"\n{SEPARATOR}\n  GENERATING EPILOGUE — Chapter {chapter_num}\n{SEPARATOR}")
    try:
        epilogue = generate_epilogue(provider, game)
        run.chat_messages.append({"role": "assistant", "content": epilogue, "epilogue": True})
        print_narration(epilogue, full=True)
    except Exception as e:
        tb = traceback.format_exc()
        say(f"  [EPILOGUE] Failed: {e}")
        say(tb)
        slog.ended_reason = f"epilogue_error: {type(e).__name__}: {e}"
        slog.violations.append(f"CRASH in generate_epilogue: {tb[-500:]}")
        run.narration = ""
        return True

    save_game(game, run.settings.username, run.chat_messages, run.settings.save_out)

    if chapter_idx + 1 >= run.settings.max_chapters:
        slog.ended_reason = "max_chapters_reached"
        run.narration = ""
        return True

    say(f"\n{SEPARATOR}\n  STARTING CHAPTER {chapter_num + 1}\n{SEPARATOR}")
    try:
        narration = start_new_chapter(provider, game)
    except Exception as e:
        tb = traceback.format_exc()
        say(f"  [CHAPTER] Failed: {e}")
        say(tb)
        slog.ended_reason = f"chapter_transition_error: {type(e).__name__}: {e}"
        slog.violations.append(f"CRASH in start_new_chapter: {tb[-500:]}")
        run.narration = ""
        return True
    run.narration = narration
    run.chat_messages = [{"role": "assistant", "content": narration}]
    say(f"  [CHAPTER] Chapter {game.campaign.chapter_number} at {game.world.current_location}")
    return False


def _try_save(game: GameState, username: str, chat_messages: list[dict[str, Any]], save_out: str) -> None:
    try:
        save_game(game, username, chat_messages, save_out)
        say(f"  [SAVE] Saved to '{save_out}'")
    except Exception as e:
        say(f"  [SAVE] Failed: {e}")


def _log_story_blueprint(game: GameState, slog: SessionLog) -> None:
    bp = game.narrative.story_blueprint
    if not bp:
        return
    slog.story_blueprint = {
        "central_conflict": bp.central_conflict,
        "thematic_thread": bp.thematic_thread,
        "acts": [a.to_dict() for a in bp.acts],
    }


def _aggregate_quality_stats(slog: SessionLog) -> dict[str, Any]:
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


def aggregate_token_stats(slog: SessionLog) -> dict[str, Any]:
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
