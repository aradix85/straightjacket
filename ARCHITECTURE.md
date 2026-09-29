# Architecture

A bird's-eye view of Straightjacket: what it is built to do, how a turn flows, where the code lives, and the rules its structure keeps. Details live elsewhere and are not repeated here: [CONTRIBUTING.md](CONTRIBUTING.md) holds the project rules, code standards, and testing; `docs/ai.md` the AI layer; `docs/mechanics.md` the game mechanics; `docs/settings.md` settings and character creation; `docs/divergences.md` the deliberate departures from the source rulebooks and the design document.

## The core idea

Straightjacket implements the Narrative RPG Engine design document (`docs/narrative_rpg_engine_v2_4.pdf`): the engine owns the rules and the facts, the AI writes prose within them. Every value that can be derived from game state is computed by the engine: dice and outcomes, resources, pacing, act transitions, the emotional weight of memories, the opening clock and time of day. The AI receives results, not choices.

**Order of preference.** Whoever can decide something decides it in this order: first a tabletop system the engine implements (Mythic GME as the game master's stand-in, the Ironsworn and Starforged rules, the Adventure Crafter, Blades in the Dark), then an engine rule where no source settles it, and only then the AI, which writes prose and reads the player's free text. The design document's specific recommendations serve this aim; where practice shows one of them fails, `docs/divergences.md` records the departure and why, judged by this order.

**What the AI still decides.** Four decisions stay with the AI in play, each bounded by the engine:

- The Brain turns free player text into a move, a stat, a roll bonus, a target NPC, a new track's name and rank, and the undetermined facts the action turns on. Free text needs interpretation, but each choice is limited to what the engine offers in that situation, and the dice, fate, and the engine decide the outcome.
- The narrator supplies every fact the engine has not settled, such as the look of a room or what an NPC says.
- The metadata extraction registers the NPCs, renames, and deaths the narration introduces, so narrated facts can become state; the opening extraction does the same for an opening scene.
- The Director writes agendas, instincts, and arcs for the NPCs the engine selects.

Three further calls judge rather than invent: the revelation check decides whether a planned revelation has appeared in the prose (step 9d moves that decision to the engine), the correction analysis turns a `##` correction into state operations, and blueprint voicing words the Adventure Crafter's rolled turning points for the setting. The first and last of the four are part of the design; step 9a moved the facts an action depends on from the narrator to fate, and step 9c shrinks the second and third further by generating entities before the narrator writes.

**Engine-resolved fiction.** The target is an engine that produces every fact the fiction needs before the narrator writes: names and dispositions from oracle rolls, locations from generators, plot beats from the Adventure Crafter, facts and NPC behaviour under uncertainty from Mythic's fate system, encounters from weighted tables, scene structure from chaos rolls, content from Mythic's element meaning tables. Implemented today: NPC names from oracles, plot beats from the Adventure Crafter, scene structure from chaos rolls, meaning-table rolls inside random events, the naming of threats and clocks, and facts: the Brain names the uncertain facts an action or question depends on, and the engine settles each through Mythic's fate chart with odds it derives from the fact type and the game state (`docs/mechanics.md`, Facts). The player types what the character does; a question about the fiction is Ironsworn's Ask the Oracle, which the engine answers, a yes/no question that a fact type covers through fate and an open question through the setting's oracle tables. Fate and oracles are consulted at concrete callsites in the modules that need them; `mechanics/generation.py` → `generate` is the single entry point for engine-generated content, with facts as its first category.

## Turn pipeline

The player types "I search the room"; the engine returns narration and the updated game state.

```
player input
  ↓
Scene test (mechanics/scene.py) → keyed > interrupt > altered > expected
  ↓
Brain (ai/brain.py) → one classification call with the game state in its prompt
  ↓
Location and time (mechanics/world.py) → the Brain's move to another place clears the facts of the old one
  ↓
Fact resolution (mechanics/generation.py, mechanics/facts.py) → each undetermined fact settled by fate or reused
  ↓
NPC activation (npc/activation.py) → decides which NPCs get full context
  ↓
Roll (mechanics/consequences.py) → the Ironsworn action roll: STRONG_HIT, WEAK_HIT, or MISS
  ↓
Consequences (game/action_resolution.py) → move outcome, combat position, clock ticks, crisis check; a hit clears the facts whose type says so
  ↓
Prompt assembly (prompt_action.py, prompt_dialog.py) → XML prompt with world, NPCs, result, facts, scene type
  ↓
Narration (game/finalization.py) → narrator call, then cleanup of leaked metadata (parser.py)
  ↓
Post-narration (game/finalization.py) → engine memories, scene context, metadata extraction
  ↓
Scene-end bookkeeping (game/scene_finalization.py) → autonomous clock and threat ticks, chaos, list upkeep
  ↓
Database sync (db/sync.py) and save (persistence.py)
  ↓
Director (game/director_runner.py) → after the turn is returned: NPC reflections; saved again
```

Dialog turns skip the roll and its consequences. A correction (`##`) of a misread input restores the state taken right after the scene test and plays the turn again with the corrected input, keeping the scene type, the settled facts, and the dice (`game/turn.py` → `replay_turn`); a correction of the state edits it and narrates the turn again. A momentum burn restores the state taken right after the roll and runs the turn's own resolution, narration, and scene-end path with the better result (`game/momentum_burn.py` → `process_momentum_burn`).

## Code map

The source lives under `src/straightjacket/`.

- `engine/` — the engine core: the typed models (`models.py` re-exports every dataclass from `models_base.py`, `models_npc.py`, and `models_story.py`), strict serialization (`serialization.py`), saves (`persistence.py`), users and save folders (`user_management.py`), the loaders for `config.yaml` and the yaml stores, narrator prompt assembly (`prompt_action.py`, `prompt_dialog.py`, `prompt_boundary.py`, with shared parts in `prompt_shared.py` and `prompt_blocks.py`), narrator output cleanup (`parser.py`), story-arc tracking (`story_state.py`), and the Director (`director.py`).
- `engine/mechanics/` — the rules, with no AI: rolls and consequences, move outcomes, progress tracks, impacts, legacy, assets and roll bonuses, NPC stance and information gating, fate, facts and the generation entry point, scene structure and keyed scenes, random events, threats, clocks, the Adventure Crafter, and the mechanical side of succession.
- `engine/npc/` — NPC state: bond from connection tracks, name matching, memory, activation, lifecycle, oracle names, and applying extracted metadata.
- `engine/ai/` — every AI call: provider adapters and routing, the Brain, the narrator, metadata extraction, recap, chapter summary, blueprint voicing, output schemas, and sentence streaming.
- `engine/tools/` — the Director's tool registry and tool loop, and engine query functions such as the available moves.
- `engine/game/` — orchestration: the turn, action resolution, shared narration and finalization, momentum burn, game start, chapters, succession, and the deferred Director run.
- `engine/correction/` — the `##` correction: the analysis call, atomic state patches, and snapshot restore with re-narration.
- `engine/datasworn/` — Datasworn JSON: loading, moves, oracle cascades, and setting packages.
- `engine/db/` — the in-memory SQLite read model: schema, sync, and read-only queries.
- `web/` — the Starlette server, one handler per WebSocket message, session state, serializers that turn game state into client JSON, and the single-page client `web/static/index.html`.

Beside them, `i18n.py` and `strings_loader.py` serve user-facing strings. The tests, including the test player Elvira, are described in CONTRIBUTING.md.

**Subpackage public API via `__init__.py`.** `mechanics`, `npc`, `game`, `db`, `tools`, and `correction` re-export their public names in `__init__.py`, so callers write `from straightjacket.engine.mechanics import roll_action` and the internal file layout stays free to change. `models.py` is the same kind of hub for the dataclasses. `engine`, `ai`, `datasworn`, and `web` are package markers without re-exports.

**Import layers.** Dependencies point downward. `datasworn` and `db` import only the engine core (models, config, loaders). `npc` and `mechanics` may use those and each other, but never `ai`, `tools`, `game`, `correction`, or `web`. `ai`, `tools`, and the engine core's own files never import `game`, `correction`, or `web`. `game` orchestrates everything below it, `correction` builds on `game`, and nothing in the engine imports `web`. A project-rule scan enforces this, inline imports included.

## State

**Typed dataclasses.** `GameState` holds typed sub-objects (resources, world, narrative, campaign), and every other piece of state (NPCs, memories, moves, progress tracks, threads, clocks, threats, chapter summaries) is a dataclass with fixed fields, reached by attribute, never as a dict. `serialization.py` → `SerializableMixin` serializes every class without manual overrides.

**Snapshot and restore.** `GameState.snapshot()` captures all mutable state, including every entry of the story lists, and `restore()` reverts it atomically. Each turn keeps a snapshot taken right after its scene test, with the scene type, as `GameState.last_turn_snapshot` for corrections; the momentum burn takes a second one right after the roll, and a turn whose AI call fails is rolled back to the state before it. A resolved fact lives in `WorldState.facts`, so the snapshot carries it like any other world state.

**Saves.** A save is JSON in the users folder (the project's `users` folder, or the folder `STRAIGHTJACKET_USERS_DIR` names). Loading is strict: a field the class does not know, or a field the data lacks, raises, and `persistence.py` → `load_game` reports such a save to the player as incompatible.

**Database as read model.** An in-memory SQLite database mirrors `GameState` after every turn, creation, correction, restore, and load. The dataclasses stay the write model; the database serves indexed queries to prompt assembly and the Director's tool. It is rebuilt from `GameState`, so it needs no migrations.

## Configuration

Configuration lives in yaml stores that are directories with one file per subsystem or topic: `engine` for rules and numbers, `prompts` for AI-facing text, `strings` for user-facing text, `emotions` for emotion scoring. Each loader merges its directory and raises on duplicate keys; code reaches them only through `eng()`, `get_prompt()`, `t()`, and `importance_map()`. `config.yaml` stays a single, user-edited file for the server, the providers, and the model assignment. Game content comes from Datasworn JSON and the Mythic and Adventure Crafter data in the `data` folder, each setting from a yaml file in `data/settings`.

Every yaml block is parsed into a typed dataclass at load time (`engine_config.py`, `engine_config_dataclasses.py`) and read as `eng().subsystem.field`. The exception is yaml whose keys are themselves domain content, such as move names or dispositions, which must extend without a Python change; those blocks are read with `eng().get_raw("section")`.

## Interface and accessibility

A single HTML page with inline CSS and JavaScript and no build step. The server sends JSON over one WebSocket; the client renders it. The page is built for screen readers: semantic HTML, a heading per scene for navigation, an ARIA live region that reads each narration aloud, and native form controls. Narration streams sentence by sentence, so the screen reader starts after the first sentence (see `docs/ai.md`).

During play there is one text input plus the Save/Load and Retire buttons. Everything else appears only when needed, as overlays with native controls: character creation, the momentum-burn offer, story completion, succession, the retire confirmation. The `/status`, `/score`, `/tracks`, and `/threats` commands are answered by the engine without an AI call, in narrative form: "seriously wounded" rather than "health 2". The player never sees numbers, dice, or system terms.

## Constraints

**Single session.** One player at a time (SECURITY.md describes the session model). Module-level accumulators (the pending random events, the token log) and the in-memory database assume a single session; several would need per-session state.
