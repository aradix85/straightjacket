from __future__ import annotations

from dataclasses import dataclass, field

from straightjacket.engine.models import GameState

TARGETS = (
    "result:MISS",
    "result:WEAK_HIT",
    "result:STRONG_HIT",
    "match",
    "dialog",
    "combat",
    "npc_introduced",
    "npc_died",
    "clock_fired",
    "location_change",
    "director",
    "burn_offered",
    "burn_taken",
    "correction",
    "chapter_transition",
    "game_over",
    "succession",
    "save_roundtrip",
    "stream_complete",
    "bonus_used",
    "chained_move",
    "pay_the_price",
    "ai_failure_rollback",
)

STEERING = (
    ("dialog", "bot_turn_directive_dialog"),
    ("combat", "bot_turn_directive_physical_risk"),
    ("location_change", "bot_turn_directive_travel"),
)


@dataclass
class WorldView:
    npc_status: dict[str, str]
    fired_clocks: set[str]
    location: str


@dataclass
class Coverage:
    counts: dict[str, int] = field(default_factory=dict)

    def hit(self, target: str, times: int = 1) -> None:
        if target not in TARGETS:
            raise ValueError(f"Unknown coverage target '{target}'")
        if times > 0:
            self.counts[target] = self.counts.get(target, 0) + times

    def observe_turn(self, before: WorldView, after: WorldView, result: str | None, match: bool, move: str) -> None:
        if result is None:
            self.hit("dialog")
        else:
            self.hit(f"result:{result}")
            if match:
                self.hit("match")
        if move.startswith("combat/"):
            self.hit("combat")
        self.hit("npc_introduced", len(set(after.npc_status) - set(before.npc_status)))
        self.hit(
            "npc_died",
            sum(
                1
                for npc_id, status in after.npc_status.items()
                if status == "deceased" and before.npc_status.get(npc_id) != "deceased"
            ),
        )
        self.hit("clock_fired", len(after.fired_clocks - before.fired_clocks))
        if after.location and after.location != before.location:
            self.hit("location_change")

    def observe_events(self, events: list[str]) -> None:
        if any(e.startswith("[Bonus]") and "ignored" not in e for e in events):
            self.hit("bonus_used")
        if any(e.startswith("[Chain]") and "skipped" not in e for e in events):
            self.hit("chained_move")
        self.hit("pay_the_price", sum(1 for e in events if e.startswith("[PayThePrice]")))

    def steer(self, turn: int, max_turns: int) -> str | None:
        if turn <= max_turns // 2:
            return None
        for target, directive in STEERING:
            if target not in self.counts:
                return directive
        return None

    def exercised(self) -> list[str]:
        return [t for t in TARGETS if t in self.counts]

    def missing(self) -> list[str]:
        return [t for t in TARGETS if t not in self.counts]

    def summary(self) -> dict[str, object]:
        return {"counts": dict(self.counts), "missing": self.missing()}


def world_view(game: GameState) -> WorldView:
    return WorldView(
        npc_status={n.id: n.status for n in game.npcs},
        fired_clocks={c.name for c in game.world.clocks if c.fired},
        location=game.world.current_location,
    )
