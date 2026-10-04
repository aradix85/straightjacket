# Origins

Straightjacket puts the [Narrative RPG Engine](https://blindgamer85.itch.io/narrative-rpg-engine-accessible-solo-tabletop-with-ai-as-narrator-and-systems-u) design document into practice. The document, written by this project's author and published on itch.io, is the theoretical concept: AI storytelling fails when the AI is asked to decide outcomes, track memory, manage pacing, and write prose all at once, so the AI should only narrate while structured systems decide. This project is the practical implementation and differs from the document wherever building it called for it.

## Lineage

Straightjacket started in March 2026 as a fork of [EdgeTales](https://github.com/edgetales/edgetales), Lars' implementation of the same design document and the first engine that ran it. During March, changes from EdgeTales were carried over until the two projects diverged; since April 2026 Straightjacket has been an independent codebase. The fork's early commits are not in this repository's git history.

The codebase still contains code and design decisions from EdgeTales. It is not a clean-room reimplementation: it is a refactor and extension of Lars' implementation, made with his permission, toward a different architecture, type system, AI pipeline, and testing approach, and extended with subsystems EdgeTales does not have, among them typed state with snapshot and restore, per-role provider routing, Datasworn setting packages with deterministic character creation, the Adventure Crafter blueprint, fate-settled facts, the correction pipeline, chapters and succession, and the test player Elvira.

## Credits

- **Lars** ([EdgeTales](https://github.com/edgetales/edgetales)) — the first working implementation of the design document, the fork point for Straightjacket, and the source of code and design decisions that persist in it. Straightjacket exists because Lars built the first version and permitted the refactor that followed.
- **Shawn Tomkin** — Ironsworn, Ironsworn: Delve, Ironsworn: Starforged, and Sundered Isles.
- **rsek** — the [Datasworn](https://github.com/rsek/datasworn) data format.
- **Tana Pigeon** — Mythic Game Master Emulator Second Edition and The Adventure Crafter, published by Word Mill Games.
- **John Harper** — Blades in the Dark (position and effect, clocks).
- **Gnome Stew** — the AIMS framework (Agenda, Instinct, Moves, Secrets) for NPC agency.

The licenses under which the game data is used are in README.md (License).
