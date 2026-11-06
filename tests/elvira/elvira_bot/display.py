from __future__ import annotations

from typing import TYPE_CHECKING, Any

from straightjacket.engine.ruleset.bond import get_npc_bond
from tests.elvira.elvira_bot.console import say

if TYPE_CHECKING:
    from straightjacket.engine.models import GameState
    from tests.elvira.elvira_bot.models import SessionLog


def print_narration(narration: str, *, full: bool) -> None:
    if full:
        say(f"\n  [NARRATOR]\n{narration}\n")
    else:
        excerpt = narration.replace("\n", " ").strip()[:220]
        say(f"\n  [NARRATOR] {excerpt}{'...' if len(narration) > 220 else ''}")


def print_state(game: GameState) -> None:
    meters = " ".join(f"{name}:{value}" for name, value in game.resources.meters.items())
    say(f"  [STATE] {meters} chaos:{game.world.chaos_factor} scene:{game.narrative.scene_count}")


def final_state_dict(game: GameState) -> dict[str, Any]:
    return {
        "character": game.player_name,
        "chapter": game.campaign.chapter_number,
        "location": game.world.current_location,
        "scene": game.narrative.scene_count,
        "meters": dict(game.resources.meters),
        "chaos": game.world.chaos_factor,
        "npcs": [
            {
                "id": n.id,
                "name": n.name,
                "status": n.status,
                "disposition": n.disposition,
                "bond": get_npc_bond(game, n.id),
                "agenda": n.agenda,
                "instinct": n.instinct,
                "arc": n.arc,
                "aliases": list(n.aliases),
                "memory_count": len(n.memory),
                "importance_accumulator": n.importance_accumulator,
                "needs_reflection": n.needs_reflection,
            }
            for n in game.npcs
        ],
        "active_clocks": [
            {
                "name": c.name,
                "clock_type": c.clock_type,
                "filled": c.filled,
                "segments": c.segments,
                "owner_kind": c.owner_kind,
                "owner_id": c.owner_id,
            }
            for c in game.world.clocks
            if not c.fired
        ],
    }


def print_summary(slog: SessionLog, game: GameState | None) -> None:
    separator = "=" * 62
    say(f"\n{separator}")
    say(f"  Session complete: {slog.ended_reason}")
    say(f"  Chapters played : {len(slog.chapters)}")
    say(f"  Total turns     : {slog.total_turns}")
    say(f"  Violations      : {len(slog.violations)}")
    if game:
        say(f"  Final scene     : {game.narrative.scene_count}")
        meters = ", ".join(f"{name} {value}" for name, value in game.resources.meters.items())
        say(f"  Final meters    : {meters}")
    bs = slog.burn_stats
    if bs.get("offered", 0) > 0:
        say(f"  Burns           : {bs['offered']} offered, {bs['taken']} taken, {bs['failed']} failed")
    if slog.narration_quality_issues:
        say(f"  Quality issues  : {len(slog.narration_quality_issues)}")
    if slog.spatial_issues:
        say(f"  Spatial issues  : {len(slog.spatial_issues)}")
    if slog.correction_tests:
        failed = sum(1 for c in slog.correction_tests if not c.get("success"))
        say(f"  Corrections     : {len(slog.correction_tests)} tested, {failed} failed")
    qs = slog.quality_summary
    if qs.get("narration_quality_total", 0) > 0:
        say(f"  Narration leaks : {qs['narration_quality_total']}")
    if qs.get("spatial_issues_total", 0) > 0:
        say(f"  Spatial issues  : {qs['spatial_issues_total']}")
    if qs.get("chapter_continuity_total", 0) > 0:
        say(f"  Continuity      : {qs['chapter_continuity_total']}")
    ct = qs.get("correction_tests_total", 0)
    if ct > 0:
        cf = qs.get("correction_tests_failed", 0)
        say(f"  Corrections     : {ct} tested, {cf} failed")
    ts = slog.token_summary
    if ts.get("total", 0) > 0:
        say(f"  Tokens          : {ts['total_input']} in + {ts['total_output']} out = {ts['total']} total")
        for role, stats in sorted(ts.get("by_role", {}).items(), key=lambda x: -x[1]["input"]):
            say(f"    {role:<20}: {stats['calls']}x, {stats['input']} in + {stats['output']} out")
    say(separator)
