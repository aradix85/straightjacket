"""Typed data models for session logging.

Replaces the handcrafted dicts with dataclasses. Every field has a type,
every default is explicit, serialization is one call.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RollRecord:
    """Dice roll outcome for a single turn."""
    stat: str = ""
    d1: int = 0
    d2: int = 0
    total: int = 0
    c1: int = 0
    c2: int = 0
    result: str = ""
    match: bool = False


@dataclass
class StateSnapshot:
    """Resource/world state after a turn."""
    health: int = 0
    spirit: int = 0
    supply: int = 0
    momentum: int = 0
    chaos: int = 0
    scene: int = 0
    location: str = ""
    time_of_day: str = ""
    scene_context: str = ""


@dataclass
class NpcSnapshot:
    """Lightweight NPC state for session log."""
    id: str = ""
    name: str = ""
    status: str = ""
    disposition: str = ""
    bond: int = 0
    agenda: str = ""
    instinct: str = ""
    arc: str = ""
    memory_count: int = 0
    last_memory: str = ""
    last_location: str = ""
    aliases: list[str] = field(default_factory=list)


@dataclass
class ClockSnapshot:
    """Clock state for session log."""
    name: str = ""
    clock_type: str = ""
    filled: int = 0
    segments: int = 0
    owner: str = ""
    fired: bool = False


@dataclass
class ValidatorRecord:
    """Constraint validator outcome."""
    passed: bool = True
    retries: int = 0
    violations: list[str] = field(default_factory=list)
    attempt_violations: list[int] = field(default_factory=list)  # violation count per attempt
    picked_attempt: int = -1  # -1 = last attempt, 0+ = picked an earlier one


@dataclass
class EngineLogRecord:
    """Engine session_log entry snapshot."""
    summary: str = ""
    move: str = ""
    dramatic_question: str = ""
    chaos_interrupt: str | None = None
    director_trigger: str = ""
    consequences: list[str] = field(default_factory=list)
    clock_events: list[dict] = field(default_factory=list)
    position: str = ""
    effect: str = ""
    npc_activation: dict = field(default_factory=dict)


@dataclass
class StoryArcRecord:
    """Current story arc position."""
    phase: str = ""
    title: str = ""
    goal: str = ""
    mood: str = ""
    story_complete: bool = False


@dataclass
class TurnRecord:
    """Complete record of one turn."""
    turn: int = 0
    chapter: int = 0
    scene: int = 0
    location: str = ""
    action: str = ""
    narration: str = ""
    narration_excerpt: str = ""
    roll: RollRecord | None = None
    burn_offered: str = ""
    burn_taken: bool = False
    burn_error: str = ""
    director_ran: bool = False
    director_error: str = ""
    director_guidance: dict = field(default_factory=dict)
    state_after: StateSnapshot = field(default_factory=StateSnapshot)
    npcs: list[NpcSnapshot] = field(default_factory=list)
    clocks: list[ClockSnapshot] = field(default_factory=list)
    validator: ValidatorRecord | None = None
    engine_log: EngineLogRecord | None = None
    story_arc: StoryArcRecord | None = None
    violations: list[str] = field(default_factory=list)
    narration_quality: list[str] = field(default_factory=list)
    spatial_issues: list[str] = field(default_factory=list)
    is_correction: bool = False
    error: str = ""

    def to_dict(self) -> dict:
        """Serialize for JSON output. Strips None values and empty defaults."""
        from dataclasses import asdict
        d = asdict(self)
        # Remove empty/None fields for compact JSON
        return {k: v for k, v in d.items() if v is not None and v != "" and v != [] and v != {}}

    @property
    def has_issues(self) -> bool:
        """True if this turn had any diagnostic-relevant problems."""
        return bool(
            self.error
            or self.violations
            or self.narration_quality
            or self.spatial_issues
            or (self.validator and not self.validator.passed)
            or self.burn_error
            or self.director_error
        )

    def to_compact_dict(self) -> dict:
        """Compact turn summary for diagnostic logs. ~300 bytes vs ~6KB full.
        Includes narration excerpt only when this turn had issues."""
        d: dict = {"turn": self.turn, "scene": self.scene}
        if self.roll:
            d["result"] = self.roll.result
            d["move"] = self.engine_log.move if self.engine_log else ""
            if self.roll.match:
                d["match"] = True
        else:
            d["result"] = "dialog"
        d["action"] = self.action[:80]
        sa = self.state_after
        d["state"] = f"H{sa.health} Sp{sa.spirit} Su{sa.supply} M{sa.momentum} C{sa.chaos}"
        if self.validator:
            if not self.validator.passed:
                d["validator"] = f"FAIL({self.validator.retries}r, {len(self.validator.violations)}v)"
                d["validator_violations"] = self.validator.violations[:5]
                if self.narration:
                    d["narration_excerpt"] = self.narration[:500]
            elif self.validator.retries > 0:
                d["validator"] = f"pass({self.validator.retries}r)"
        if self.engine_log and self.engine_log.consequences:
            d["consequences"] = self.engine_log.consequences
        if self.engine_log and self.engine_log.clock_events:
            d["clock_events"] = [e.get("clock", "?") for e in self.engine_log.clock_events]
        if self.story_arc:
            d["phase"] = self.story_arc.phase
            if self.story_arc.story_complete:
                d["complete"] = True
        if self.director_ran:
            d["director"] = True
        if self.violations:
            d["invariant_violations"] = self.violations
        if self.narration_quality:
            d["quality_issues"] = self.narration_quality
        if self.spatial_issues:
            d["spatial_issues"] = self.spatial_issues
        if self.error:
            d["error"] = self.error
        if self.burn_offered:
            d["burn"] = f"{self.burn_offered}->{'taken' if self.burn_taken else 'skip'}"
        if self.has_issues:
            d["narration"] = self.narration[:500]
        if self.is_correction:
            d["correction"] = True
        return d


@dataclass
class ChapterRecord:
    """Summary of one chapter."""
    chapter: int = 0
    started_at_turn: int = 0
    turns_played: int = 0
    ended_reason: str = "unknown"


@dataclass
class SessionLog:
    """Complete session log. Serializable to JSON."""
    started_at: str = ""
    ended_at: str = ""
    config: dict = field(default_factory=dict)
    engine_version: str = ""
    auto_mode: bool = False
    style: str = ""
    max_chapters: int = 1
    character: str = ""
    location_start: str = ""
    game_context: dict = field(default_factory=dict)
    creation_data: dict = field(default_factory=dict)
    opening_narration: str = ""
    opening_validator: ValidatorRecord | None = None
    story_blueprint: dict = field(default_factory=dict)
    chapters: list[ChapterRecord] = field(default_factory=list)
    turns: list[TurnRecord] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    narration_quality_issues: list[str] = field(default_factory=list)
    spatial_issues: list[str] = field(default_factory=list)
    chapter_continuity_issues: list[str] = field(default_factory=list)
    validator_summary: dict = field(default_factory=dict)
    quality_summary: dict = field(default_factory=dict)
    correction_tests: list[dict] = field(default_factory=list)
    burn_stats: dict = field(default_factory=dict)
    ended_reason: str = "unknown"
    total_turns: int = 0
    final_state: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Full serialization — debug mode. ~160KB for 24 turns."""
        from dataclasses import asdict
        d = asdict(self)
        d["turns"] = [t.to_dict() if isinstance(t, TurnRecord) else t for t in self.turns]
        return d

    def to_diagnostic_dict(self) -> dict:
        """Compact diagnostic format. ~15-20KB for 24 turns.
        Keeps full session metadata + compact turn summaries.
        Narration included only for turns with issues (validator fail,
        invariant violations, quality issues, errors).
        NPC snapshots only at session end, not per-turn."""
        d: dict = {
            "engine_version": self.engine_version,
            "style": self.style,
            "character": self.character,
            "setting": self.config.get("game", {}).get("setting_id", ""),
            "total_turns": self.total_turns,
            "ended_reason": self.ended_reason,
            "chapters": [
                {"chapter": ch.chapter, "turns": ch.turns_played, "ended": ch.ended_reason}
                for ch in self.chapters
            ],
        }
        # Story blueprint — conflict and structure only
        if self.story_blueprint:
            bp = self.story_blueprint
            d["story"] = {
                "structure": bp.get("structure_type", ""),
                "conflict": bp.get("central_conflict", "")[:200],
                "thematic": bp.get("thematic_thread", "")[:200],
                "acts": [f"{a.get('phase', '?')}: {a.get('title', '?')}" for a in bp.get("acts", [])],
            }
        # Compact turns
        d["turns"] = [
            t.to_compact_dict() if isinstance(t, TurnRecord) else t
            for t in self.turns
        ]
        # Aggregated stats — truncate violation strings for readability
        vs = dict(self.validator_summary) if self.validator_summary else {}
        if vs.get("top_violations"):
            vs["top_violations"] = [
                [v[:120], count] for v, count in vs["top_violations"]
            ]
        d["validator_summary"] = vs
        if self.quality_summary:
            d["quality_summary"] = self.quality_summary
        d["burn_stats"] = self.burn_stats
        # Final NPC state (once, not per-turn)
        if self.turns:
            last = self.turns[-1]
            if isinstance(last, TurnRecord) and last.npcs:
                d["final_npcs"] = [
                    {"name": n.name, "status": n.status, "disposition": n.disposition,
                     "bond": n.bond, "memories": n.memory_count}
                    for n in last.npcs
                ]
        d["final_state"] = self.final_state
        # Session-level issues
        if self.violations:
            d["invariant_violations"] = self.violations
        if self.chapter_continuity_issues:
            d["continuity_issues"] = self.chapter_continuity_issues
        if self.correction_tests:
            d["correction_tests"] = self.correction_tests
        return d
