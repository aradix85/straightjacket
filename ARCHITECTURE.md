# Architecture

How a turn flows through the system. Read this first.

## Turn Pipeline

Player types "I search the room" → engine returns narration + updated game state.

```
player input
  ↓
Scene Test (mechanics/scene.py) → keyed > interrupt > altered > expected (keyed branch overrides chaos)
  ↓
Brain (ai/brain.py)           → single-call classification with injected game state (no tool calling)
  ↓
Roll (mechanics/consequences.py) → 2d6+stat vs 2d10, result: STRONG_HIT / WEAK_HIT / MISS
  ↓
Consequences (game/finalization.py) → move outcome, combat position, clock ticks, crisis check
  ↓
NPC Activation (npc/activation.py) → TF-IDF scores decide which NPCs get full context
  ↓
Prompt Builder (prompt_action/prompt_dialog) → assembles XML prompt with world, NPCs, result, scene type
  ↓
Narrate (game/finalization.py → narrate_scene)
  → narrator call (ai/narrator.py) → prose with conversation memory
  → parser (parser.py) → strips leaked metadata (10-step cleanup)
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
| Game rules, damage, NPC limits | `engine/damage.yaml`, `engine/npc.yaml` (no Python) |
| AI prompts (narrator, brain, director) | `prompts/*.yaml` (directory set in `config.yaml` → `ai.prompts_dir`) |
| Emotion scoring, keyword boosts | `emotions/*.yaml` (no Python) |
| UI text | `strings/*.yaml` (no Python) |
| Server port | `config.yaml` (no Python) |
| AI model assignment per role | `config.yaml` → `clusters` (per-cluster model + parameters), `role_cluster` (remap role to cluster) |
| Provider-specific params per role | `config.yaml` → `extra_body` (per-cluster) |
| Move types or stat assignments | Datasworn JSON (moves loaded automatically per setting) |
| A new setting (genre + constraints) | `data/settings/your_setting.yaml` + Datasworn JSON |
| How dice rolls work | `mechanics/consequences.py` → `roll_action`, `roll_progress` |
| Move outcome effects | `engine/move_outcomes.yaml` (no Python for simple moves) |
| Move outcome handlers (suffer, threshold, recovery) | `mechanics/move_handlers.py` |
| Move outcome resolution + crisis check | `game/finalization.py` → `resolve_action_consequences`, `ActionOutcome` |
| Narrator call + parse + validate | `game/finalization.py` → `narrate_scene` (all four narration paths) |
| Move data model and loading | `datasworn/moves.py` → `Move`, `get_moves` |
| Combat position (in_control / bad_spot) | `models_base.py` → `WorldState.combat_position`, set by move outcomes |
| How the narrator is prompted | `prompts/*.yaml` → task templates; `prompt_action.py` / `prompt_dialog.py` / `prompt_boundary.py` → XML assembly; `prompt_shared.py` → shared helpers |
| NPC memory / activation logic | `npc/memory.py`, `npc/activation.py` |
| Story structure / act tracking | `story_state.py` → `get_current_act`, `check_story_completion`; `ai/architect.py` |
| Correction (## undo) flow | `correction/` (package: `analysis.py` brain call, `ops.py` atomic state patches, `orchestrator.py` snapshot restore + re-narrate) |
| Momentum burn re-narration | `game/momentum_burn.py` → `process_momentum_burn` |
| Chapter transition (close, reset, restore) | `game/chapters.py` → `_close_previous_chapter`, `_reset_chapter_mechanics`, `_restore_chapter_mechanics`; narrative summary via `ai/architect.py` → `call_chapter_summary` |
| Character succession (death/despair/retire → new protagonist) | `game/succession.py` → `prepare_succession`, `start_succession_with_character`, `determine_end_reason`; `mechanics/succession.py` → `build_predecessor_record`, `run_inheritance_rolls`, `seed_successor_legacy`, `apply_npc_carryover`; config in `engine/succession.yaml`; `CampaignState.predecessors`, `pending_succession` |
| Save format | `models.py` → SerializableMixin on each dataclass (no manual `to_dict`/`from_dict`) |
| User/save directory management | `user_management.py` → `create_user`, `get_save_dir`, `_safe_name` |
| WebSocket protocol / UI | `web/handlers.py`, `web/static/index.html` |
| Character creation validation | `game/game_start.py` → `validate_stats`, stat arrays in `engine/stats.yaml` |
| Creation data for client | `web/serializers.py` → `build_creation_options` |
| Setting-specific creation flow | `data/settings/*.yaml` → `creation_flow` block |
| Progress track mechanics | `models_base.py` → `ProgressTrack`, `PROGRESS_RANKS` |
| Mythic threads/characters lists | `models_story.py` → `ThreadEntry`, `CharacterListEntry` |
| Truths in narrator prompt | `prompt_blocks.py` → `truths_block` |
| Pacing (engine-computed) | `mechanics/world.py` → `get_pacing_hint`; scene structure via `mechanics/scene.py` |
| Act transitions (engine-computed) | `director.py` → `_check_engine_act_transition` |
| Memory emotional weight (engine-computed) | `mechanics/engine_memories.py` → `derive_memory_emotion`, table in `engine/memory.yaml` |
| Database queries (NPCs, memories, threads, clocks, threats) | `db/queries.py` → `query_npcs`, `query_memories`, `query_threads`, `query_clocks` |
| Database sync after state changes | `db/sync.py` → `sync(game)`, called by turn, creation, correction, restore, load |
| Tool definitions for AI agents | `tools/registry.py` → `@register("director")`, `get_tools(role)` |
| Tool execution and iterative loop | `tools/handler.py` → `execute_tool_call`, `run_tool_loop` |
| Built-in Director tools | `tools/builtins.py` → `query_npc`, `query_active_threads`, `query_active_clocks` |
| Engine query functions (no tool registration) | `tools/builtins.py` → `available_moves` |
| Track-creating moves | `engine/track_moves.yaml` → `track_creating_moves` (no Python) |
| Track lifecycle (creation, completion) | `game/tracks.py` → `find_progress_track`, `complete_track`, `sync_combat_tracks` |
| Combat track ↔ combat_position sync | `game/tracks.py` → `complete_track` (clears position), `sync_combat_tracks` (orphan cleanup) |
| Scene challenge progress routing | `engine/track_moves.yaml` → `scene_challenge_progress_moves`; `game/turn.py` action path |
| Which moves are available in a game state | `tools/builtins.py` → `available_moves`, `_is_move_available` (filters by `status == "active"`) |
| NPC bond level | `npc/bond.py` → `get_npc_bond` (reads connection track, not NpcData) |
| Status commands (/status, /score) | `web/handlers.py` → `handle_status_query`; `web/serializers.py` → `build_narrative_status` |
| Status command /tracks | `web/handlers.py` → `handle_tracks_query`; `web/serializers.py` → `build_tracks_status` |
| Status command /threats | `web/handlers.py` → `handle_threats_query`; `web/serializers.py` → `build_threats_status` |
| Fate questions (yes/no) | `mechanics/fate.py` → `resolve_fate`, `resolve_likelihood`; `engine/fate.yaml` |
| Scene structure (keyed/expected/altered/interrupt) | `mechanics/scene.py` → `check_scene`, `SceneSetup`; `mechanics/keyed_scenes.py` → `evaluate_keyed_scenes` |
| Keyed scene triggers and dispatch | `mechanics/keyed_scenes.py` → `_EVALUATORS`; trigger registry in `engine/keyed_scenes.yaml` |
| Random events and meaning tables | `mechanics/random_events.py` → `generate_random_event`, `roll_event_focus`, `roll_meaning_table` |
| Mythic list maintenance (weight, consolidation) | `mechanics/random_events.py` → `add_thread_weight`, `add_character_weight`, `consolidate_threads` |
| Consequence sentence templates | `engine/consequence_templates.yaml`, `engine/pay_the_price.yaml` (no Python) |
| Consequence sentence generation | `mechanics/consequences.py` → `generate_consequence_sentences` |
| NPC stance matrix | `engine/stance_matrix.yaml` (no Python) |
| NPC stance resolution | `mechanics/stance_gate.py` → `resolve_npc_stance`, `NpcStance` |
| Information gate levels | `engine/information_gate.yaml` (typed `InformationGateConfig`) |
| Information gate computation | `mechanics/stance_gate.py` → `compute_npc_gate` |
| Gate-filtered NPC prompt data | `prompt_shared.py` → `_npc_block` (gate 0–4 filtering) |
| Threat menace track, Forsake Your Vow | `engine/threats.yaml`; `mechanics/threats.py` → `advance_menace_on_miss`, `tick_autonomous_threats`, `resolve_full_menace` |
| Threat-vow coupling | `models_base.py` → `ThreatData.linked_vow_id`; `game/tracks.py` → `complete_track` resolves linked threat |
| Impacts (wounded, shaken, etc.) | `engine/impacts.yaml` (typed `ImpactConfig`); `mechanics/impacts.py` → `apply_impact`, `clear_impact`, `blocks_recovery`, `recalc_max_momentum` |
| Legacy tracks, XP, asset advancement | `engine/legacy.yaml` (typed `LegacyConfig`); `mechanics/legacy.py` → `mark_legacy`, `apply_threat_overcome_bonus`, `advance_asset`; `CampaignState.legacy_quests/bonds/discoveries` |
| NPC name generation | `npc/naming.py` → `roll_oracle_name`; `data/settings/*.yaml` → `oracle_paths.names` |
| Adventure Crafter primitives (themes, plot points, meta dispatch, turning points, supporting tables) | `mechanics/adventure_crafter.py` → `assign_themes`, `lookup_plot_point`, `lookup_meta_plot_point`, `dispatch_meta`, `roll_turning_point`, `lookup_theme_priority`, `lookup_characters_template`, `lookup_plotlines_template`; `engine/adventure_crafter.yaml` (themes, theme_die_table, special_ranges); `data/adventure_crafter.json` (lookup tables, turning_point_rules, plot_point_theme_priority, characters_list_template, plotlines_list_template) |
| AC characters list and plotlines list state | `models_story.py` → `CharacterListEntry` (shared with Mythic random-event-targeting; AC populates `ac_status` and `ac_turning_point_count`), `PlotlineEntry` (AC-only). Lists live on `NarrativeState.characters_list` and `NarrativeState.plotlines_list`. Chapter snapshot/restore through `ChapterSummary.characters_list` and `ChapterSummary.plotlines_list` per the three-place pattern in `game/chapters.py`. |

## AI Model Assignment

The engine assigns models to AI roles via clusters. Each cluster groups roles that share a model and default parameters. `model_for_role(role)` is the single entry point — no module ever hardcodes a model string.

```
Cluster          Roles                                              Needs
─────────────────────────────────────────────────────────────────────────────
narrator         narrator                                           prose generation (creative writing)
creative         architect, director, chapter_summary, recap        open-ended generation needing real reasoning
classification   brain, correction                                  single-shot structured-output decisions
judgment         revelation_check                                   interpretive yes/no with nuance
extraction       narrator_metadata, opening_setup                   pure data extraction, no interpretation
```

Config structure in `config.yaml`:

```yaml
ai:
  clusters:
    narrator:
      model: "zai-glm-4.7"
      temperature: 1.0
      top_p: 0.95
      max_tokens: 8192
      max_retries: 3
      extra_body:
        reasoning_effort: "none"  # GLM 4.7 reasoning disabled for prose
    creative:
      model: "gpt-oss-120b"
      temperature: 0.7
      ...
      extra_body:
        reasoning_effort: "medium"
    # ...classification, judgment, extraction follow the same shape
  # Remap a role to a different cluster:
  role_cluster:
    architect: "creative"
```

Clusters are the single source of truth. `sampling_params(role)` resolves all call parameters from the role's cluster. `model_for_role(role)` resolves the model. No per-role overrides — to change a role's parameters, change the cluster or remap the role via `role_cluster`.

`max_tool_rounds` is an engine mechanical limit, configured in `engine/pacing.yaml` under `max_tool_rounds`.

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
│   ├── engine_config_dataclasses.py  # subsystem dataclasses that bind engine/*.yaml sections
│   ├── format_utils.py      # PartialFormatDict (shared by prompt_loader, strings_loader)
│   ├── mechanics/
│   │   ├── world.py            # Location matching, chaos adjustment, time, pacing, story structure
│   │   ├── resolvers.py        # Position, effect, time progression, move category
│   │   ├── consequences.py     # Dice rolls (action + progress), clocks, momentum burn, consequence sentences
│   │   ├── move_outcome.py     # Top-level move-outcome resolver (resolve_move_outcome) and handler dispatch
│   │   ├── move_effects.py     # Effect parser, 13 effect handlers, dispatch dict (apply_effects)
│   │   ├── move_handlers.py    # Complex move handlers: suffer, threshold, recovery
│   │   ├── stance_gate.py      # NPC stance resolution, information gating
│   │   ├── engine_memories.py  # Memory emotion derivation, engine memories, scene context
│   │   ├── fate.py             # Mythic GME 2e fate chart, fate check, likelihood resolver
│   │   ├── random_events.py    # Event focus, meaning tables, random event pipeline, list maintenance
│   │   ├── scene.py            # Scene structure: keyed/chaos branch, altered/interrupt scenes
│   │   ├── keyed_scenes.py     # Keyed scene evaluator + per-trigger dispatch table
│   │   ├── adventure_crafter.py # AC themes, plot-point lookup, meta-plot-point dispatch, turning-point assembly
│   │   ├── threats.py          # Threat menace advancement, autonomous ticks, Forsake Your Vow
│   │   ├── impacts.py          # Impact apply/clear, max_momentum recalc, recovery blocking
│   │   ├── legacy.py           # Legacy tracks (quests/bonds/discoveries), XP, asset advancement
│   │   └── succession.py       # Inheritance rolls, NPC carryover (per status), legacy seeding
│   ├── parser.py            # Narrator output cleanup (10 regex steps)
│   ├── correction/          # ## correction subpackage
│   │   ├── __init__.py      # Re-exports process_correction, call_correction_brain, _apply_correction_ops
│   │   ├── analysis.py      # Correction brain call (classify misread vs state error)
│   │   ├── ops.py           # Atomic state patches (npc edit/split/merge, location, time, backstory)
│   │   └── orchestrator.py  # Snapshot restore, optional re-roll, re-narrate, post-narration flow
│   ├── director.py          # Story steering, NPC reflections, act transitions
│   ├── persistence.py       # Save/load
│   ├── story_state.py       # Act tracking, revelation timing, story completion check
│   ├── prompt_shared.py     # Shared prompt helpers (scene header, NPC blocks, pacing, director, random events)
│   ├── prompt_action.py     # Action-turn narrator prompt: build_action_prompt, result constraint
│   ├── prompt_dialog.py     # Dialog- and oracle-turn narrator prompt: build_dialog_prompt
│   ├── prompt_boundary.py   # Scene-boundary prompts: build_new_game_prompt, build_epilogue_prompt, build_new_chapter_prompt
│   ├── prompt_blocks.py     # Reusable XML blocks: content boundaries, backstory, status, tone authority, vocabulary, world truths, narrative direction, story arc, recent events, campaign history. All templates yaml-driven via prompts/blocks.yaml.
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
│   │   ├── turn.py          # Main turn pipeline orchestration (process_turn, phase helpers)
│   │   ├── turn_types.py    # Shared turn-pipeline dataclasses (SceneContext, RollOutcome, ActionResolution)
│   │   ├── action_resolution.py  # Action-roll consequence resolution (resolve_action_phase)
│   │   ├── scene_finalization.py # Post-narration finalize_scene + scene-list maintenance
│   │   ├── tracks.py        # Progress track mechanics (find, complete, sync, oracle rolls)
│   │   ├── momentum_burn.py # Momentum burn re-narration pipeline
│   │   ├── game_start.py    # Character creation → opening scene
│   │   ├── chapters.py      # Epilogue, new chapter orchestration
│   │   ├── succession.py    # Continue a Legacy: prepare/start succession, predecessor archive, character replacement
│   │   ├── setup_common.py  # Shared opening setup logic
│   │   ├── finalization.py  # Shared pre- and post-narration: outcome resolution, crisis, memories, metadata
│   │   └── director_runner.py # Deferred Director call
│   ├── datasworn/
│   │   ├── loader.py        # Reads Datasworn JSON (oracles, assets, moves)
│   │   ├── moves.py         # Move dataclass, loader, expansion merge, cached accessor
│   │   └── settings.py      # Setting packages (vocabulary, genre constraints)
│   ├── db/
│   │   ├── schema.sql       # Table definitions (mirrors dataclasses)
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

**Config-driven game logic.** Move outcomes, NPC limits, disposition shifts, damage tables — all in `engine/*.yaml` or Datasworn JSON. Adding a move means adding one YAML entry to `engine/move_outcomes.yaml`. No Python change. Move definitions (stats, roll types, trigger conditions) load directly from Datasworn JSON per setting.

**Modular yaml stores.** Every yaml store in the repo is a directory of files, not a single file: one per subsystem under `engine/`, one per dotted-key prefix under `strings/`, one per cluster under `prompts/`, plus `emotions/`. Each loader globs its directory, merges top-level keys, raises on duplicates. Callsites only talk to `eng()` / `get_prompt()` / `t()` / `importance_map()` — filesystem layout is invisible to the rest of the codebase. `config.yaml` stays single (small, user-edited). `data/settings/*.yaml` was already one file per setting.

**Subpackage public API via `__init__.py`.** Subpackages `mechanics`, `npc`, `game`, `db`, and `tools` each expose their public API by re-exporting from their submodules in `__init__.py`. Callers import `from straightjacket.engine.mechanics import roll_action`, not `from straightjacket.engine.mechanics.consequences import roll_action` — internal module layout stays free to change. The top-level `engine/__init__.py` and the `ai/` package are package markers only, no re-exports. `models.py` is a separate re-export hub for every dataclass across `models_base.py`, `models_npc.py`, and `models_story.py`. The F401 ignore list in `pyproject.toml` covers exactly these intentional public-API hub files.

**Typed dataclasses everywhere.** GameState has sub-objects (Resources, WorldState, NarrativeState, CampaignState). NpcData, MemoryEntry, Move, ProgressTrack, ThreadEntry, ChapterSummary, ClockData, ThreatData and the rest are all typed dataclasses with fixed fields. Move uses typed trigger conditions and roll options. Attribute access, never dict-style. `SerializableMixin` handles serialization; complex classes override `to_dict`/`from_dict` manually.

**Yaml access: dataclass by default, `get_raw` only when keys are domain-data.** Every yaml block is parsed into a typed dataclass at load time; callsites use `eng().subsystem.field` with mypy coverage. The single exception is yaml whose keys are themselves the domain content (move-names, NPC dispositions parallel to an enum) and must extend without Python changes — those are read via `eng().get_raw("section")` with a one-line comment at the callsite. A dataclass with a single `mapping: dict[str, X]` field is no typing win; use `get_raw`. A dataclass with multiple fixed fields is a typing win; use the dataclass.

**Two-call pattern.** Narrator writes pure prose. A second call on the analytical cluster model extracts NPC-related metadata (new NPCs, renames, details, deaths). Same pattern for opening_setup, revelation_check, recap, and chapter_summary. The analytical cluster typically uses a cheaper/faster model for these structured output calls.

**Snapshot/restore.** `GameState.snapshot()` captures all mutable state before a turn. `restore()` reverts everything atomically. Used by correction (##) and momentum burn.

**Chapter transitions are explicit snapshot+restore.** `_close_previous_chapter` builds a `ChapterSummary` containing both AI-written narrative fields and an engine-captured mechanical snapshot (progress_tracks, threats, impacts, assets, narrative.threads). `_reset_chapter_mechanics` zeros every chapter-spanning field, then `_restore_chapter_mechanics` replays the snapshot onto the live game state. Net effect on the running game is unchanged from the previous implicit carry-over, but the chapter-end state is now an auditable record in `campaign_history`, and adding a new chapter-spanning field requires touching three named places (capture, reset, restore) instead of "remember not to add it to the reset list". xp and legacy live on `CampaignState` and carry over campaign-wide; they are not in `ChapterSummary`. NPC list and NPC connection tracks carry via `game.npcs` (not reset by `_reset_chapter_mechanics`) and are handled separately by `_prepare_npcs_for_new_chapter`.

**Character succession.** When the protagonist dies (face_death MISS, or both health and spirit reach zero) or is explicitly retired by the player, the campaign continues with a new protagonist in the same world. Two-step lifecycle gated by `CampaignState.pending_succession`: `prepare_succession` archives the predecessor into `campaign.predecessors` and locks in the inheritance rolls onto that record (so reload can't reroll); `start_succession_with_character` reads the locked-in rolls, closes the predecessor's chapter via the same `_close_previous_chapter` used for chapter transitions, applies NPC carryover (active full / background half / lore half / deceased pruned per `succession.yaml`), wipes PC-specific state via `_reset_for_successor` while keeping world-level threats and unresolved threads (vow-typed and creation-sourced threads drop), seeds the successor's legacy from the rolls, replaces character identity, generates an opening narration, and clears the pending flag. The two-step shape is mandatory for save-resilience: locking the rolls at archive time rather than at character-replacement time is what makes the inheritance deterministic across reload. Unknown roll outcomes and unknown NPC statuses both raise — there is no carryover for state the engine doesn't recognise.

**Provider abstraction.** `AIProvider` protocol with two implementations (Anthropic, OpenAI-compatible). The engine never imports provider SDKs directly. `create_with_retry` handles transient errors with exponential backoff. Multi-model: config.yaml assigns models via five clusters — narrator (GLM 4.7 for prose), creative (GPT-OSS for architect, director, chapter_summary, recap), classification (GPT-OSS for brain, correction), judgment (GPT-OSS for revelation_check), extraction (GPT-OSS for narrator_metadata, opening_setup). Clusters are the single source of truth for all call parameters. `model_for_role(role)` resolves the model; `sampling_params(role)` resolves temperature, top_p, max_tokens, max_retries, and extra_body. The provider stores no model state.

**AI-call exception carve-out.** The strict-rules forbid broad `try/except Exception` suppression. AI call sites are an explicit carve-out — `brain.py`, `narrator.py`, `architect.py`, `director.py`, `correction/analysis.py`, `metadata.py`, `tools/handler.py`. AI calls fail transiently (rate limits, network blips, provider outages, 429/500/502/503/529); the retry wrapper handles retryable status codes with exponential backoff, and what remains after retries is unrecoverable for that call. Strict-raise would crash the player's session on any transient fault. Graceful degradation — Brain falling through to `dialog`, revelation_check defaulting to confirmed, narrator retry returning empty string — hides the fault but preserves the session; every suppression site logs at warning or error level with the exception type so faults stay observable. This carve-out does not extend to config loading, yaml parsing, file persistence, input validation, or domain-rule enforcement: those must raise.

**Minimal UI.** Single HTML page, no build step, no npm. Server sends JSON, client renders. Scene headings for screen reader navigation, aria-live for automatic narration readout. One button (Save/Load), one text input. Status via `/status` and `/score` text commands — engine answers directly, no AI call. Status output is narrative, not mechanical: "seriously wounded" instead of "health 2", "growing trust" instead of "bond 4/10". The player never sees numbers, dice, or system terms.

**Progress tracks as dataclass.** ProgressTrack has rank and ticks; ticks-per-mark by rank lives in `engine/progress.yaml` under `track_types.default.ticks_per_mark` (rank-graduated, fewer ticks for higher ranks), with the `track_types` map extensible for future variants. Status (active/completed/failed) on the track. Background vow becomes a track at creation. Track-creating moves defined in `engine/track_moves.yaml` — engine creates tracks from Brain output. Connection tracks replace NpcData.bond: `get_npc_bond(game, npc_id)` reads connection track filled_boxes.

**Mythic lists seeded at creation.** Threads list starts with the background vow plus any tensions derived from truth selections via `engine/creation.yaml` templates. Characters list starts with the vow subject (if provided) and opening scene NPCs. Both lists are in NarrativeState for snapshot/restore.

**Truths as world context.** Player truth selections stored in GameState.truths and injected into every narrator prompt as a `<world_truths>` block. The narrator treats them as established canon. Truths that match `engine/creation.yaml` patterns automatically seed tension threads.

**AI surface minimization.** Every value derivable from game state is computed by the engine. Director pacing is computed from scene_intensity_history, not requested from the AI. Act transitions fire when scene_count exceeds act range — deterministic, no AI flag. Memory emotional_weight is derived from (move_category, result, disposition) via `engine/memory.yaml` lookup. Opening scene clock and time_of_day are engine-determined before any AI call. The AI receives results, not choices.

**Engine-resolved fiction.** The player types actions, never questions. The engine produces every fact the fiction requires before the narrator writes — NPC names and dispositions from oracle rolls, location structure from generators, plot beats from Adventure Crafter, NPC behavior under uncertainty from fate, encounter contents from weighted tables, scene structure from chaos rolls, content elements from the 45 Mythic element-meaning tables. The narrator receives resolved facts and writes prose around them; it does not invent the deer's locked state or the stranger's name on the fly. Fate and oracles are consulted on many moments across a turn — scene setup, NPC agency, thread phase boundaries, content generation when entities first appear, doublet-triggered random events, MISS-triggered consequences. These are not routed through a central fate-dispatcher but live as concrete callsites in the modules that need them; a shared layer extracts only when callsite count and pattern overlap force it (per the absolute rule "duplication is cheaper than wrong abstraction"). Roadmap steps 9, 10, 11, 13, 25, 26, 27, 31, 32, 33, 34 each add or wire specific consumption sites; the architecture absorbs them as they land. Player-typed fate questions are not part of the model — the player plays the game; the engine asks the questions.

**Data-driven move outcomes.** `resolve_move_outcome` reads structured effect lists from `engine/move_outcomes.yaml` per move per result. Simple moves (momentum, resources, progress, position) are pure data — no Python. Complex moves (suffer, threshold, recovery) use named handlers that share patterns across moves. Engine-specific moves (`dialog`, `ask_the_oracle`, `world_shaping`) live alongside Datasworn moves in `engine/engine_moves.yaml` — single source of truth read by `available_moves`, the brain-output schema, and the narrator. The `available_moves` function filters moves by game state (combat position, active tracks); Brain receives the filtered list in its prompt. Consequence sentences generated from outcome strings via `engine/consequence_templates.yaml`.

**Datasworn mechanic naming.** Datasworn is the spec for mechanical behaviour, not a contract on Python shape. A Datasworn move enters `move_outcomes.yaml` as a formal move when it represents a player choice that Brain can classify and produces a structured outcome (the 56 currently implemented moves all qualify). A Datasworn `no_roll` or `special_track` move that fires automatically when a mechanical condition becomes true (`mark_your_failure` on MISS, `out_of_supply` at supply zero, `face_a_setback` at momentum minimum, `advance_a_threat` on inaction) lives as an engine-trigger with a name that says what the code does — `advance_menace_on_miss` already exemplifies the pattern. Engine-trigger code reaches for the mechanic directly rather than routing through the move-outcome pipeline, because the spec there is "this happens, narrate it" not "the player picked this, resolve it." Both shapes preserve Datasworn coverage; the difference is whether the trigger is choice or consequence.

**Shared outcome resolution.** Three codepaths produce action narration: normal turns, corrections (input_misread), and momentum burns. All three share `resolve_action_consequences` in `game/finalization.py` — move outcome, combat position, MISS clock ticking, crisis check. They also share `apply_progress_and_legacy` — consumes `outcome.progress_marks` on the active track and `outcome.legacy_track` on campaign legacy tracks. Without this shared step, correction and burn would silently drop progress and legacy rewards from the re-resolved outcome after the snapshot restore. Turn.py adds WEAK_HIT clock ticking, track completion on progress rolls, and scene_challenge routing (intentionally turn-only — these are mechanical turn boundaries, not re-narration events). All four narration paths (turn dialog, turn action, correction, burn) share `narrate_scene` — narrator call plus parser — in one call. Post-narration state mutations share `apply_post_narration` from the same module.

**NPC behavioral stance.** Engine computes per-NPC stance from disposition, bond (via connection track), and move category via `engine/stance_matrix.yaml`. The narrator receives `stance="evasive" constraint="One fact, then silence."` instead of raw disposition values. The engine tells the narrator how the NPC behaves, not just how they feel.

**Information gating.** Per-NPC gate level (0–4) controls what enters the narrator prompt. Gate 0 = name + description (stranger). Gate 4 = full secrets. Computed from scenes known, gather_information successes, bond level, and stance cap. The narrator cannot reveal what it doesn't have. Stance caps prevent hostile NPCs from being too transparent regardless of bond.

**Database as read model.** SQLite (in-memory, stdlib) mirrors GameState after every turn, creation, correction, restore, and load. GameState dataclasses remain the write model — all mutations go through Python. The database provides indexed queries for prompt builders, tool handlers, and future NPC trigger evaluation. Ephemeral: rebuilt from GameState on load/restore, no migration burden. JSON save files remain the persistence format.

**Tool calling.** Director uses decorator-based registry (`@register("director")`) producing OpenAI function calling schemas from Python type hints. Iterative handler loop: AI calls tool → engine executes → result appended → AI continues, with configurable round limit. Tools are read-only: they query GameState and database but never mutate. Director uses two-phase: tool loop for context, then json_schema for structured output. Brain does not use tool calling — all game state is injected via prompt (moves, NPCs, tracks). The core principle ("tools determine results, AI narrates") is preserved across both roles: the engine produces all mechanical outcomes. Only the mechanism (prompt injection for Brain vs tool calls for Director) differs — see "Deliberate divergences from the design document" below.

**When tool-call vs when prompt-inject.** The design document treats tool-calling as the central engine-AI communication mechanism; the empirical practice with GLM-4.7 and GPT-OSS is that the right choice depends on the data shape and the AI's role at that callsite. Prompt-injection is the right tool when the data is always or near-always relevant for the call (current location, recent narration, vocabulary substitutions, narrative direction, scene type, activated NPCs in scene, faction context for those NPCs) and the payload is bounded and predictable; adding a tool-roundtrip there spends tokens on overhead that the prompt would carry anyway. Tool-calling is the right tool when (a) the data is selective or conditional and the AI itself is best positioned to choose what is relevant — Director picking which NPC memories matter for a reflection, which threads to weave into a chapter summary, which oracle table to roll on among hundreds — or (b) the payload set is too large to inject by default — the 600-plus Datasworn oracle tables, the 45 Mythic element-meaning tables, full per-NPC memory histories — or (c) the call is conditional on AI judgment that prompt-injection cannot pre-decide. Tool-calling is the wrong tool when the AI must not be allowed to choose: Brain cannot be permitted to pick which moves are available (engine filters that) or which NPCs are present (engine activates those), so Brain stays prompt-injection-only — measured as ~13× cheaper than the tool-calling alternative for that role per CHANGELOG 0.46.50, but the principle is correctness, not cost. The three existing Director tools (`query_npc`, `query_active_threads`, `query_active_clocks`) already follow this principle; future roadmap steps that introduce new AI-consumable data evaluate the same axis per data type.

**Concrete callsite mapping.** Brain, Narrator, Revelation_check, Opening_setup, Narrator_metadata, Recap, Chapter_summary, Correction, and Architect are prompt-only — engine pre-selects all inputs, no AI-side selection of what enters the call. Director is the only mixed site: scene plus story_arc plus reflection-blocks injected (engine pre-selects which NPCs need reflection), and `query_npc`+`query_active_threads`+`query_active_clocks` available as tools for selective deeper inspection. The reflection-block memory window and `query_npc`'s memory limit both read `engine/npc.yaml::npc.reflection_observation_window`, so the same NPC's recent memory looks identical across paths.

**Fate system (Mythic GME 2e).** Probabilistic yes/no questions about the fiction. Two methods: fate chart (9×9 odds/chaos matrix, d100) and fate check (2d10 + modifiers). Both produce four outcomes (yes, no, exceptional yes, exceptional no) and can trigger random events via the doublet rule. Likelihood resolver maps game state (NPC disposition, chaos, resources) to odds level via `engine/fate.yaml` lookup table. Currently engine-consumed only via the random-event pipeline (`mechanics/random_events.py` triggers fate doublets and interrupt scenes). Player-visible fate questions are not part of the model — the player types actions, the engine consults fate under the hood when the fiction requires a fact to exist (see "Engine-resolved fiction" below). Additional fate consumers (NPC behavior, thread discovery, scene-setup feeds) land via roadmap steps that introduce specific callsites; no central fate-router is anticipated. The `ask_the_oracle` move covers Mythic meaning-table rolls (action/subject pairs) — a separate mechanism from the fate chart, with its own `<oracle_answer>` tag.

**Scene structure (Mythic GME 2e).** Every turn starts with a scene test. Priority order: keyed > interrupt > altered > expected. The keyed branch (`mechanics/keyed_scenes.py::evaluate_keyed_scenes`) runs first: if any `KeyedScene` on `narrative.keyed_scenes` has its trigger fire (`clock_fills`, `threat_menace_phase`, `bond_threshold`, `chaos_extreme`, or `scene_count`), the highest-priority match consumes itself from the list and replaces the chaos-driven outcome with `scene_type="keyed"` plus the spawner's `narrative_hint` carried into the narrator prompt as `<keyed_scene>`. Otherwise the d10 vs chaos factor fires: expected (roll > CF), altered (roll ≤ CF, odd), or interrupt (roll ≤ CF, even). Altered scenes roll on the Scene Adjustment Table; interrupt scenes generate a random event via the pipeline. Scene test runs before Brain call. Replaces the old chaos interrupt system.

**Keyed scenes are the engine's pre-scheduled beat channel.** Triggers are registered in `engine/keyed_scenes.yaml`; each registered name maps to an evaluator in `mechanics/keyed_scenes.py::_EVALUATORS`. `KeyedScene.__post_init__` validates `trigger_type` against the registered set so a buggy spawner cannot install a dead scene that fails silently at evaluation. The matched scene is consumed (one-shot) by `check_scene`. Spawning is not yet wired: the Adventure Crafter (planned) will be the spawner, writing keyed scenes onto `narrative.keyed_scenes` when its turning points and plot beats map deterministically onto an engine trigger. Until then `narrative.keyed_scenes` stays empty in normal play and the keyed branch is dormant.

**Adventure Crafter primitives.** AC (Pigeon, Word Mill Games) provides plot-level structure that complements Mythic GME 2e's scene-level chaos. The primitives live in `mechanics/adventure_crafter.py`: theme assignment over five canonical themes (action, tension, mystery, social, personal) via a d10 table, plot-point lookup keyed by `(theme, roll)` because the entries in `data/adventure_crafter.json` carry sparse theme coverage (most entries declare ranges on only a subset of themes), special-range flagging on `Conclusion (1-8)`, `None (9-24)`, and `Meta (96-100)`, and a meta-handler dispatch table covering the seven meta-plot-point types. Engine-level configuration lives in `engine/adventure_crafter.yaml` (themes, theme_slots, theme_die_table, special_ranges); the lookup data lives in `data/adventure_crafter.json`. The yaml `theme_die_table` is cross-validated against the JSON `random_themes` block on first load — mismatches raise at parse time so the engine never silently diverges from the AC data file.

Turning points are the second AC layer: a turning point combines 2-5 plot points into one structured plot beat. `roll_turning_point` picks a plotline (template d100 over `plotlines_list_template`, fallback to `choose_most_logical` when the list is empty), rolls 3d10 per plot point (one d10 for theme priority via `plot_point_theme_priority`, two d10 as d100 for the plot-point lookup), and assembles a `TurningPoint` carrying the plotline reference plus a list of `PlotPointHit` records. The 4th/5th theme priority alternation is held in a per-assembly `ThemeAlternation` dataclass — strictly toggling between 4 and 5 across consecutive 10-rolls within one turning-point — and discarded when assembly ends. A Conclusion (1-8) plot point on any of the assembled hits flips the active plotline from `advancement` to `conclusion`. Two NarrativeState fields hold the lists: `characters_list` is shared with Mythic random-event-targeting and gains AC-only fields `ac_status` and `ac_turning_point_count` (single source of truth for "who exists in the plot layer", reused across both consumers); `plotlines_list` is AC-only with `id`, `name`, `status`, `turning_point_count`. Both round-trip through `ChapterSummary` per the three-place chapter pattern. The seven meta handlers mutate these lists in place: `Character Exits The Adventure` flips an active character's `ac_status` to `exited`; `Character Returns` either revives an exited character or creates a new one; `Steps Up`/`Steps Down` adjust weight; `Downgrade`/`Upgrade` set `ac_status` plus weight; `Plotline Combo` merges two advancing plotlines (excluding the active turning-point's plotline if supplied).

AC's role expands across subsequent steps: AC as the plot-structure source replacing the AI architect blueprint plus keyed-scene spawning (step 7), and thread-phase coupling (step 31).

**Random events.** Four-step pipeline: event focus (d100 over event-focus categories) → target selection from weighted Mythic lists → meaning table roll (actions or descriptions) → structured `RandomEvent` assembly. Events fire on fate doublets and interrupt scenes. `<random_event>` and `<interrupt_scene>` tags injected into narrator prompt. List maintenance: present NPCs/threads get weight bumps, new NPCs added to characters list, automatic consolidation past the configured cap.

**Director reduction.** Director no longer advises on pacing — that is fully engine-computed from scene structure and narrative direction. Director retains NPC reflections (AIMS, arc updates, description updates) and optional chapter summaries. Act transitions are engine-computed from scene count vs act range.

**No save compatibility.** Saves break whenever the code requires it. No migration layer, no default-on-old fields, no ignore-unknown-fields. Every dataclass field is required; adding a field breaks existing saves. Backwards compatibility requires an explicit request per change, otherwise it is not considered. This is by design for an alpha project with no production users.

**AI-surface reduction over post-hoc validation.** Atmospheric and genre drift in narrator output are mitigated by reducing the AI surface (AC-driven blueprint, fiction generators, oracle-driven NPC generation, and engine-computed pacing), not by post-hoc detection or AI-judgment validation. The narration-validator and architect-validator and chapter-validator have all been removed because AI-judgment over writing rules is unreliable; the principle is that the engine narrows what the AI can produce rather than checking what it produced. A diagnostic measurement layer — tag-and-count without retry or prompt injection — remains an open option for after the roadmap is fully implemented and concept-scope is fixed; this is a different design from the deleted retry-validators and is not a closed door.

## Known Limitations

**Single session.** One player at a time. The module-level accumulators (`_pending_events`, `_token_log`) and the in-memory SQLite database assume single-threaded access. Multi-session would require per-session state isolation.

**No faction layer yet.** Within the in-scope scheme-and-individual-relationships boundary defined under Deliberate divergences below: faction-level schemes, faction-player reputation, and faction-NPC loyalty thresholds are not implemented. NPCs act individually via agenda and goal-clocks. The "world moves independently" principle is partially realized through autonomous clock ticks and NPC agency checks, not through the scheme-interaction layer that the scope boundary calls for.

**No fiction generators yet.** NPCs, locations, and encounters are generated by the AI from context, not from structured oracle table rolls. The design document specifies hybrid generators (oracle tables produce structure, AI writes description within that structure). This means the engine currently relies on AI invention where it should rely on oracle-constrained generation.

**No NPC-player emotional dynamics yet.** The engine tracks NPC disposition and bond but not relationship-altering events (broken promises, betrayals, sacrifices), emotional requests, or refusal/concession history. NPCs react to standing relationship state, not to the dynamic history of the relationship. Planned within the in-scope boundary defined under Deliberate divergences — individual scale and player-involving triangles only.

**No asset mechanics.** Assets are stored as ID strings but have no mechanical effect. The modifier pipeline (stat bonuses, rerolls, companion health, vehicle condition) is not implemented.

**Blueprint is AI-generated at game start.** The story architect produces a 3-act or Kishōtenketsu blueprint via a single AI call. Quality varies by model — different models trend toward different default patterns (supernatural horror, romance, action set-pieces) regardless of the setting's genre. The engine compensates with mood sanitization and genre validation, but blueprint quality directly affects Director guidance and narrative direction. Replacing the AI-generated blueprint with a table-driven plot structure (Adventure Crafter) is planned; doing so would be consistent with the design document principle that the engine decides, the AI narrates.

## Deliberate divergences from the design document

Five places where Straightjacket departs from the design document's architectural recommendations. Each was an explicit decision, taken on empirical grounds or as a deliberate scope boundary, not a discard from the document.

**Input parsing as a separate call.** The design document specifies that input parsing is integrated into the single narrator call — the AI classifies the action type and narrates the result in one response. Straightjacket uses a separate Brain call that classifies input before the narrator writes prose. This split was already present in EdgeTales, where the integrated approach did not produce reliable classification. Straightjacket preserved the split on the same empirical grounds. Two independent implementations reaching the same conclusion is stronger evidence than a single project running into the issue.

**Tool calling scoped per data type, not as a universal mechanism.** The design document proposes tool calling as the central engine-AI communication mechanism — the AI requests rolls, queries NPC state, and accesses oracles via callable tools. Straightjacket diverges by treating tool-calling and prompt-injection as complementary rather than substitutable: each callsite picks the gear that matches its data shape and role boundary (see "When tool-call vs when prompt-inject" above). The most visible consequence is that Brain receives all game state via prompt injection rather than tool calls — Brain tool calling was tested and found to cost ~13× the tokens (67K vs 5K over 10 turns) without improving classification quality (CHANGELOG 0.46.50), and the deeper principle is that Brain must not be allowed to pick which moves are available or which NPCs are present (engine decides). Director uses tool-calling for selective queries (memories, threads, clocks) and prompt-injection for scene-fixed context (current location, activated NPCs). Future roadmap steps that introduce new AI-consumable data — generator-framework outputs, faction state, expedition status, site features, the 600-plus Datasworn oracle tables, the 45 Mythic element-meaning tables — evaluate per data type rather than committing to one mechanism. The core principle ("tools determine results, AI narrates") is preserved across all roles.

**Two-call narrator pattern.** The design document treats narration as a single AI call — one prose response per turn within hard constraints. Straightjacket runs a second call on the analytical cluster after the prose is written: the narrator_metadata extractor reads the rendered narration and returns structured NPC-related data (new NPCs, renames, details, deaths) for the engine to apply to game state. Same pattern for opening_setup, revelation_check, recap, and chapter_summary. The split exists because asking the narrator model to also emit structured metadata in the same response degraded prose quality; the analytical cluster is configured for cheaper, faster structured output and does not have to balance two output contracts at once.

**No narration validator.** The design document proposes constraint verification as a second AI call — a cheaper model that checks output against the narrator's constraints, with retry on violation. Straightjacket built that validator (LLM-pass plus regex-pass plus retry-loop) and ran it for many versions, then removed it in 2026.04.27.8. The verdict: verifying writing rules with an AI judge is unreliable on rules that are ambiguous even for humans, and the retry-loop produced predictable prose flattening as the narrator was steered away from anything the validator might flag. The principle now is AI-surface reduction over post-hoc validation: the engine narrows what the AI can produce (engine-dictated consequences, oracle-driven generation, engine-computed pacing, vocabulary control) rather than checking what it produced. A diagnostic measurement layer — tag-and-count without retry or prompt injection — remains an open option after the roadmap is fully implemented and concept-scope is fixed; that is a different design from the deleted retry-validator and not a closed door.

**Faction layer scoped to schemes and individual relationships.** The design document devotes its Relationships and Memory plus Agency and Motivation chapters to factions with goal-clocks ticking independently, faction-level reputation, faction-NPC loyalty thresholds, and inter-faction emotional dynamics. Straightjacket scopes the dynamic relationship layer differently: the individual scale (emotional requests, refusals, concessions, relationship events between NPC and player) and NPC-NPC triangles that involve the player are in scope; the faction scale operates through schemes with independent goal-clocks, faction-player reputation, and scheme-interactions that surface as narrative consequences when the player encounters them; inter-faction emotional dynamics (faction-to-faction emotional requests, refusals, debts as a separate layer) are out of scope. The narrative effect the document calls for — factions acting in the world independent of the player, consequences surfacing on encounter — is achieved through scheme-interaction, not through a simulated faction-emotion network. This is a deliberate scope boundary, not a deferred feature.

## Testing

```bash
python -m pytest tests/                                # unit/integration suite
python tests/elvira/elvira.py --auto --turns 5         # direct engine (needs API key)
python tests/elvira/elvira.py --ws --auto --turns 5    # via WebSocket server
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

Parsed strictly at load. Required top-level keys: `id`, `title`, `datasworn_id`, `description`, `oracle_paths`, `vocabulary`. Optional: `parent`, `creation_flow`. Missing required keys raise `KeyError`.

```yaml
id: your_setting                    # yaml stem
title: "Your Setting Name"
datasworn_id: your_setting          # Datasworn JSON basename
description: "One paragraph."
parent: classic                     # Optional: inherits from this setting

vocabulary:
  substitutions: { spaceship: "starship — worn, patched" }
  sensory_palette: "Metal, recycled air, ozone."

oracle_paths:
  action_theme: ["core/action", "core/theme"]
  descriptor_focus: ["core/descriptor", "core/focus"]
  names: ["characters/name/given", "characters/name/family_name"]
  backstory: "campaign_launch/backstory_prompts"

creation_flow:
  has_truths: true
  has_backstory_oracle: true
  has_name_tables: true
  has_ship_creation: false
  starting_asset_categories: [companion, module]
```

`vocabulary` keeps AI in-setting. `oracle_paths.names` drives engine NPC name rolls. `creation_flow` controls client UI steps.

### Inheritance

With `parent:`, blocks inherit from the parent yaml, resolved at load.

`oracle_paths`, `creation_flow`: per-field. Omitted field → parent's value. Present field (even empty) → explicit override. Root settings must specify every field.

`vocabulary`: section-level. Both sub-fields empty → whole block from parent.

Discovery is yaml-only: `list_packages()` scans `data/settings/*.yaml`, `get_moves()` reads `parent:` from the child yaml. No Python mapping tables.
