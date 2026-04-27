# Origins

Straightjacket implements the [Narrative RPG Engine](docs/narrative_rpg_engine_v2_4.pdf) design document ([itch.io](https://blindgamer85.itch.io/narrative-rpg-engine-accessible-solo-tabletop-with-ai-as-narrator-and-systems-u)). The document's core thesis: AI storytelling fails because projects ask AI to do everything — decide outcomes, track memory, manage pacing, generate narrative. The solution is less AI, with more structure around it. The AI narrates. It does not decide.

The document grew out of five months of intensive work with AI as a co-author and thinking partner, starting August 2025. Experimental chatbots, RPG scenarios, then frustration with what AI cannot do by default (memory, consequences, pacing), then exploration of tabletop and solo-RPG systems where those problems are already solved. The resulting synthesis: use AI for what it is good at (prose generation within tight constraints), use tabletop design patterns for everything else. Version 2.4 of the document was published on itch.io in January 2026, with accompanying posts on r/Solo_Roleplaying, r/RPGdesign, r/Ironsworn, and one other subreddit.

In February 2026, Lars reached out about his in-progress implementation of the document and asked for beta testing. That implementation is [EdgeTales](https://github.com/edgetales/edgetales) — the first working code that turned the design document into a running engine. Ironsworn mechanics, NiceGUI interface, chaos factor, momentum burn, scene-by-scene loop, NPC/clock/memory tracking, prompt assembly — the bones of a working narrative RPG engine, built by Lars on the architecture the document proposes.

Straightjacket began shortly afterwards as a fork of EdgeTales. The fork ran through March 2026, with intensive same-day backporting from upstream whenever Lars pushed changes. The cross-references are verifiable against Lars' repository: Straightjacket v0.10.0 is a modular refactor of EdgeTales v0.9.44 (committed to EdgeTales on 9 March 2026); Straightjacket v0.13.0 "Upstream sync v0.9.61" (22 March 2026) matches EdgeTales v0.9.61 committed the same day; Straightjacket v0.17.0 "Upstream UI sync" (28 March 2026) matches EdgeTales v0.9.66 from the day before. Backporting was costly work but worth doing as long as both projects moved in the same direction. After late March the two projects diverged enough that staying synchronised was no longer feasible, and the fork was carried forward as an independent codebase.

The fork's git history prior to the split is not preserved in the current Straightjacket repository — the early commits were lost, likely through a force push during the transition. What does remain are the CHANGELOG entries (versions 0.10 through 0.30) and the cross-referenced upstream versions in EdgeTales' repository, which together establish the fork period. The current Straightjacket repository was initialised on 6 April 2026 with v0.31.0 ("Project independence. Renamed to Straightjacket"). At the time of writing (20 April 2026) Straightjacket has been standalone for fourteen days.

The codebase still contains code and design decisions that trace back to EdgeTales, both from the initial fork and from the backport period. This is not a clean-room reimplementation, and it would be wrong to describe it as one. What Straightjacket is, is a refactor-plus-extension of Lars' implementation, done with his permission — refactored toward a different architecture, type system, AI pipeline, and testing approach, and extended with new subsystems that were not present upstream.

## How the codebase has evolved

The table below describes the shape of the current codebase relative to EdgeTales. Many of these differences are the result of refactoring work on the original implementation, not parallel development from scratch.

| EdgeTales | Straightjacket |
|---|---|
| Single-file engine (engine.py) | Multi-package engine (~80 modules across mechanics, ai, npc, game, datasworn, db, tools) |
| Single-file app (app.py) | Starlette/uvicorn server + single-page HTML client (web/ package) |
| Hardcoded constants | YAML-driven configuration (engine/, emotions/, prompts/, strings/) |
| NPC/clock/memory as dicts | Typed dataclasses with snapshot/restore |
| Hardcoded move list | Config-driven (engine.yaml + Datasworn JSON per setting) |
| German + English hardcoded | English default, YAML-extensible i18n |
| Claude-only | Provider-agnostic (AIProvider Protocol, any OpenAI-compatible API) |
| Voice I/O | Browser-native assistive tech |
| AI-generated character creation | Datasworn-driven deterministic creation |

## Extensions beyond the original fork

Subsystems built on top of the refactored base, not inherited from EdgeTales:

- Typed dataclass model layer with snapshot/restore for atomic undo
- Provider abstraction with cluster-based model assignment
- Two-call pattern (narrator prose + metadata extraction)
- NPC memory system (importance scoring, TF-IDF activation, reflection thresholds, presence guards)
- Story architect (3-act and Kishōtenketsu structures)
- Director agent (NPC reflections, AIMS generation, act transitions)
- Datasworn integration (setting packages, oracle tables, deterministic character creation)
- Correction pipeline (## undo with full state restore)
- Chapter system (campaign continuity, epilogues, NPC ID remapping)
- Elvira test bot (headless integration testing with invariant checking)
- Accessibility architecture (ARIA, screen reader support, narrative-only status output)
- 1138-test suite plus twenty AST/regex project rules

## Credits

- **Lars** ([EdgeTales](https://github.com/edgetales/edgetales)) — first working implementation of the design document, the fork point for Straightjacket, and the source of code and design decisions that persist in the current codebase. Straightjacket exists because Lars built the first version and permitted the refactor that followed.
- **Shawn Tomkin** — Ironsworn/Starforged (CC BY-NC-SA 4.0)
- **rsek** — [Datasworn](https://github.com/rsek/datasworn) data format
- **Tana Pigeon** — Mythic Game Master Emulator Second Edition (fate system, scene structure, random events, meaning tables, thread/character list mechanics)
- **John Harper** — Blades in the Dark (position & effect, clocks)
- **Gnome Stew** — AIMS framework (Agenda, Instinct, Moves, Secrets) for NPC agency
