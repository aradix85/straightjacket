# Origins

Straightjacket implements the [Narrative RPG Engine](docs/narrative_rpg_engine_v2_4.pdf) design document ([itch.io](https://blindgamer85.itch.io/narrative-rpg-engine-accessible-solo-tabletop-with-ai-as-narrator-and-systems-u), January 2026). The document's core thesis: AI storytelling fails because projects ask AI to do everything — decide outcomes, track memory, manage pacing, generate narrative. The solution is less AI, with more structure around it. The AI narrates. It does not decide.

The initial prototype was built on [EdgeTales](https://github.com/edgetales/edgetales) by Lars, which was itself based on the same design document. The fork diverged structurally from the first week. What started as refactoring became a reimplementation: different architecture, different type system, different AI pipeline, different testing approach. The codebases no longer share meaningful code.

## What came from EdgeTales

The original prototype, the NiceGUI web interface approach, and the idea of combining Ironsworn mechanics with AI narration. The initial chaos factor implementation, the basic momentum burn flow, and the scene-by-scene game loop structure.

## What Straightjacket built independently

- Config-driven game logic (engine.yaml, emotions.yaml, prompts.yaml, strings.yaml)
- Typed dataclass model layer with snapshot/restore
- Provider abstraction (AIProvider protocol, any OpenAI-compatible API)
- Two-call pattern (narrator prose + metadata extraction)
- NPC memory system (importance scoring, TF-IDF activation, reflection thresholds, presence guards)
- Constraint validator with retry logic
- Story architect (3-act and Kishōtenketsu structures)
- Director agent (pacing, NPC reflections, act transitions)
- Datasworn integration (setting packages, oracle tables, deterministic character creation)
- Correction pipeline (## undo with full state restore)
- Chapter system (campaign continuity, epilogues, NPC ID remapping)
- Elvira test bot (headless integration testing with invariant checking)
- Accessibility architecture (ARIA, screen reader support)
- 485-test suite

## Structural differences from EdgeTales

| EdgeTales | Straightjacket |
|---|---|
| Single-file engine (engine.py) | 15+ module engine package |
| Single-file app (app.py) | app.py + 7-module UI package |
| Hardcoded constants | YAML-driven configuration |
| NPC/clock/memory as dicts | Typed dataclasses throughout |
| Hardcoded move list | Config-driven (engine.yaml) |
| German + English hardcoded | English default, YAML-extensible i18n |
| Claude-only | Provider-agnostic (Protocol-based) |
| Voice I/O | Browser-native assistive tech |
| AI-generated character creation | Datasworn-driven deterministic creation |

## Credits

- **Lars** ([EdgeTales](https://github.com/edgetales/edgetales)) — original prototype and foundational ideas
- **Shawn Tomkin** — Ironsworn/Starforged (CC-BY-4.0)
- **rsek** — [Datasworn](https://github.com/rsek/datasworn) data format
- **Tana Pigeon** — Mythic GME (chaos factor concept)
- **John Harper** — Blades in the Dark (position & effect, clocks)
