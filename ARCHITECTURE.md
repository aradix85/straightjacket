# Architecture

A bird's-eye view of Straightjacket: what it is built to do, how a turn flows, where the code lives, and the rules its structure keeps. The details live in the files README.md lists and are not repeated here.

## The core idea

Straightjacket puts the Narrative RPG Engine design document ([itch.io](https://blindgamer85.itch.io/narrative-rpg-engine-accessible-solo-tabletop-with-ai-as-narrator-and-systems-u)) into practice: the engine owns the rules and the facts, the AI writes prose within them. Every value that can be derived from game state is computed by the engine: dice and outcomes, resources, pacing, act transitions, the emotional weight of memories, the opening clock and time of day. The AI receives results, not choices.

**Order of preference.** Whoever can decide something decides it in this order: first a tabletop system the engine implements (Mythic GME as the game master's stand-in, the Ironsworn and Starforged rules, the Adventure Crafter, Blades in the Dark), then an engine rule where no source settles it, and only then the AI, which writes prose and reads the player's free text. The design document's specific recommendations serve this aim; where practice shows one of them fails, `docs/divergences.md` records the departure and why, judged by this order. Every rule that decides something in the fiction names its origin: a source, or an engine rule with its reason in the register (AUDIT.md, principle 6). What came from EdgeTales without a source is taken over in the roadmap step that names it, by a source or by a system the engine already has, and leaves only once that does its work.

**What the AI still decides.** These decisions stay with the AI in play, each bounded by the engine:

- The Brain turns free player text into a move and its parameters, each limited to what the engine offers in that situation (`docs/ai.md`, Roles), and the dice, fate, and the engine decide the outcome; what of its free text reaches the world is the name of a place the character moves to and a detail the player adds to the scene.
- The narrator supplies every fact the engine has not settled, such as the look of a room or what an NPC says.
- The metadata extraction registers the NPCs, renames, and deaths the narration introduces, and gives each new NPC a disposition from the engine's list, so narrated facts can become state; the opening extraction does the same for an opening scene and also writes the opening NPCs' agendas, instincts, and secrets.
- The Director writes agendas, instincts, and arcs for the NPCs the engine selects, and guidance that reaches the narrator's next prompts.
- The correction analysis reads a `##` correction and decides whether the input was misread, which the engine replays with the dice already rolled, or which state operations apply; the operations, fields, NPCs, and values are limited to those its schema offers.

The Brain reading free text, the narrator's prose, and the Director's wording stay with the AI by design. What the AI still decides where a system could is listed in `docs/divergences.md`, each with the roadmap step that takes it over.

**Engine-resolved fiction.** The target is an engine that produces every fact the fiction needs before the narrator writes: names and dispositions from oracle rolls, locations from generators, plot beats from the Adventure Crafter, facts and NPC behaviour under uncertainty from Mythic's fate system, encounters from weighted tables, scene structure from chaos rolls, content from Mythic's element meaning tables. Implemented today: NPC names from oracles, locations and settlements from the setting's tables when the character first arrives, plot beats from the Adventure Crafter and the moment each act's revelation lands, scene structure from chaos rolls, meaning-table rolls inside random events, the naming of threats and clocks (complication clocks included), and facts that the Brain names and fate settles (`docs/mechanics.md`, Facts and Generators). `gamemaster/generation.py` is the entry point for the content a turn asks the engine to settle: `generate_fact` settles a fact, and `generate_entity` rolls an entity category (an NPC's name, a location, a settlement) from the tables the setting names; threats and clocks are still rolled at their own callsites.

## Turn pipeline

The player types "I search the room"; the engine returns narration and the updated game state.

```
player input
  ↓
Scene test (gamemaster/scene.py) → a keyed scene that fires, else the chaos die: expected, altered, or interrupt
  ↓
Snapshot (game/turn.py) → the turn's state, which a correction restores
  ↓
Brain (ai/brain.py) → one classification call with the game state in its prompt, asked again once for a wrong stat
  ↓
Location and time (gamemaster/world.py) → the Brain's move to another place clears the facts of the old one
  ↓
Place generation (gamemaster/generation.py) → a place the world does not know yet is rolled from the setting's tables
  ↓
Fact resolution (gamemaster/generation.py, gamemaster/facts.py) → each undetermined fact settled by fate or reused
  ↓
NPC activation (gamemaster/npc/activation.py) → decides which NPCs get full context
  ↓
Roll (ruleset/make_move.py) → the move's Ironsworn roll: STRONG_HIT, WEAK_HIT, or MISS; the momentum-burn offer and a second snapshot
  ↓
Consequences (game/action_resolution.py) → position and effect, move outcome, combat position, clock ticks, threats, the dying clock, follow-up moves (Endure, Face Death), crisis check
  ↓
Facts and revelation (game/turn.py) → the facts the result settles or clears, and the act's revelation if it lands
  ↓
Prompt assembly (prompt_action.py, prompt_dialog.py) → XML prompt with world, NPCs, result, facts, scene type
  ↓
Narration (game/finalization.py) → narrator call, then cleanup of leaked metadata (parser.py)
  ↓
Post-narration (game/finalization.py) → scene context, engine memories, metadata extraction
  ↓
Scene-end bookkeeping (game/scene_finalization.py) → autonomous clock and threat ticks, act transition, story completion, chaos, list upkeep
  ↓
Save (web/handlers.py, persistence.py)
  ↓
Director (game/director_runner.py) → after the turn is returned, when the scene end called for it: NPC reflections; saved again
```

Dialog turns skip the roll and the move's consequences, but resolve the dying clock, a full menace track, their follow-up moves, the crisis, and a revelation. A `##` correction of a misread input and a momentum burn play parts of this pipeline again from a snapshot, and a correction of the state edits it and narrates again (`docs/mechanics.md`, Shared outcome resolution).

## Code map

The source lives under `src/straightjacket/`.

- `engine/` — the engine core: the typed models (`models.py` re-exports every dataclass from `models_base.py`, `models_npc.py`, and `models_story.py`), strict serialization (`serialization.py`), saves (`persistence.py`), users and save folders (`user_management.py`), the loaders for `config.yaml` and the yaml stores, narrator prompt assembly (`prompt_action.py`, `prompt_dialog.py`, `prompt_boundary.py`, with shared parts in `prompt_shared.py` and `prompt_blocks.py`), narrator output cleanup (`parser.py`), story-arc tracking and act transitions (`story_state.py`), the Director with its AI call (`director.py`), and small helpers (logging, ids, XML escaping in `xml_utils.py`).
- `engine/setting/` — the setting layer: the Datasworn files, the world each holds (its oracles and truths) and the ruleset it names, setting packages, and the rolls on their oracle tables, cascades included.
- `engine/gamemaster/` — the game master layer, with no AI: its own moves, dialog and asking the oracle, Mythic's fate, chaos, scene test, random events, and lists, and the loader of Mythic's data, keyed scenes, the scene context, and the engine's rules that hold in any system: clocks and their ticks, position and effect, facts and the generation entry point, pacing, location and time, NPC stance and information gating, the engine's memories, and the questions it asks the ruleset.
- `engine/gamemaster/npc/` — NPC state: name matching, memory, activation, lifecycle, oracle names, and applying extracted metadata.
- `engine/crafters/` — the crafters layer: the Adventure Crafter's tables, turning points, and blueprint seed.
- `engine/ruleset/` — the ruleset layer, the Ironsworn rules, with no AI: the rules, moves, and assets of the ruleset's Datasworn files, the character a player creates, stats and meters, rolls, Datasworn moves and which of them a situation offers, move outcomes with their effects and handlers, progress tracks and a connection's bond, impacts, harm and stress, legacy, assets and roll bonuses, boasts, threats, the narrator's sentences for consequences, the mechanical side of succession, and its answers to the game master's questions.
- `engine/ai/` — provider adapters and routing, output schemas, sentence streaming, and the AI calls of the Brain, the narrator, the metadata and opening extractions (applied with the NPC layer by `ai/metadata.py` and `game/setup_common.py`), recap, and blueprint voicing. Two calls live with the code that uses them: the Director's in `director.py` and the correction analysis in `correction/analysis.py`.
- `engine/tools/` — the Director's tool registry, its tool, and the execution of its tool calls.
- `engine/game/` — orchestration: the turn, action resolution, shared narration and finalization, momentum burn, game start, chapters, succession, and the deferred Director run.
- `engine/correction/` — the `##` correction: the analysis call, the replay of a misread input, and state patches with re-narration.
- `web/` — the Starlette server, one handler per WebSocket message, session state, serializers that turn game state into client JSON, and the single-page client `web/static/index.html`.

Beside them, `i18n.py` serves user-facing strings, which any layer may import.

**The four layers.** The setting, the game master, the crafters, and the ruleset each have a package and yaml of their own, the setting's in `data/settings` beside its Datasworn files, apart so that another system replaces only the ruleset. The game master reaches the ruleset only through the questions it asks in its own words, which the ruleset answers and the game package installs (`docs/mechanics.md`, Game master and ruleset). Each layer reads its yaml through its own accessor (`setting/packages.py` → `load_package`, `gm()`, `crafter()`, and `rules()`; `eng()` reads the engine's own `engine/`), so reading a layer's configuration means importing that layer, and the import layers below hold it to the direction. Their packages are markers without re-exports, and callers import from the module, so every import names the layer it reaches into.

**Subpackage public API via `__init__.py`.** `game`, `tools`, and `correction` re-export their public names in `__init__.py`, so callers write `from straightjacket.engine.game import process_turn` and the internal file layout stays free to change; a project-rule scan holds code outside the three packages to it. `models.py` is the same kind of hub for the dataclasses. `engine`, `ai`, and `web` are package markers without re-exports, like the four layers.

**Import layers.** Dependencies point downward. The files directly under `engine/` are not one layer. Their base (the models, serialization, the configuration and yaml loaders, logging, and small helpers such as `xml_utils.py`; the list is `_CORE_BASE` in `tests/test_project_rules.py`) imports nothing above it. `setting` imports only that base. Above it the layers point one way: `gamemaster` may use the base and `setting`, `crafters` also `gamemaster`, and `ruleset` also `crafters`, so the game master and the crafters never import the ruleset; none of them imports `ai` or `tools`; `tools` may use all of those but not `ai`, since it only answers the tool calls the Director's AI call makes in `director.py`. None of them imports the rest of the core files, `game`, `correction`, or `web`. The rest of the core (prompt assembly, the parser, persistence, story-arc tracking, and the Director) and `ai` use each other: the Brain and the narrator read prompt blocks and the parser, while the Director in `director.py` calls `ai` and `tools`. No core file and nothing in `ai` imports `game`, `correction`, or `web`. `game` orchestrates everything below it, `correction` builds on `game`, and nothing in the engine imports `web`. A project-rule scan enforces this, inline imports included.

## State

**Typed dataclasses.** `GameState` holds typed sub-objects (resources, world, narrative, campaign), and every other piece of state (NPCs, memories, moves, progress tracks, threads, clocks, threats, chapter summaries) is a dataclass with fixed fields, reached by attribute, never as a dict; only a consequence keeps the values its label is filled with in one. The character's stats and meters are values keyed by the names their ruleset gives them (`GameState.stats`, `Resources.meters`), since another ruleset names others. `serialization.py` → `SerializableMixin` serializes every class without manual overrides.

**Snapshot and restore.** `GameState.snapshot()` captures all mutable state, including every entry of the story lists, and `restore()` reverts it atomically. A correction of a misread input, a momentum burn, and a turn whose AI call fails restore from snapshots (`docs/mechanics.md`, Shared outcome resolution; `docs/ai.md`, When an AI call fails). A resolved fact lives in `WorldState.facts`, so the snapshot carries it like any other world state.

**Saves.** A save is JSON in the users folder (the project's `users` folder, or the folder `STRAIGHTJACKET_USERS_DIR` names). Loading is strict: a field the class does not know, a field the data lacks, a null where the type allows none, or a plain value where an object belongs raises, and `persistence.py` → `load_game` reports such a save to the player as incompatible. The list of saves (`list_saves_with_info`) leaves out a file in the saves folder that is not readable JSON with a save's header fields, and logs a warning, since one stray file should not keep the player from the other saves. Restoring a turn's snapshot is equally strict.

**No second store.** The dataclasses are the only store; the Director's tool and the prompts filter them directly. A copy for queries would have to be rebuilt after every change and cost more than the filtering it saves, while the state of a solo game stays small enough to fit in memory.

## Configuration

Configuration lives in yaml stores that are directories with one file per subsystem or topic: `gamemaster`, `crafters`, and `ruleset` for the rules and numbers of each layer, `engine` for the engine's own numbers and text that are no rule (the AI's text, the parser, retry, persistence), `prompts` for AI-facing text, `strings` for user-facing text, `emotions` for emotion scoring. Each loader merges its directory and raises on a key that two files define; code reaches them only through `eng()`, `gm()`, `crafter()`, `rules()`, `get_prompt()` with `get_prompt_prefix()`, `t()` with `all_strings()`, and `importance_map()` with `keyword_boosts()`. `config.yaml` stays a single, user-edited file for the server, the providers, and the model assignment, read as strictly as the rest: a key it does not know, a key it lacks, or a role mapped to a cluster it does not define stops startup with a message that names it, and a role that `ai.role_cluster` lacks stops its first call. Game content comes from Datasworn JSON and the Mythic and Adventure Crafter data in the `data` folder, each setting from a yaml file in `data/settings`.

Every yaml block is parsed into a typed dataclass at load time, by the folder's own module (`engine_config.py` with `engine_config_dataclasses.py` for `engine/`, `gamemaster/config.py` with `gamemaster/config_types.py`, `crafters/config.py`, `ruleset/config.py` with `ruleset/config_types.py`; the strict binding they share is `config_binding.py`), and read as `gm().subsystem.field`, `rules().subsystem.field`, and so on; inside a section a key the dataclass does not know raises, at every depth, and a top-level section that no code reads fails the orphan-key scan (CONTRIBUTING.md). The exception is yaml whose keys are themselves domain content, such as move names or dispositions, which must extend without a Python change; those blocks are read with `get_raw("section")` on the folder's accessor.

## Interface and accessibility

A single HTML page with inline CSS and JavaScript and no build step. The server sends JSON over one WebSocket; the client renders it. The page is built for screen readers: semantic HTML, a heading per scene for navigation, an ARIA live region that reads each narration aloud, and native form controls. Narration streams sentence by sentence, so the screen reader starts after the first sentence (see `docs/ai.md`).

Before play the page shows the players and then character creation. During play there is one text input plus the Save/Load and Retire buttons; everything else appears only when needed, as overlays with native controls: the momentum-burn offer, story completion, succession, the retire confirmation. The `/status`, `/score`, `/tracks`, and `/threats` commands are answered by the engine without an AI call, in narrative form: "seriously wounded" rather than "health 2"; `/advance` spends experience, `recap` asks the AI for a recap, and a line starting with `##` is a correction. Narration and status never show numbers, dice, or system terms; the burn offer, `/advance`, and character creation name the costs and values the player chooses among.

## Constraints

**Single session.** One player at a time (SECURITY.md, Session model). Module-level accumulators (the pending random events) assume it; several sessions would need per-session state.
