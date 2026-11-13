# Architecture

A bird's-eye view of Straightjacket: what it is built to do, how a turn flows, where the code lives, and the rules its structure keeps. The details live in the files README.md lists and are not repeated here.

## The core idea

Straightjacket puts the Narrative RPG Engine design document ([itch.io](https://blindgamer85.itch.io/narrative-rpg-engine-accessible-solo-tabletop-with-ai-as-narrator-and-systems-u)) into practice: the engine owns the rules and the facts, and the AI writes prose within them. Every value that can be derived from game state is computed by the engine: dice and outcomes, resources, pacing, act transitions, the emotional weight of memories, the opening clock and time of day. The AI receives results, not choices.

**Order of preference.** Whoever can decide something decides it in this order:

1. a tabletop system the engine implements: Mythic GME as the game master's stand-in, the Ironsworn and Starforged rules, the Adventure Crafter, Blades in the Dark;
2. an engine rule, where no source settles it;
3. only then the AI, which writes prose and reads the player's free text.

The design document's specific recommendations serve this aim; where practice shows one of them fails, `docs/divergences.md` records the departure and why, judged by this order. Every rule that decides something in the fiction names its origin: a source, or an engine rule with its reason in the register (AUDIT.md, principle 6). What came from EdgeTales without a source is taken over in the roadmap step that names it, by a source or by a system the engine already has, and leaves only once that does its work.

**What the AI still decides.** These decisions stay with the AI in play, each bounded by the engine:

- The Brain turns free player text into a move and its parameters, each limited to what the engine offers in that situation (`docs/ai.md`, The Brain); the dice, fate, and the engine decide the outcome. Of its free text, what reaches the world is the name of a place the character moves to, a detail the player adds to the scene, the name of a track a move starts, and the player's intent, which the engine's NPC memories and the session log keep.
- The narrator supplies every fact the engine has not settled, such as the look of a room or what an NPC says.
- The metadata extraction registers the NPCs, renames, and deaths the narration introduces, and gives each new NPC a disposition from the engine's list, so narrated facts can become state. The opening extraction does the same for an opening scene and also writes the opening NPCs' agendas, instincts, and secrets.
- The Director writes agendas, instincts, and arcs for the NPCs the engine selects, and guidance that reaches the narrator's next prompts.
- The correction analysis reads a `##` correction and decides whether the input was misread, which the engine replays with the dice already rolled, or which state operations apply; the operations, fields, NPCs, and values are limited to those its schema offers.

The Brain reading free text, the narrator's prose, and the Director's wording stay with the AI by design. What the AI still decides where a system could is listed in `docs/divergences.md`, each with the roadmap step that takes it over.

**Engine-resolved fiction.** The target is an engine that produces every fact the fiction needs before the narrator writes: names and dispositions from oracle rolls, locations from generators, plot beats from the Adventure Crafter, facts and NPC behaviour under uncertainty from Mythic's fate system, encounters from weighted tables, scene structure from chaos rolls, content from Mythic's element meaning tables.

Implemented today: NPC names from oracles; locations and settlements from the setting's tables when the character first arrives (`docs/gamemaster.md`, Generators); plot beats from the Adventure Crafter, and the moment each act's revelation lands; scene structure from chaos rolls; meaning-table rolls inside random events; the naming of threats and clocks, complication clocks included; and facts that the Brain names and fate settles (`docs/gamemaster.md`, Facts). `gamemaster/generation.py` is the entry point for the content a turn asks the engine to settle: `generate_fact` settles a fact, and `generate_entity` rolls an entity category (an NPC's name, a location, a settlement) from the tables the setting names. Threats and clocks are still rolled at their own callsites.

## Turn pipeline

The player types "I search the room"; the engine returns narration and the updated game state.

```
player input
  ↓
Scene test (gamemaster/scene.py) → a keyed scene that fires, else the chaos die: expected, altered, or interrupt
  ↓
Pending random events (game/turn.py) → a threat that a random event of the last turn aimed at advances
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
Consequences (game/action_resolution.py) → position and effect, move outcome, combat position, clock ticks, a bond test a forsaken vow asks, threats, the dying clock, follow-up moves (Endure, Face Death), crisis check
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

**Turns without a roll.** Dialog turns and moves without a roll, such as Reach a Milestone, skip the roll and a rolled move's consequences; a move without a roll applies its own effects instead (`docs/ruleset.md`, Moves without a roll). They still resolve pending clock fills, NPC agency, a bond test a forsaken vow asks of the NPC they are aimed at, pending threat events, the dying clock, a full menace track, their follow-up moves, the crisis, and a revelation.

**Replays.** A `##` correction of a misread input and a momentum burn play parts of this pipeline again from a snapshot, and a correction of the state edits it and narrates again (`docs/gamemaster.md`, Replaying a turn).

## Code map

The source lives under `src/straightjacket/`.

- `engine/` — the engine core: the typed models (`models.py` re-exports every dataclass from `models_base.py`, `models_npc.py`, and `models_story.py`), the writer and the strict reader of dataclasses (`serialization.py`), saves (`persistence.py`), users and save folders (`user_management.py`), the loaders for `config.yaml` and the yaml stores, narrator prompt assembly (`prompt_action.py`, `prompt_dialog.py`, `prompt_boundary.py`, with shared parts in `prompt_shared.py` and `prompt_blocks.py`), narrator output cleanup (`parser.py`), story-arc tracking and act transitions (`story_state.py`), the Director with its AI call (`director.py`), and small helpers (logging, ids, XML escaping in `xml_utils.py`).
- `engine/setting/` — the setting layer: the Datasworn files, the world each holds (its oracles and truths) and the ruleset it names, setting packages, and the rolls on their oracle tables, cascades included.
- `engine/gamemaster/` — the game master layer, with no AI: its own moves, dialog and asking the oracle; Mythic's fate, chaos, scene test, random events, and lists, and the loader of Mythic's data; keyed scenes and the scene context; and the engine's rules that hold in any system: clocks and their ticks, position and effect, facts and the generation entry point, pacing, location and time, NPC stance and information gating, the engine's memories, and the questions it asks the ruleset.
- `engine/gamemaster/npc/` — NPC state: name matching, memory, activation, lifecycle, oracle names, and applying extracted metadata.
- `engine/crafters/` — the crafters layer: the Adventure Crafter's tables, turning points, and blueprint seed.
- `engine/ruleset/` — the ruleset layer, the Ironsworn rules, with no AI: the rules, moves, and assets of the ruleset's Datasworn files; the character a player creates; stats and meters; rolls; Datasworn moves and which of them a situation offers; move outcomes with their effects and handlers; progress tracks and a connection's bond; impacts, harm, and stress; legacy; assets and roll bonuses; boasts; threats; the narrator's sentences for consequences; the mechanical side of succession; and its answers to the game master's questions.
- `engine/ai/` — provider adapters and routing, output schemas, sentence streaming, and the AI calls of the Brain, the narrator, the metadata and opening extractions (applied with the NPC layer by `ai/metadata.py` and `game/setup_common.py`), recap, and blueprint voicing. Two calls live with the code that uses them: the Director's in `director.py` and the correction analysis in `correction/analysis.py`.
- `engine/tools/` — the Director's tool registry, its tool, and the execution of its tool calls.
- `engine/game/` — orchestration: the turn, action resolution, shared narration and finalization, momentum burn, game start, chapters, succession, the deferred Director run, and the check at startup (`startup.py`).
- `engine/correction/` — the `##` correction: the analysis call, the replay of a misread input, and state patches with re-narration.
- `web/` — the Starlette server, one handler per WebSocket message, session state, serializers that turn game state into client JSON, and the single-page client `web/static/index.html`.

Beside them, `i18n.py` serves user-facing strings, which any layer may import.

**The four layers.** The setting, the game master, the crafters, and the ruleset each have a package and yaml of their own (the setting's in `data/settings`, beside its Datasworn files), kept apart so that another system replaces only the ruleset. Each has a document: `docs/settings.md`, `docs/gamemaster.md`, `docs/story.md` for the crafters with chapters and succession, and `docs/ruleset.md`.

- The game master reaches the ruleset only through questions in its own words, which the ruleset answers and the server and Elvira install when they start (`docs/gamemaster.md`, Questions to the ruleset).
- Each layer reads its yaml through its own accessor: `setting/packages.py` → `load_package`, `gm()`, `crafter()`, and `rules()`; `eng()` reads the engine's own `engine/`. So reading a layer's configuration means importing that layer, and the import layers below hold it to the direction.
- Their packages are markers without re-exports, and callers import from the module, so every import names the layer it reaches into.

**Subpackage public API via `__init__.py`.** `game`, `tools`, and `correction` re-export their public names in `__init__.py`, so callers write `from straightjacket.engine.game import process_turn` and the internal file layout stays free to change; a project-rule scan holds code outside the three packages to it. `models.py` is the same kind of hub for the dataclasses. `engine`, `ai`, and `web` are package markers without re-exports, like the four layers.

**Import layers.** Dependencies point downward. A project-rule scan enforces this for every `from` import, those under `TYPE_CHECKING` included; the code imports the engine's packages no other way.

- **The core base.** The files directly under `engine/` are not one layer. Their base (the models, serialization, the configuration and yaml loaders, logging, and small helpers such as `xml_utils.py`; the list is `_CORE_BASE` in `tests/_rules_imports.py`) imports nothing above it.
- **The layers.** `setting` imports only that base. Above it the layers point one way: `gamemaster` may use the base and `setting`, `crafters` also `gamemaster`, and `ruleset` also `crafters`, so the game master and the crafters never import the ruleset. None of them imports `ai` or `tools`, the rest of the core files, `game`, `correction`, or `web`.
- **`tools`** may use all of those but not `ai`, since it only answers the tool calls the Director's AI call makes in `director.py`; like them, it imports none of the rest of the core files, `game`, `correction`, or `web`. In turn `ai` imports from `tools` only the type of a tool's definition, for the call's spec.
- **The rest of the core and `ai`.** The rest of the core (prompt assembly, the parser, persistence, users and save folders, story-arc tracking, and the Director) and `ai` use each other: the Brain and the narrator read prompt blocks and the parser, while the Director in `director.py` calls `ai` and `tools`. No core file and nothing in `ai` imports `game`, `correction`, or `web`.
- **On top.** `game` orchestrates everything below it, `correction` builds on `game`, and nothing in the engine imports `web`.

## State

**Typed dataclasses.** `GameState` holds typed sub-objects (resources, world, narrative, campaign). Every other piece of state (NPCs, memories, moves, progress tracks, threads, clocks, threats, chapter summaries) is a dataclass with fixed fields, reached by attribute, never as a dict; only a consequence keeps what its label is filled with in two mappings, its texts and its numbers. The character's stats and meters are values keyed by the names their ruleset gives them (`GameState.stats`, `Resources.meters`), since another ruleset names others. `serialization.py` → `SerializableMixin` writes every class as plain data and reads it back without manual overrides.

**Snapshot and restore.** `GameState.snapshot()` captures all the state a turn can change, including every entry of the story lists, the backstory, and the predecessors the server archives once a turn ends the game; `restore()` reverts it atomically. The snapshot holds its parts as dataclasses copied from the state, and a restore copies them again, so a snapshot can be restored more than once. What the player decides between turns, an advance or a dismissed epilogue, is not in it and stays. A correction of a misread input, a momentum burn, and a turn whose AI call fails restore from snapshots (`docs/gamemaster.md`, Replaying a turn; `docs/ai.md`, When an AI call fails). A resolved fact lives in `WorldState.facts`, so the snapshot carries it like any other world state.

**Saves.** A save is JSON in the users folder: the project's `users` folder, or the folder `STRAIGHTJACKET_USERS_DIR` names.

- The game in play is saved after every change to one slot, `persistence.default_save_name` in `engine/persistence.yaml`, which selecting a player loads. Save as writes a copy under a name of the player's; Load brings a save into play, which then goes on in that slot, so a named save stays as it was saved (`web/handlers.py` → `_autosave`).
- Loading is strict. The file is read as `persistence.py` → `SavedGame`, the game with the turn's snapshot and the chat beside it, by the reader that binds the configuration, which refuses the same things (Typed binding below), a null where the type allows none among them. For a save the reader refuses, `load_game` raises `IncompatibleSaveError`, whose message names the value by its path; the web handler logs it and tells the player that the save is incompatible.
- The list of saves (`list_saves_with_info`) reads only a save's header fields, so it also shows a save that no longer loads. It leaves out a file in the saves folder that is not readable JSON with those fields, and logs a warning, since one stray file should not keep the player from the other saves.

**No second store.** The dataclasses are the only store; the Director's tool and the prompts filter them directly. A copy for queries would have to be rebuilt after every change and cost more than the filtering it saves, while the state of a solo game stays small enough to fit in memory.

## Configuration

Configuration lives in yaml stores that are directories with one file per subsystem or topic:

- `gamemaster`, `crafters`, and `ruleset`: the rules and numbers of each layer;
- `engine`: the engine's own numbers and text that are no rule (the AI's text, the parser, retry, persistence);
- `prompts`: AI-facing text; `strings`: user-facing text; `emotions`: emotion scoring.

Each loader merges its directory and raises on a key that two files define. Code reaches them only through `eng()`, `gm()`, `crafter()`, `rules()`, `get_prompt()` with `get_prompt_prefix()`, `t()` with `all_strings()`, and `importance_map()` with `keyword_boosts()`. Game content comes from the Datasworn JSON and the Mythic and Adventure Crafter data in the `data` folder, each setting from a yaml file in `data/settings`.

**`config.yaml`** stays a single, user-edited file for the server, the providers, and the model assignment, bound like the stores (Typed binding below) to the dataclasses of `config_loader.py`. Startup stops, with a message that names it, on a key it does not know or lacks, a value of another type than its field's, such as a quoted number, a role under `ai.role_cluster` that the engine does not know or one it lacks, a cluster on a provider it does not define, or a role mapped to a cluster it does not define. A cluster's `extra_body` is not checked at startup: the provider's adapter reads it, and the Anthropic adapter checks at the call the three keys it hands the SDK as typed values (`docs/ai.md`, Provider adapters).

**At startup.** `python run.py` and Elvira call `game/startup.py` → `check_startup`, which loads the four stores, so that a wrong value in their yaml stops the start and not the turn that first reads it, and then checks the configured models (`docs/ai.md`, Routing and the startup check). The prompts, the strings, and the emotions load at their first use.

**Typed binding.** Every yaml block is a field of its folder's settings class, bound at load time by `serialization.py` → `build_strict`, the reader that also loads a save, which reads the annotations of that class and of every dataclass below it: `EngineSettings` in `engine_config.py` with `engine_config_dataclasses.py`, `GameMasterSettings` in `gamemaster/config.py` with `gamemaster/config_types.py`, `CrafterSettings` in `crafters/config.py`, and `RulesetSettings` in `ruleset/config.py` with `ruleset/config_types.py`. Code reads a block as `gm().subsystem.field`, `rules().subsystem.field`, and so on.

- At every depth, the top level included, a key no field holds raises, and so do a field without its key and a value of another type than its field's, such as text for a number or a list for a mapping; a whole number serves where a fraction is asked, and a field that names several plain types takes any of them. The error names the value by its path in the yaml.
- A top-level section that no code reads fails the orphan-key scan (CONTRIBUTING.md).
- A block whose keys are themselves domain content, such as move names or dispositions, is a mapping, which extends without a Python change.
- The emotions are bound the same way, to `EmotionSettings` in `emotions_loader.py`; the prompts and the strings are text by key, and a value that is no text raises (`yaml_merge.py` → `load_text_dir`).
- The Mythic and Adventure Crafter data files are bound the same way, each as a whole at its first use: `gamemaster/mythic_data.py` → `MythicData` and `crafters/adventure_crafter.py` → `AdventureCrafterData`. A table of Mythic's that no code reads yet is a field held as it is.
- A Datasworn file is an external structure that holds far more than the engine reads, so it is not bound whole. `setting/loader.py` reads its oracles and truths into dataclasses and `ruleset/datasworn.py` its assets; the ruleset's readers take the moves, stats, meters, impacts, and special tracks from it. Each value goes through `serialization.py` → `read_key`, which refuses another type than the one asked and names the value by its path.
- A setting's yaml is parsed in `setting/packages.py`, since a setting inherits what it leaves out (`docs/settings.md`, Inheritance). Its `oracle_paths`, `vocabulary`, and `creation_flow` are bound by `build_strict`, with what the yaml leaves out filled in as absent; a key written without a value raises.
- Two blocks whose yaml shape is not their dataclass's are parsed by hand in `ruleset/config.py`: the move availability rules, and the move outcomes, where an entry's `handler` names the dataclass of its `params`.

## Interface and accessibility

A single HTML page with inline CSS and JavaScript and no build step. The server sends JSON over one WebSocket; the client renders it.

**Built for screen readers.** Semantic HTML, a heading per scene for navigation, an ARIA live region that reads each narration aloud, and native form controls. Narration streams sentence by sentence, so the screen reader starts after the first sentence (`docs/ai.md`, Narration streaming).

**The page.** Before play it shows the players and then character creation. During play there is one text input plus the Save/Load and Retire buttons. Everything else appears only when needed, as overlays with native controls: the momentum-burn offer, story completion, succession, and the retire confirmation.

**The end of a game.** On a turn that ends the game or completes the story, the burn offer comes first, and the end is announced once the player has taken or declined it (`web/handlers.py` → `_settle_turn_end`). A game that is over answers new input and a correction with what still stands, the burn offer or else its succession, and a reconnect does the same; a reload drops a standing burn offer and shows the succession (`send_player_selected`).

**Commands.** `/status`, `/score`, `/tracks`, and `/threats` are answered by the engine without an AI call, in narrative form: "seriously wounded" rather than "health 2". `/advance` spends experience, `recap` asks the AI for a recap, and a line starting with `##` is a correction.

**No numbers in the story.** Narration and status never show numbers, dice, or system terms; the burn offer, `/advance`, and character creation name the costs and values the player chooses among.

## Constraints

**Single session.** One player at a time (SECURITY.md, Session model). Module-level accumulators (the pending random events) assume it; several sessions would need per-session state.
