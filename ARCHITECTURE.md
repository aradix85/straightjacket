# Architecture

How a turn flows through the system. Read this first.

## Turn Pipeline

Player types "I search the room" → engine returns narration + updated game state.

```
player input
  ↓
Scene Test (mechanics/scene.py) → d10 vs chaos factor: expected / altered / interrupt
  ↓
Brain (ai/brain.py)           → single-call classification with injected game state (no tool calling)
  ↓
Roll (mechanics/consequences.py) → 2d6+stat vs 2d10, result: STRONG_HIT / WEAK_HIT / MISS
  ↓
Consequences (game/finalization.py) → move outcome, combat position, clock ticks, crisis check
  ↓
NPC Activation (npc/activation.py) → TF-IDF scores decide which NPCs get full context
  ↓
Prompt Builder (prompt_builders.py) → assembles XML prompt with world, NPCs, result, scene type
  ↓
Narrate (game/finalization.py → narrate_scene)
  → narrator call (ai/narrator.py) → prose with conversation memory
  → parser (parser.py) → strips leaked metadata (10-step cleanup)
  → validator (ai/validator.py) → hybrid rule-based + LLM check, retries with prompt stripping
  ↓
Post-Narration (game/finalization.py → apply_post_narration)
  → engine memories, scene context, AI metadata extraction (ai/metadata.py)
  ↓
Scene-End Bookkeeping         → chaos adjustment, list weight updates, consolidation
  ↓
Director (director.py)        → NPC reflections, AIMS generation, act transitions
  ↓
DB Sync (db/sync.py)          → full GameState → SQLite for query access
  ↓
Save (persistence.py)         → JSON to users/{name}/saves/
```

Dialog turns skip Roll and Consequences. The rest is the same.

## Module Ownership

Where to find things. If you want to change X, edit Y.

| I want to change... | Edit this |
|---|---|
| Game rules, damage, NPC limits | `engine.yaml` (no Python) |
| AI prompts (narrator, brain, director) | `prompts/*.yaml` (directory set in `config.yaml` → `ai.prompts_dir`) |
| Emotion scoring, keyword boosts | `emotions/*.yaml` (no Python) |
| UI text | `strings/*.yaml` (no Python) |
| Server port | `config.yaml` (no Python) |
| AI model assignment per role | `config.yaml` → `clusters` (per-cluster model + parameters), `role_cluster` (remap role to cluster) |
| Provider-specific params per role | `config.yaml` → `extra_body` (per-cluster) |
| Move types or stat assignments | Datasworn JSON (moves loaded automatically per setting) |
| A new setting (genre + constraints) | `data/settings/your_setting.yaml` + Datasworn JSON |
| How dice rolls work | `mechanics/consequences.py` → `roll_action`, `roll_progress` |
| Move outcome effects | `engine.yaml` → `move_outcomes` (no Python for simple moves) |
| Move outcome handlers (suffer, threshold, recovery) | `mechanics/move_outcome.py` |
| Move outcome resolution + crisis check | `game/finalization.py` → `resolve_action_consequences`, `ActionOutcome` |
| Narrator call + parse + validate | `game/finalization.py` → `narrate_scene` (all four narration paths) |
| Move data model and loading | `datasworn/moves.py` → `Move`, `get_moves` |
| Combat position (in_control / bad_spot) | `models_base.py` → `WorldState.combat_position`, set by move outcomes |
| How the narrator is prompted | `prompts/*.yaml` → task templates; `prompt_builders.py` → XML assembly |
| NPC memory / activation logic | `npc/memory.py`, `npc/activation.py` |
| Story structure / act tracking | `story_state.py` → `get_current_act`, `check_story_completion`; `ai/architect.py` |
| Correction (## undo) flow | `correction/` (package: `analysis.py` brain call, `ops.py` atomic state patches, `orchestrator.py` snapshot restore + re-narrate) |
| Momentum burn re-narration | `game/momentum_burn.py` → `process_momentum_burn` |
| Save format | `models.py` → SerializableMixin on each dataclass (no manual `to_dict`/`from_dict`) |
| User/save directory management | `user_management.py` → `create_user`, `get_save_dir`, `_safe_name` |
| WebSocket protocol / UI | `web/handlers.py`, `web/static/index.html` |
| Character creation validation | `game/game_start.py` → `validate_stats`, stat arrays in `engine.yaml` |
| Creation data for client | `web/serializers.py` → `build_creation_options` |
| Setting-specific creation flow | `data/settings/*.yaml` → `creation_flow` block |
| Progress track mechanics | `models_base.py` → `ProgressTrack`, `PROGRESS_RANKS` |
| Mythic threads/characters lists | `models_story.py` → `ThreadEntry`, `CharacterListEntry` |
| Truths in narrator prompt | `prompt_blocks.py` → `truths_block` |
| Pacing (engine-computed) | `mechanics/world.py` → `get_pacing_hint`; scene structure via `mechanics/scene.py` |
| Act transitions (engine-computed) | `director.py` → `_check_engine_act_transition` |
| Memory emotional weight (engine-computed) | `mechanics/engine_memories.py` → `derive_memory_emotion`, table in `engine.yaml` |
| Database queries (NPCs, memories, threads, clocks, threats) | `db/queries.py` → `query_npcs`, `query_memories`, `query_threads`, `query_clocks` |
| Database sync after state changes | `db/sync.py` → `sync(game)`, called by turn, creation, correction, restore, load |
| Tool definitions for AI agents | `tools/registry.py` → `@register("director")`, `get_tools(role)` |
| Tool execution and iterative loop | `tools/handler.py` → `execute_tool_call`, `run_tool_loop` |
| Built-in Director tools | `tools/builtins.py` → `query_npc`, `query_active_threads`, `query_active_clocks` |
| Engine query functions (no tool registration) | `tools/builtins.py` → `available_moves`, `fate_question`, `roll_oracle`, `query_npc_list`, `list_tracks` |
| Track-creating moves | `engine.yaml` → `track_creating_moves` (no Python) |
| Track lifecycle (creation, completion) | `game/tracks.py` → `find_progress_track`, `complete_track`, `sync_combat_tracks` |
| Combat track ↔ combat_position sync | `game/tracks.py` → `complete_track` (clears position), `sync_combat_tracks` (orphan cleanup) |
| Scene challenge progress routing | `engine.yaml` → `scene_challenge_progress_moves`; `game/turn.py` action path |
| Which moves are available in a game state | `tools/builtins.py` → `available_moves`, `_is_move_available` (filters by `status == "active"`) |
| NPC bond level | `npc/bond.py` → `get_npc_bond` (reads connection track, not NpcData) |
| Status commands (/status, /score) | `web/handlers.py` → `handle_status_query`; `web/serializers.py` → `build_narrative_status` |
| Status command /tracks | `web/handlers.py` → `handle_tracks_query`; `web/serializers.py` → `build_tracks_status` |
| Status command /threats | `web/handlers.py` → `handle_threats_query`; `web/serializers.py` → `build_threats_status` |
| Fate questions (yes/no) | `mechanics/fate.py` → `resolve_fate`, `resolve_likelihood`; `engine.yaml` → `fate` |
| Scene structure (expected/altered/interrupt) | `mechanics/scene.py` → `check_scene`, `SceneSetup` |
| Random events and meaning tables | `mechanics/random_events.py` → `generate_random_event`, `roll_event_focus`, `roll_meaning_table` |
| Mythic list maintenance (weight, consolidation) | `mechanics/random_events.py` → `add_thread_weight`, `add_character_weight`, `consolidate_threads` |
| Consequence sentence templates | `engine.yaml` → `consequence_templates`, `pay_the_price` (no Python) |
| Consequence sentence generation | `mechanics/consequences.py` → `generate_consequence_sentences` |
| NPC stance matrix | `engine.yaml` → `stance_matrix` (no Python) |
| NPC stance resolution | `mechanics/stance_gate.py` → `resolve_npc_stance`, `NpcStance` |
| Information gate levels | `engine.yaml` → `information_gate` (typed `InformationGateConfig`) |
| Information gate computation | `mechanics/stance_gate.py` → `compute_npc_gate` |
| Gate-filtered NPC prompt data | `prompt_builders.py` → `_npc_block` (gate 0–4 filtering) |
| Threat menace track, Forsake Your Vow | `engine.yaml` → `threats`; `mechanics/threats.py` → `advance_menace_on_miss`, `tick_autonomous_threats`, `resolve_full_menace` |
| Threat-vow coupling | `models_base.py` → `ThreatData.linked_vow_id`; `game/tracks.py` → `complete_track` resolves linked threat |
| Impacts (wounded, shaken, etc.) | `engine.yaml` → `impacts` (typed `ImpactConfig`); `mechanics/impacts.py` → `apply_impact`, `clear_impact`, `blocks_recovery`, `recalc_max_momentum` |
| Legacy tracks, XP, asset advancement | `engine.yaml` → `legacy` (typed `LegacyConfig`); `mechanics/legacy.py` → `mark_legacy`, `apply_threat_overcome_bonus`, `advance_asset`; `CampaignState.legacy_quests/bonds/discoveries` |
| NPC name generation | `npc/naming.py` → `roll_oracle_name`; `data/settings/*.yaml` → `oracle_paths.names` |
| Validator context bundling | `ai/rule_validator.py` → `ValidationContext` (adding new check = 1 field + 1 build line + 1 check call) |
| Architect blueprint validation | `ai/architect_validator.py` → `validate_architect`, `_check_blueprint_text_fields` |

## AI Model Assignment

The engine assigns models to AI roles via clusters. Each cluster groups roles that share a model and default parameters. Resolution order: per-role model override → cluster model. `model_for_role(role)` is the single entry point — no module ever hardcodes a model string.

```
Cluster          Roles                                              Needs
─────────────────────────────────────────────────────────────────────────────
narrator         narrator                                           prose generation (creative writing)
creative         architect, director                                genre-aware structured output + tool calling
classification   brain, correction                                  input parsing, json_schema
analytical       validator, validator_architect, narrator_metadata,  constraint checking, data extraction
                 opening_setup, revelation_check, chapter_summary,
                 recap
```

Config structure in `config.yaml`:

```yaml
ai:
  clusters:
    narrator:
      model: "qwen-3-235b-a22b-instruct-2507"
      temperature: 0.7
      top_p: 0.8
      max_tokens: 8192
      max_retries: 3
    creative:
      model: "gpt-oss-120b"
      temperature: 0.7
      ...
    analytical:
      model: "gpt-oss-120b"
      temperature: 0.5
      ...
  # Remap a role to a different cluster:
  role_cluster:
    architect: "analytical"
```

Clusters are the single source of truth. `sampling_params(role)` resolves all call parameters from the role's cluster. `model_for_role(role)` resolves the model. No per-role overrides — to change a role's parameters, change the cluster or remap the role via `role_cluster`.

`max_tool_rounds` is an engine mechanical limit, configured in `engine.yaml` under `pacing.max_tool_rounds`.

Elvira test bot model is configured separately in `tests/elvira/elvira_config.yaml` → `ai.bot_model`.

## File Map

```
src/straightjacket/
├── engine/
│   ├── models.py            # Re-export hub for all dataclasses
│   ├── models_base.py       # EngineConfig, Resources, ProgressTrack, WorldState, ClockData/Event, RandomEvent, FateResult
│   ├── models_npc.py        # NpcData, MemoryEntry
│   ├── models_story.py      # ThreadEntry, CharacterListEntry, NarrativeState, StoryBlueprint, etc.
│   ├── engine_config.py     # EngineSettings composition + _build_strict / load_strict yaml parse; re-exports dataclasses
│   ├── engine_config_dataclasses.py  # 63 subsystem dataclasses that bind engine.yaml sections
│   ├── format_utils.py      # PartialFormatDict (shared by prompt_loader, strings_loader)
│   ├── mechanics/
│   │   ├── world.py            # Location matching, chaos adjustment, time, pacing, story structure
│   │   ├── resolvers.py        # Position, effect, time progression, move category
│   │   ├── consequences.py     # Dice rolls (action + progress), clocks, momentum burn, consequence sentences
│   │   ├── move_outcome.py     # Data-driven move outcome resolution, effect parser, handlers
│   │   ├── stance_gate.py      # NPC stance resolution, information gating
│   │   ├── engine_memories.py  # Memory emotion derivation, engine memories, scene context
│   │   ├── fate.py             # Mythic GME 2e fate chart, fate check, likelihood resolver
│   │   ├── random_events.py    # Event focus, meaning tables, random event pipeline, list maintenance
│   │   ├── scene.py            # Scene structure: chaos check, altered/interrupt scenes
│   │   ├── threats.py          # Threat menace advancement, autonomous ticks, Forsake Your Vow
│   │   ├── impacts.py          # Impact apply/clear, max_momentum recalc, recovery blocking
│   │   └── legacy.py           # Legacy tracks (quests/bonds/discoveries), XP, asset advancement
│   ├── parser.py            # Narrator output cleanup (10 regex steps)
│   ├── correction/          # ## correction subpackage
│   │   ├── __init__.py      # Re-exports process_correction, call_correction_brain, _apply_correction_ops
│   │   ├── analysis.py      # Correction brain call (classify misread vs state error)
│   │   ├── ops.py           # Atomic state patches (npc edit/split/merge, location, time, backstory)
│   │   └── orchestrator.py  # Snapshot restore, optional re-roll, re-narrate, post-narration flow
│   ├── director.py          # Story steering, NPC reflections, act transitions
│   ├── persistence.py       # Save/load
│   ├── story_state.py       # Act tracking, revelation timing, story completion check
│   ├── prompt_builders.py   # Narrator prompt XML assembly (task text from prompts/)
│   ├── prompt_blocks.py     # Reusable XML blocks (content boundaries, backstory, etc.)
│   ├── prompt_loader.py     # Merges prompts/*.yaml (directory from config.yaml ai.prompts_dir)
│   ├── config_loader.py     # Reads config.yaml, provides cfg() singleton
│   ├── engine_loader.py     # Merges engine/*.yaml, provides eng() singleton
│   ├── emotions_loader.py   # Merges emotions/*.yaml
│   ├── logging_util.py      # log(), setup_file_logging(), get_logger()
│   ├── user_management.py   # User CRUD, save directories, _safe_name, config load/save
│   ├── ai/
│   │   ├── provider_base.py # AIProvider protocol + retry wrapper
│   │   ├── provider_anthropic.py
│   │   ├── provider_openai.py  # Any OpenAI-compatible API
│   │   ├── brain.py         # Single-call move classification (prompt injection, no tools)
│   │   ├── narrator.py      # Prose generation + metadata extraction calls
│   │   ├── metadata.py      # Apply extracted metadata to game state
│   │   ├── architect.py     # Story blueprint, recap, chapter summary
│   │   ├── architect_validator.py # Blueprint genre fidelity check (rule-based + LLM)
│   │   ├── validator.py     # Narrator constraint checking (rule-based + LLM) and retry loop
│   │   ├── rule_validator.py # Instant rule-based checks (player agency, result integrity, genre, format)
│   │   ├── json_utils.py    # Shared JSON extraction from text responses
│   │   └── schemas.py       # JSON output schemas (config-driven)
│   ├── npc/
│   │   ├── bond.py          # get_npc_bond: bond from connection track
│   │   ├── matching.py      # Name lookup, fuzzy matching, edit distance
│   │   ├── memory.py        # Importance scoring, retrieval, consolidation
│   │   ├── activation.py    # TF-IDF context selection for prompts
│   │   ├── lifecycle.py     # Identity merging, retiring, reactivation
│   │   ├── naming.py        # Oracle-based NPC name generation
│   │   └── processing.py    # Narrator metadata → NPC state changes
│   ├── game/
│   │   ├── turn.py          # Main turn pipeline (process_turn)
│   │   ├── tracks.py        # Progress track mechanics (find, complete, sync, oracle rolls)
│   │   ├── momentum_burn.py # Momentum burn re-narration pipeline
│   │   ├── game_start.py    # Character creation → opening scene
│   │   ├── chapters.py      # Epilogue, new chapter orchestration
│   │   ├── setup_common.py  # Shared opening setup logic
│   │   ├── finalization.py  # Shared pre- and post-narration: outcome resolution, crisis, memories, metadata
│   │   └── director_runner.py # Deferred Director call
│   ├── datasworn/
│   │   ├── loader.py        # Reads Datasworn JSON (oracles, assets, moves)
│   │   ├── moves.py         # Move dataclass, loader, expansion merge, cached accessor
│   │   └── settings.py      # Setting packages (vocabulary, genre constraints)
│   ├── db/
│   │   ├── schema.sql       # Table definitions (8 tables, mirrors dataclasses)
│   │   ├── connection.py    # In-memory SQLite singleton (init, get, reset, close)
│   │   ├── sync.py          # Full GameState → database sync (replace, not diff)
│   │   └── queries.py       # Read-only query functions → dataclass instances
│   └── tools/
│       ├── registry.py      # @register decorator, type hints → OpenAI tool schemas
│       ├── handler.py       # Tool dispatch, iterative tool-call loop
│       └── builtins.py      # Built-in query tools (Director) and engine functions (fate, oracle, moves)
├── web/
│   ├── server.py            # Starlette app, WebSocket endpoint, dispatch
│   ├── handlers.py          # One async function per protocol message type
│   ├── session.py           # Session dataclass (all mutable server state)
│   ├── serializers.py       # Game state → client JSON (i18n labels resolved)
│   └── static/
│       └── index.html       # Single-page app (HTML + CSS + JS inline)
├── i18n.py                  # String lookup (t()), label getters
└── strings_loader.py        # Merges strings/*.yaml
```

## Key Design Decisions

**Config-driven game logic.** Move outcomes, NPC limits, disposition shifts, damage tables — all in engine.yaml or Datasworn JSON. Adding a move means adding one YAML entry to `move_outcomes`. No Python change. Move definitions (stats, roll types, trigger conditions) load directly from Datasworn JSON per setting.

**Modular yaml stores.** Every yaml store in the repo is a directory of files, not a single file: `engine/` (58 files, one per subsystem), `emotions/` (3), `prompts/` (7 cluster-files), `strings/` (18, one per dotted-key prefix). Each loader globs its directory, merges top-level keys, raises on duplicates. Callsites only talk to `eng()` / `get_prompt()` / `t()` / `importance_map()` — filesystem layout is invisible to the rest of the codebase. `config.yaml` stays single (small, user-edited). `data/settings/*.yaml` was already one file per setting.

**Subpackage public API via `__init__.py`.** Subpackages `mechanics`, `npc`, `game`, `db`, and `tools` each expose their public API by re-exporting from their submodules in `__init__.py`. Callers import `from straightjacket.engine.mechanics import roll_action`, not `from straightjacket.engine.mechanics.consequences import roll_action`. This keeps the internal module layout free to change without breaking consumers. The top-level `engine/__init__.py` deliberately does NOT re-export — it is a package marker only (8 lines, docstring). `models.py` is a separate re-export hub for every dataclass across `models_base.py`, `models_npc.py`, and `models_story.py`. The F401 ignore in `pyproject.toml` for these seven files covers this intentional public-API surface. The 0.48.1 and 0.51 audits removed the top-level `engine/__init__.py` and `ai/__init__.py` hubs because they had zero consumers; the remaining hubs stay because they do.

**Typed dataclasses everywhere.** GameState has sub-objects (Resources, WorldState, NarrativeState, CampaignState). NpcData has 17 fields. MemoryEntry has 10. Move has 15 fields with typed trigger conditions and roll options. Attribute access, never dict-style. `SerializableMixin` handles serialization; complex classes override `to_dict`/`from_dict` manually.

**Two-call pattern.** Narrator writes pure prose. A second call on the analytical cluster model extracts NPC-related metadata (new NPCs, renames, details, deaths). Same pattern for opening_setup, revelation_check, recap, and chapter_summary. The analytical cluster typically uses a cheaper/faster model for these structured output calls.

**Snapshot/restore.** `GameState.snapshot()` captures all mutable state before a turn. `restore()` reverts everything atomically. Used by correction (##) and momentum burn.

**Provider abstraction.** `AIProvider` protocol with two implementations (Anthropic, OpenAI-compatible). The engine never imports provider SDKs directly. `create_with_retry` handles transient errors with exponential backoff. Multi-model: config.yaml assigns models via four clusters — narrator (Qwen 3 for prose), creative (GPT-OSS for architect, director), classification (GPT-OSS for brain, correction), analytical (GPT-OSS for validator, metadata, recap, and other structured output roles). Clusters are the single source of truth for all call parameters. `model_for_role(role)` resolves the model; `sampling_params(role)` resolves temperature, top_p, max_tokens, max_retries, and extra_body. The provider stores no model state.

**Minimal UI.** Single HTML page, no build step, no npm. Server sends JSON, client renders. Scene headings for screen reader navigation, aria-live for automatic narration readout. One button (Save/Load), one text input. Status via `/status` and `/score` text commands — engine answers directly, no AI call. Status output is narrative, not mechanical: "seriously wounded" instead of "health 2", "growing trust" instead of "bond 4/10". The player never sees numbers, dice, or system terms.

**Progress tracks as dataclass.** ProgressTrack has rank and ticks; ticks-per-mark by rank lives in `engine.yaml` under `progress.track_types.default.ticks_per_mark` (troublesome=12, epic=1 on the default track), with the `track_types` map extensible for future variants. Status (active/completed/failed) on the track. Background vow becomes a track at creation. Track-creating moves defined in engine.yaml `track_creating_moves` — engine creates tracks from Brain output. Connection tracks replace NpcData.bond: `get_npc_bond(game, npc_id)` reads connection track filled_boxes.

**Mythic lists seeded at creation.** Threads list starts with the background vow (weight 2) plus any tensions derived from truth selections via engine.yaml templates. Characters list starts with the vow subject (if provided) and opening scene NPCs. Both lists are in NarrativeState for snapshot/restore.

**Truths as world context.** Player truth selections stored in GameState.truths and injected into every narrator prompt as a `<world_truths>` block. The narrator treats them as established canon. Truths that match engine.yaml patterns automatically seed tension threads.

**AI surface minimization.** Every value derivable from game state is computed by the engine. Director pacing is computed from scene_intensity_history, not requested from the AI. Act transitions fire when scene_count exceeds act range — deterministic, no AI flag. Memory emotional_weight is derived from (move_category, result, disposition) via engine.yaml lookup. Opening scene clock and time_of_day are engine-determined before any AI call. The AI receives results, not choices.

**Data-driven move outcomes.** `resolve_move_outcome` reads structured effect lists from engine.yaml per move per result. Simple moves (momentum, resources, progress, position) are pure data — no Python. Complex moves (suffer, threshold, recovery) use named handlers that share patterns across moves. Engine-specific moves (`dialog`, `ask_the_oracle`, `world_shaping`) live alongside Datasworn moves in `engine.yaml engine_moves:` — single source of truth read by `available_moves`, the brain-output schema, and the narrator. The `available_moves` function filters moves by game state (combat position, active tracks); Brain receives the filtered list in its prompt. Consequence sentences generated from outcome strings via engine.yaml templates.

**Shared outcome resolution.** Three codepaths produce action narration: normal turns, corrections (input_misread), and momentum burns. All three share `resolve_action_consequences` in `game/finalization.py` — move outcome, combat position, MISS clock ticking, crisis check. They also share `apply_progress_and_legacy` — consumes `outcome.progress_marks` on the active track and `outcome.legacy_track` on campaign legacy tracks. Without this shared step, correction and burn would silently drop progress and legacy rewards from the re-resolved outcome after the snapshot restore. Turn.py adds WEAK_HIT clock ticking, track completion on progress rolls, and scene_challenge routing (intentionally turn-only — these are mechanical turn boundaries, not re-narration events). All four narration paths (turn dialog, turn action, correction, burn) share `narrate_scene` — narrator call, parse, optional validation — in one call. Post-narration state mutations share `apply_post_narration` from the same module.

**NPC behavioral stance.** Engine computes per-NPC stance from disposition, bond (via connection track), and move category via engine.yaml stance matrix (60 entries). The narrator receives `stance="evasive" constraint="One fact, then silence."` instead of raw disposition values. The engine tells the narrator how the NPC behaves, not just how they feel.

**Information gating.** Per-NPC gate level (0–4) controls what enters the narrator prompt. Gate 0 = name + description (stranger). Gate 4 = full secrets. Computed from scenes known, gather_information successes, bond level, and stance cap. The narrator cannot reveal what it doesn't have. Stance caps prevent hostile NPCs from being too transparent regardless of bond.

**Database as read model.** SQLite (in-memory, stdlib) mirrors GameState after every turn, creation, correction, restore, and load. GameState dataclasses remain the write model — all mutations go through Python. The database provides indexed queries for prompt builders, tool handlers, and future NPC trigger evaluation. Ephemeral: rebuilt from GameState on load/restore, no migration burden. JSON save files remain the persistence format.

**Tool calling.** Director uses decorator-based registry (`@register("director")`) producing OpenAI function calling schemas from Python type hints. Iterative handler loop: AI calls tool → engine executes → result appended → AI continues, with configurable round limit. Tools are read-only: they query GameState and database but never mutate. Director uses two-phase: tool loop for context, then json_schema for structured output. Brain does not use tool calling — all game state is injected via prompt (moves, NPCs, tracks). Brain's fate_question and oracle_table fields are resolved by the engine after classification. The core principle ("tools determine results, AI narrates") is preserved across both roles: the engine produces all mechanical outcomes. Only the mechanism (prompt injection for Brain vs tool calls for Director) differs — see "Deliberate divergences from the design document" below.

**Fate system (Mythic GME 2e).** Probabilistic yes/no questions about the fiction. Two methods: fate chart (9×9 odds/chaos matrix, d100) and fate check (2d10 + modifiers). Both produce four outcomes (yes, no, exceptional yes, exceptional no) and can trigger random events via the doublet rule. Likelihood resolver maps game state (NPC disposition, chaos, resources) to odds level via engine.yaml lookup table. Brain sets `fate_question` field; engine resolves after classification.

**Scene structure (Mythic GME 2e).** Every turn starts with a scene test: d10 vs chaos factor. Expected (roll > CF), altered (roll ≤ CF, odd), or interrupt (roll ≤ CF, even). Altered scenes roll on the Scene Adjustment Table. Interrupt scenes generate a random event via the pipeline. Scene test runs before Brain call. Replaces the old chaos interrupt system.

**Random events.** Four-step pipeline: event focus (d100, 12 categories) → target selection from weighted Mythic lists → meaning table roll (actions or descriptions) → structured `RandomEvent` assembly. Events fire on fate doublets and interrupt scenes. `<random_event>` and `<interrupt_scene>` tags injected into narrator prompt. List maintenance: present NPCs/threads get weight bumps, new NPCs added to characters list, consolidation at 25 entries.

**Director reduction.** Director no longer advises on pacing — that is fully engine-computed from scene structure and narrative direction. Director retains NPC reflections (AIMS, arc updates, description updates) and optional chapter summaries. Act transitions are engine-computed from scene count vs act range.

## Known Limitations

**Validator is model-specific.** The hybrid validator (rule-based + LLM) is tuned for Qwen 3 patterns on Cerebras. The rule validator catches common violations (player agency regex patterns, atmospheric drift wordlists, split-monologue detection). The LLM validator catches the rest — resolution pacing (NPC speech content), genre physics, consequence compliance. Resolution pacing remains the hardest violation to correct: Qwen's creative writing training biases it toward information-rich NPC dialog. Retry success rate is ~60% for pacing violations. Switching narrator model will require re-tuning: new agency patterns, different drift words, different pacing tendencies.

**Single session.** One player at a time. The module-level accumulators (`_pending_events`, `_token_log`) and the in-memory SQLite database assume single-threaded access. Multi-session would require per-session state isolation.

**No faction system yet.** NPCs act individually via agenda and goal-clocks. Faction-level schemes, reputation, and NPC loyalty thresholds are not implemented. The "world moves independently" principle is partially realized through autonomous clock ticks and NPC agency checks, not through faction dynamics.

**No fiction generators yet.** NPCs, locations, and encounters are generated by the AI from context, not from structured oracle table rolls. The design document specifies hybrid generators (oracle tables produce structure, AI writes description within that structure). This means the engine currently relies on AI invention where it should rely on oracle-constrained generation.

**No NPC-player emotional dynamics yet.** The engine tracks NPC disposition and bond but not relationship-altering events (broken promises, betrayals, sacrifices), emotional requests, or refusal/concession history. NPCs react to standing relationship state, not to the dynamic history of the relationship.

**No asset mechanics.** Assets are stored as ID strings but have no mechanical effect. The modifier pipeline (stat bonuses, rerolls, companion health, vehicle condition) is not implemented.

**Blueprint is AI-generated at game start.** The story architect produces a 3-act or Kishōtenketsu blueprint via a single AI call. Quality varies by model — Qwen trends toward supernatural horror patterns. The engine compensates with mood sanitization and genre validation, but blueprint quality directly affects Director guidance and narrative direction. Replacing the AI-generated blueprint with a table-driven plot structure (Adventure Crafter) is planned; doing so would be consistent with the design document principle that the engine decides, the AI narrates.

## Deliberate divergences from the design document

Two places where Straightjacket departs from the design document's architectural recommendations. Both were retained on empirical grounds, not discarded from the document.

**Input parsing as a separate call.** The design document specifies that input parsing is integrated into the single narrator call — the AI classifies the action type and narrates the result in one response. Straightjacket uses a separate Brain call that classifies input before the narrator writes prose. This split was already present in EdgeTales, where the integrated approach did not produce reliable classification. Straightjacket preserved the split on the same empirical grounds. Two independent implementations reaching the same conclusion is stronger evidence than a single project running into the issue.

**Tool calling limited to Director.** The design document proposes tool calling as the central engine-AI communication mechanism — the AI requests rolls, queries NPC state, and accesses oracles via callable tools. Straightjacket uses tool calling only for Director. Brain receives all game state via prompt injection instead. Brain tool calling was tested and found to cost ~13× the tokens (67K vs 5K over 10 turns) without improving classification quality — see CHANGELOG 0.46.50. The core principle ("tools determine results, AI narrates") is preserved; only the mechanism (prompt injection vs tool calls) differs.

## Testing

```bash
python -m pytest tests/ -v          # ~15 seconds, ~786 tests
python tests/elvira/elvira.py --auto --turns 5   # direct engine (needs API key)
python tests/elvira/elvira.py --ws --auto --turns 5  # via WebSocket server
```

Elvira is the real integration test. Direct mode drives the engine with an AI player bot, checks state invariants after every turn, runs narration quality checks, tests the correction pipeline, and verifies NPC spatial consistency. WebSocket mode does the same but through the full server stack.

## Adding a New AI Provider

1. Create `ai/provider_yourname.py` implementing `AIProvider` protocol (see `provider_base.py`)
2. Add a branch in `ai/api_client.py` → `get_provider()`
3. Set `ai.provider` in config.yaml

## Adding a New Setting

Settings are data packages that combine a Datasworn JSON file (game content: moves, oracles, assets) with a settings YAML file (engine integration: vocabulary, genre constraints, oracle paths).

### Step by step

1. Place the Datasworn JSON at `data/<datasworn_id>.json`, where `<datasworn_id>` is the value you will declare inside the yaml. Datasworn JSON files contain the game's mechanical content: moves, oracles, assets (paths/companions/etc). See [github.com/rsek/datasworn](https://github.com/rsek/datasworn) for the format.
2. Create `data/settings/<id>.yaml` (use `data/settings/starforged.yaml` as template). The yaml stem is the setting id used by the engine; `datasworn_id` inside the yaml points at the JSON file.
3. The setting appears in character creation automatically — no Python changes needed.

### Settings YAML format

Parsed strictly at load. Required top-level keys: `id`, `title`, `datasworn_id`, `description`, `oracle_paths`, `vocabulary`, `genre_constraints`. Optional: `parent`, `creation_flow`. Missing required keys raise `KeyError`.

```yaml
id: your_setting                    # yaml stem
title: "Your Setting Name"
datasworn_id: your_setting          # Datasworn JSON basename
description: "One paragraph."
parent: classic                     # Optional: inherits from this setting

vocabulary:
  substitutions: { spaceship: "starship — worn, patched" }
  sensory_palette: "Metal, recycled air, ozone."

genre_constraints:
  forbidden_terms: [magic, spell]
  forbidden_concepts: ["supernatural powers beyond tech level"]
  genre_test: "Could this exist without magic?"
  atmospheric_drift: [eldritch, otherworldly]
  atmospheric_drift_threshold: 2

oracle_paths:
  action_theme: ["core/action", "core/theme"]
  descriptor_focus: ["core/descriptor", "core/focus"]
  names: ["characters/name/given", "characters/name/family_name"]
  backstory: "campaign_launch/backstory_prompts"
  factions: "factions"

creation_flow:
  has_truths: true
  has_backstory_oracle: true
  has_name_tables: true
  has_ship_creation: false
  starting_asset_categories: [companion, module]
```

`vocabulary` keeps AI in-setting. `genre_constraints` feeds rule and architect validators. `oracle_paths.names` drives engine NPC name rolls. `creation_flow` controls client UI steps.

### Inheritance

With `parent:`, blocks inherit from the parent yaml, resolved at load.

`oracle_paths`, `genre_constraints`, `creation_flow`: per-field. Omitted field → parent's value. Present field (even empty) → explicit override. Root settings must specify every field.

`vocabulary`: section-level. Both sub-fields empty → whole block from parent.

Discovery is yaml-only: `list_available()` scans `data/settings/*.yaml`, `get_moves()` reads `parent:` from the child yaml. No Python mapping tables.
