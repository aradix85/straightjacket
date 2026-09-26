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
NPC Activation (npc/activation.py) → TF-IDF scores decide which NPCs get full context
  ↓
Roll (mechanics/consequences.py) → d6+stat (max 10) vs 2d10, the Ironsworn action roll, result: STRONG_HIT / WEAK_HIT / MISS
  ↓
Consequences (game/action_resolution.py → resolve_action_phase) → move outcome, combat position, clock ticks, crisis check (shared core: game/finalization.py → resolve_action_consequences)
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
Scene-End Bookkeeping (game/scene_finalization.py → finalize_scene) → autonomous clock/threat ticks, chaos adjustment, list weight updates, consolidation
  ↓
DB Sync (db/sync.py)          → full GameState → SQLite for query access
  ↓
Save (persistence.py)         → JSON to users/{name}/saves/
  ↓
Director (game/director_runner.py → director.py) → deferred after the turn is returned: NPC reflections, AIMS generation; saved again afterwards
```

Dialog turns skip Roll and Consequences. The rest is the same. Act transitions are engine-computed (`director.py` → `_check_engine_act_transition`), not a Director decision.

## Module Ownership

Where to find things. If you want to change X, edit Y.

| I want to change... | Edit this |
|---|---|
| Game rules, damage, NPC limits | `engine/damage.yaml`, `engine/npc.yaml` (no Python) |
| AI prompts (narrator, brain, director) | `prompts/*.yaml` (directory set in `config.yaml` → `ai.prompts_dir`) |
| Emotion scoring, keyword boosts | `emotions/*.yaml` (no Python) |
| UI text | `strings/*.yaml` (no Python) |
| Server port | `config.yaml` (no Python) |
| AI model assignment per role | `config.yaml` → `clusters` (per-cluster model + parameters), `role_cluster` (maps every AI role to its cluster) |
| Provider-specific params per role | `config.yaml` → `extra_body` (per-cluster) |
| Move types or stat assignments | Datasworn JSON (moves loaded automatically per setting) |
| A new setting (genre + constraints) | `data/settings/your_setting.yaml` + Datasworn JSON |
| How dice rolls work | `mechanics/consequences.py` → `roll_action`, `roll_progress` |
| Move outcome effects | `engine/move_outcomes.yaml` (no Python for simple moves) |
| Move outcome handlers (suffer, threshold, recovery) | `mechanics/move_handlers.py` |
| Move outcome resolution + crisis check | `game/finalization.py` → `resolve_action_consequences`, `ActionOutcome` |
| Narrator call + parse + validate | `game/finalization.py` → `narrate_scene` (all four narration paths) |
| AI failure during a turn (pause, restore, tell the player) | `ai/provider_base.py` → `AIUnavailableError`; `web/handlers.py` → `_restore_after_failed_turn`, `_error_text`; `web/server.py` → `_dispatch_one_message` for unexpected handler errors |
| Move data model and loading | `datasworn/moves.py` → `Move`, `get_moves` |
| Combat position (in_control / bad_spot) | `models_base.py` → `WorldState.combat_position`, set by move outcomes |
| How the narrator is prompted | `prompts/*.yaml` → task templates; `prompt_action.py` / `prompt_dialog.py` / `prompt_boundary.py` → XML assembly; `prompt_shared.py` → shared helpers |
| NPC memory / activation logic | `npc/memory.py`, `npc/activation.py` |
| Story structure / act tracking | `story_state.py` → `get_current_act`, `check_story_completion`; `mechanics/adventure_crafter.py` → `assemble_blueprint_seed_from_ac`, `assemble_blueprint_seed_kishotenketsu`, `materialize_blueprint`; `ai/blueprint_voicing.py` → `call_blueprint_voicing` |
| Correction (## undo) flow | `correction/` (package: `analysis.py` brain call, `ops.py` atomic state patches, `orchestrator.py` snapshot restore + re-narrate) |
| Momentum burn re-narration | `game/momentum_burn.py` → `process_momentum_burn` |
| Chapter transition (close, reset, restore) | `game/chapters.py` → `_close_previous_chapter`, `_reset_chapter_mechanics`, `_restore_chapter_mechanics`; narrative summary via `ai/chapter_summary.py` → `call_chapter_summary` |
| Character succession (death/despair/retire → new protagonist) | `game/succession.py` → `prepare_succession`, `start_succession_with_character`, `determine_end_reason`; `mechanics/succession.py` → `build_predecessor_record`, `run_inheritance_rolls`, `seed_successor_legacy`, `apply_npc_carryover`; config in `engine/succession.yaml`; `CampaignState.predecessors`, `pending_succession` |
| Save format | `serialization.py` → `SerializableMixin`, inherited by each dataclass in `models*.py`; loading is strict (an unknown or missing field raises), and `persistence.py` → `load_game` reports such a save as `IncompatibleSaveError` |
| User/save directory management | `user_management.py` → `create_user`, `get_save_dir`, `_safe_name` |
| WebSocket protocol / UI | `web/handlers.py`, `web/static/index.html` |
| Character creation validation | `game/game_start.py` → `validate_stats`, stat arrays in `engine/stats.yaml` |
| Creation data for client | `web/serializers.py` → `build_creation_options` |
| Setting-specific creation flow | `data/settings/*.yaml` → `creation_flow` block |
| Progress track mechanics | `models_base.py` → `ProgressTrack`; valid ranks and ticks per mark in `engine/progress.yaml` (`track_types.default.ticks_per_mark`) |
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
| Track lifecycle (creation, completion) | `mechanics/tracks.py` → `find_progress_track`, `complete_track`, `sync_combat_tracks` |
| Combat track ↔ combat_position sync | `mechanics/tracks.py` → `complete_track` (clears position), `sync_combat_tracks` (orphan cleanup) |
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
| Threat creation (random events, AC plot-points) | `engine/random_events.yaml::threat_creation_mapping` + `engine/adventure_crafter.yaml::threat_creation_mapping`; `mechanics/random_events.py::spawn_threat_from_random_event`; `mechanics/adventure_crafter.py::spawn_threats_for_turning_point`; cascade-naming via `datasworn/cascade.py::roll_oracle_cascade` plus `oracle_paths.threats` per setting |
| Clock creation (random events, AC plot-points) | `engine/random_events.yaml::clock_creation_mapping` + `engine/adventure_crafter.yaml::clock_creation_mapping`; `mechanics/random_events.py::spawn_clock_from_random_event`; `mechanics/adventure_crafter.py::spawn_clocks_for_turning_point`; segments/cap config in `engine/clocks.yaml` |
| Clock fill-consequences (fill handler) | `engine/clocks.yaml::fill_consequences`; `mechanics/clock_consequences.py::resolve_clock_fill`; emits `<clock_filled>` tag via `prompt_shared.py::_clock_filled_block`; suppressed when an attached keyed-scene with source-prefix `clock:` is still pending |
| Spawn-source prefixes (shared constants) | `mechanics/spawn_sources.py` → `RANDOM_EVENT_SOURCE_PREFIX`, `AC_SOURCE_PREFIX`, `CLOCK_KEYED_SOURCE_PREFIX`, `SETUP_SOURCE`, `EMERGENT_SOURCE_PREFIXES` |
| Threat-vow coupling | `models_base.py` → `ThreatData.linked_vow_id`; `mechanics/tracks.py` → `complete_track` resolves linked threat |
| Impacts (wounded, shaken, etc.) | `engine/impacts.yaml` (typed `ImpactConfig`); `mechanics/impacts.py` → `apply_impact`, `clear_impact`, `blocks_recovery`, `recalc_max_momentum` |
| Legacy tracks, XP, asset advancement | `engine/legacy.yaml` (typed `LegacyConfig`); `mechanics/legacy.py` → `mark_legacy`, `apply_threat_overcome_bonus`, `advance_asset`; `CampaignState.legacy_quests/bonds/discoveries` |
| NPC name generation | `npc/naming.py` → `roll_oracle_name`; `data/settings/*.yaml` → `oracle_paths.names` |
| Adventure Crafter primitives (themes, plot points, meta dispatch, turning points, supporting tables, character crafting) | `mechanics/adventure_crafter.py` (theme/plot-point lookups, `roll_turning_point`, `dispatch_meta`, `roll_character_traits`); `engine/adventure_crafter.yaml`; `data/adventure_crafter.json` |
| AC characters list and plotlines list state | `models_story.py` → `CharacterListEntry` (shared with Mythic; AC adds `ac_status`, `ac_turning_point_count`), `PlotlineEntry` (AC-only). Lists on `NarrativeState`; chapter snapshot/restore via three-place pattern in `game/chapters.py`. |

## AI Model Assignment

The engine assigns models to AI roles via clusters. Each cluster names a provider, a model, and the call parameters its roles share, in full, even where clusters repeat each other, so every cluster reads on its own. `model_for_role(role)`, `provider_for_role(role)`, and `sampling_params(role)` are the only way to reach them; no module hardcodes a model string.

```
Cluster          Roles                                       Model, reasoning effort, temperature
────────────────────────────────────────────────────────────────────────────────────────────────────
narrator         narrator                                    GLM 5.3 Flash, low, not sent
creative         blueprint_voicing, chapter_summary, recap   GLM 5.3 Flash, low, not sent
director         director                                    GLM 5.3 Flash, low, not sent
classification   brain, correction                           GLM 5.3 Flash, low, 0.5
judgment         revelation_check                            GLM 5.3 Flash, low, 0.5
extraction       narrator_metadata, opening_setup            GLM 5.3 Flash, low, 0.3
```

GLM 5.3 Flash runs through Together's own API (`zai-org/GLM-5.3-Flash`, $0.15 per million input tokens, $0.03 cached, $0.50 output), chosen by the user in 2026.09.26.5 for its narration over GPT-6 Luna's speed and cost. It always thinks, `low` is its lowest effort, and every cluster runs at it with the temperatures Luna had; at that effort it honours strict JSON schemas and function calling, so the Brain, the extractors, and the Director's tool loop work unchanged. Measured with every role on it (CHANGELOG 2026.09.26.2 to .5): its misses kept to Ironsworn's miss outcomes where DeepSeek V4 Flash turned them into successes, its narration ran about 350 words against Luna's 150, and a twelve-turn session cost about 3 cents against Luna's 1.4. Of the hosts measured, Together direct brought the first sentence soonest, after 2.9 seconds against 3.8 through OpenRouter and about 4.3 on Fireworks, because it also caches short prompts: Fireworks caches only whole blocks of 2048 tokens and Baseten blocks of 1024, so there the Brain, the Director, and the extractors rarely or never hit the cache. GPT-6 Luna stays the measured alternative for speed and cost; moving a cluster back is a change of its `provider`, `model`, and `extra_body`, and Luna needs reasoning effort `none` wherever a cluster sends a temperature or calls tools (CHANGELOG 2026.09.24.42).

Config structure in `config.yaml`:

```yaml
ai:
  providers:
    together:
      type: "openai_compatible"
      api_base: "https://api.together.xyz/v1"
      api_key_env: "TOGETHER_API_KEY"
      timeout_seconds: 120
  clusters:
    narrator:
      provider: together
      model: "zai-org/GLM-5.3-Flash"
      temperature: null
      top_p: null
      max_tokens: 8192
      max_retries: 3
      extra_body:
        reasoning_effort: "low"
        user: "straightjacket"
  role_cluster:
    narrator: narrator
    director: director
```

Every cluster has the same keys; every role maps to exactly one cluster in `role_cluster`. An `api_base` of `""` means the SDK's default endpoint; a `null` temperature or top_p is not sent. The OpenAI, Fireworks, OpenRouter, and Anthropic providers stay configured but unused by the game, so a cluster moves to one of their models by naming the provider and model, and a key is needed only for a provider in use: the game needs `TOGETHER_API_KEY`, and Elvira, who plays and judges on GPT-6 Luna, `OPENAI_API_KEY`. The startup check reads each OpenAI-compatible provider's `/models` with a plain request and accepts both an object with `data` and the bare list Together returns, which the OpenAI SDK's model listing cannot parse (CHANGELOG 2026.09.26.4). Through OpenRouter a cluster's `extra_body` pins one host with `provider: {order: [host], allow_fallbacks: false, require_parameters: true}` and sets thinking with `reasoning: {effort, exclude: true}`; without the pin OpenRouter may route to a host with a temporary discount, a 4-bit quantization, or no structured outputs, which the Brain and the extractors need (CHANGELOG 2026.09.26.2). Together caches the shared start of prompts on its own, short prompts included, and bills cached input at a fifth of fresh input; like the other hosts' caches it matches the longest identical prefix, so the narrator system prompt keeps its fixed rules first, the blocks fixed for a game after them, and the character state, which changes from turn to turn, last. Both adapters report the cached share as `cache_read_tokens`, which the `[TOKENS]` log line shows (for the OpenAI-compatible providers from `prompt_tokens_details.cached_tokens`, checked against Fireworks' `fireworks-cached-prompt-tokens` header in 2026.09.25.4). Every cluster sends the same `user` value as a session-affinity key: identical GLM 5.3 prompts hit Fireworks' cache without one in 2026.09.25.4, but for GLM 5.3 Flash on Fireworks it raised the narrator's cached share from 7 to 14 percent to 39 (CHANGELOG 2026.09.26.5), and Together accepts it. Baseten takes the key only as an `x-session-affinity` header, which the adapter does not send. Anthropic prompt caching needs `cache_control` in the extra body, while OpenAI, Fireworks, and Together cache automatically.

Routing: `ai/api_client.py` → `get_provider` returns a routing provider that sends each call to the provider of its role's cluster, keyed on `AICallSpec.log_role`, which every AI call sets to its own role name; the project-rule scan `_check_ai_calls_route_by_their_role` enforces this. `python run.py` and Elvira call `check_configured_models` first: every cluster's model must appear in its provider's model list, or startup stops naming the missing model. `max_tool_rounds` is an engine limit in `engine/pacing.yaml`.

## File Map

```
src/straightjacket/
├── engine/
│   ├── models.py            # Re-export hub for all dataclasses
│   ├── models_base.py       # EngineConfig, Resources, ProgressTrack, WorldState, ClockData/Event/FillResult, RandomEvent, FateResult
│   ├── models_npc.py        # NpcData, MemoryEntry
│   ├── models_story.py      # ThreadEntry, CharacterListEntry, NarrativeState, StoryBlueprint, etc.
│   ├── engine_config.py     # EngineSettings composition + _build_strict / load_strict yaml parse; re-exports dataclasses
│   ├── engine_config_dataclasses.py  # subsystem dataclasses that bind engine/*.yaml sections
│   ├── format_utils.py      # PartialFormatDict (shared by prompt_loader, strings_loader)
│   ├── serialization.py     # SerializableMixin, serialize/deserialize for all save-format dataclasses
│   ├── yaml_merge.py        # load_yaml_dir: shared "merge every *.yaml in a directory, raise on duplicate keys"
│   ├── xml_utils.py         # xe() / xa(): XML escaping for prompt content and attributes (see SECURITY.md)
│   ├── bootstrap_log.py     # bootstrap_log(): logging for modules that load before file logging is set up
│   ├── mechanics/
│   │   ├── world.py            # Location matching, chaos adjustment, time, pacing, story structure
│   │   ├── resolvers.py        # Position, effect, time progression, move category
│   │   ├── consequences.py     # Dice rolls (action + progress), clocks, momentum burn, consequence sentences
│   │   ├── clock_consequences.py  # Clock fill handler (resolve_clock_fill) → `<clock_filled>` tag, progress-track completion
│   │   ├── spawn_sources.py    # Shared spawn-source prefixes (random_event:, ac:, clock:, setup)
│   │   ├── move_outcome.py     # Top-level move-outcome resolver (resolve_move_outcome) and handler dispatch
│   │   ├── move_effects.py     # Effect parser, effect handlers, dispatch dict (apply_effects), Pay the Price
│   │   ├── move_handlers.py    # Complex move handlers: suffer, threshold, recovery
│   │   ├── assets.py           # Asset data lookup, enabled abilities per asset, enabling the next ability
│   │   ├── bonuses.py          # Roll bonuses from enabled asset abilities and connections, the Brain's choice, momentum on a hit
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
│   │   ├── tracks.py           # Progress track lifecycle: find, complete (clears combat position, resolves linked threat), sync, oracle answer
│   │   └── succession.py       # Inheritance rolls, NPC carryover (per status), legacy seeding
│   ├── parser.py            # Narrator output cleanup (10 regex steps)
│   ├── correction/          # ## correction subpackage
│   │   ├── __init__.py      # Re-exports process_correction, call_correction_brain, _apply_correction_ops
│   │   ├── analysis.py      # Correction brain call (classify misread vs state error)
│   │   ├── ops.py           # Atomic state patches (npc edit/split/merge, location, time, backstory)
│   │   └── orchestrator.py  # Snapshot restore, optional re-roll, re-narrate, post-narration flow
│   ├── director.py          # Story steering, NPC reflections, act transitions
│   ├── persistence.py       # Save/load
│   ├── ids.py              # unique_id: a free id from a base and the ids already taken
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
│   ├── logging_util.py      # log(), setup_file_logging()
│   ├── user_management.py   # User CRUD, save directories, _safe_name, config load/save
│   ├── ai/
│   │   ├── api_client.py    # get_provider(): routes each call to its role's provider; check_configured_models(): startup check; provider_named(): one configured provider's adapter; lazy SDK import
│   │   ├── sentence_stream.py # SentenceStream: cuts streamed narrator text into whole, cleaned sentences for the client
│   │   ├── provider_base.py # AIProvider protocol + retry wrapper
│   │   ├── provider_anthropic.py
│   │   ├── provider_openai.py  # Any OpenAI-compatible API
│   │   ├── brain.py         # Single-call move classification (prompt injection, no tools)
│   │   ├── narrator.py      # Prose generation + metadata extraction calls
│   │   ├── metadata.py      # Apply extracted metadata to game state
│   │   ├── recap.py         # Player-facing recap (call_recap)
│   │   ├── chapter_summary.py  # Chapter summary for campaign history (call_chapter_summary)
│   │   ├── blueprint_voicing.py  # Voices an AC blueprint seed in the active setting → StoryBlueprint (call_blueprint_voicing)
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
│   │   ├── cascade.py       # roll_oracle_cascade: follows markdown-link IDs across oracle tables (depth-limited)
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

**Import layers.** Dependencies point downward. `datasworn/` and `db/` import only the engine core (models, config, loaders). `npc/` and `mechanics/` may use those and each other, but never `ai/`, `tools/`, `game/`, `correction/`, or `web/`. `ai/`, `tools/`, and the engine core's top-level files never import `game/`, `correction/`, or `web/`; `game/` orchestrates everything below it; `correction/` builds on `game/`; nothing in the engine imports `web/`. `_check_import_layers` in `tests/test_project_rules.py` enforces this, inline imports included: a circular-break import does not excuse a dependency in the wrong direction.

**Typed dataclasses everywhere.** GameState has sub-objects (Resources, WorldState, NarrativeState, CampaignState). NpcData, MemoryEntry, Move, ProgressTrack, ThreadEntry, ChapterSummary, ClockData, ThreatData and the rest are all typed dataclasses with fixed fields. Move uses typed trigger conditions and roll options. Attribute access, never dict-style. `SerializableMixin` (in `serialization.py`) handles serialization for every class, with no manual overrides, and loads strictly: a field the class does not know, or a field the data lacks, raises instead of being skipped or defaulted.

**Yaml access: dataclass by default, `get_raw` only when keys are domain-data.** Every yaml block is parsed into a typed dataclass at load time; callsites use `eng().subsystem.field` with mypy coverage. The single exception is yaml whose keys are themselves the domain content (move-names, NPC dispositions parallel to an enum) and must extend without Python changes — those are read via `eng().get_raw("section")`. A dataclass with a single `mapping: dict[str, X]` field is no typing win; use `get_raw`. A dataclass with multiple fixed fields is a typing win; use the dataclass.

**Two-call pattern.** Narrator writes pure prose. A second call, `narrator_metadata` on the extraction cluster, extracts NPC-related metadata (new NPCs, renames, details, deaths). Opening_setup, revelation_check, recap, and chapter_summary are likewise separate calls rather than extra duties for the narrator, each on the cluster that fits its task (see AI Model Assignment). The extraction cluster is the natural place for a cheaper/faster model: pure data extraction, no interpretation.

**Snapshot/restore.** `GameState.snapshot()` captures all mutable state before a turn. `restore()` reverts everything atomically. Used by correction (##) and momentum burn.

**Chapter transitions are explicit snapshot+restore.** Three-place pattern: `_close_previous_chapter` builds a `ChapterSummary` with narrative fields plus a mechanical snapshot, `_reset_chapter_mechanics` zeros every chapter-spanning field, `_restore_chapter_mechanics` replays the snapshot. Adding a new chapter-spanning field requires touching all three. `CampaignState.xp` and legacy tracks carry campaign-wide and are not in `ChapterSummary`. NPC list and connection tracks carry via `game.npcs` (not reset) and are handled by `_prepare_npcs_for_new_chapter`.

**Character succession.** When the protagonist dies (face_death MISS, or both health and spirit reach zero) or is explicitly retired, the campaign continues with a new protagonist in the same world. Two-step lifecycle gated by `CampaignState.pending_succession`: `prepare_succession` archives the predecessor into `campaign.predecessors` and locks in the inheritance rolls onto that record; `start_succession_with_character` reads the locked-in rolls, closes the predecessor's chapter via `_close_previous_chapter`, applies NPC carryover per `succession.yaml`, wipes PC-specific state while keeping world-level threats and unresolved non-vow non-creation-sourced threads, seeds the successor's legacy, replaces character identity, generates opening narration, clears the flag. Locking rolls at archive time rather than at replacement time is what makes inheritance deterministic across reload. Unknown roll outcomes and unknown NPC statuses raise.

**Provider abstraction.** `AIProvider` protocol with two implementations, `ai/provider_anthropic.py` and `ai/provider_openai.py` (any OpenAI-compatible endpoint); nothing else imports a provider SDK. Model assignment is described under AI Model Assignment. Both adapters create their SDK client with `max_retries=0` and the provider's `timeout_seconds`, so `create_with_retry` is the only retry layer: it honours a `Retry-After` header, capped by `retry.max_retry_after_seconds` in `engine/retry.yaml`, and otherwise backs off exponentially. A refusal (Anthropic `refusal`, OpenAI `content_filter`) normalizes to the stop reason `refusal`, which is retried like a transient error and raises `AIUnavailableError` when it persists. Only text reaches `AIResponse.content`; reasoning never does. The OpenAI-compatible adapter sends `max_completion_tokens`, which OpenAI's own models require. The Anthropic adapter sends `temperature`, `top_p`, and `top_k` through `extra_body` and only when set, routes `cache_control`, `thinking`, and `output_config` from the cluster's `extra_body` to their typed parameters, and converts the tool loop's OpenAI-style messages into `tool_use` and `tool_result` blocks.

**Sentence-level narration streaming.** With `server.stream_narration: true` in `config.yaml`, a player turn streams the narrator's output. `web/handlers.py` hands `process_turn` a `SentenceStream`, which travels through `SceneContext` and `narrate_scene` into `call_narrator`; `ai/provider_base.py` → `stream_with_retry` calls the provider's `stream_message` (both adapters implement it, and only text deltas ever reach the stream, never reasoning). The stream buffers text until a sentence is complete (abbreviations and hold markers live in `engine/parser.yaml`), cleans it with `parser.py` → `clean_sentence`, and the handler sends it as a `narration_sentence` WebSocket message that the client appends to the log region, so the screen reader starts reading after the first sentence. The existing `narration` message still carries the authoritative, fully parsed text and a `stream_complete` flag: when the streamed text matches, the client leaves it as it is; otherwise it replaces it and announces only the part the player has not heard. A hold marker (tag, code fence, JSON) stops the stream and leaves the rest to the final message; a failed stream falls back to a normal call. Openings, corrections, and momentum burns do not stream.

**AI-call exception carve-out.** The strict-rules forbid broad `try/except Exception` suppression. AI call sites are an explicit carve-out: AI calls fail transiently (rate limits, network blips, provider outages, 429/500/502/503/529); the retry wrapper handles retryable status codes with exponential backoff, and what remains after retries is unrecoverable. The two calls a turn cannot do without, the Brain and the narrator, do not degrade: after the retries they raise `AIUnavailableError` (`ai/provider_base.py`), as do a persistent refusal and an empty narration, and the web handler for a turn, a correction, or a momentum burn restores the snapshot it took before the call and tells the player that nothing in the story changed, as the design document asks. The other calls degrade without a wrong state change: a failed revelation check counts as not yet confirmed, metadata extraction and the Director are skipped, blueprint_voicing returns None, and a recap or chapter summary uses its fallback. Every such site logs at warning or error level, which Elvira reports. This carve-out does not extend to config loading, yaml parsing, file persistence, input validation, or domain-rule enforcement: those must raise. The files covered by the carve-out are listed in `_AI_CALL_CARVE_OUT_FILES` in `tests/test_project_rules.py`; that set is the authoritative carve-out file list, including for audits.

**Minimal UI.** Single HTML page, no build step, no npm. Server sends JSON, client renders. Scene headings for screen reader navigation, aria-live for automatic narration readout. During play: one text input plus the Save/Load and Retire buttons. Everything else appears only when needed, as overlays and forms with native controls: character creation, the momentum-burn offer, story completion, succession, and the retire confirmation. Status via `/status`, `/score`, `/tracks`, and `/threats` text commands — engine answers directly, no AI call. Status output is narrative, not mechanical: "seriously wounded" instead of "health 2", "growing trust" instead of "bond 4/10". The player never sees numbers, dice, or system terms.

**Progress tracks as dataclass.** ProgressTrack has rank and ticks; ticks-per-mark by rank lives in `engine/progress.yaml` under `track_types.default.ticks_per_mark` (rank-graduated, fewer ticks for higher ranks), with the `track_types` map extensible for future variants. Status (active/completed/failed) on the track. Background vow becomes a track at creation. Track-creating moves defined in `engine/track_moves.yaml` — engine creates tracks from Brain output. Connection tracks replace NpcData.bond: `get_npc_bond(game, npc_id)` reads connection track filled_boxes.

**Mythic lists seeded at creation.** Threads list starts with the background vow plus any tensions derived from truth selections via `engine/creation.yaml` templates. Characters list starts with the vow subject (if provided) and opening scene NPCs. Both lists are in NarrativeState for snapshot/restore.

**Truths as world context.** Player truth selections stored in GameState.truths and injected into every narrator prompt as a `<world_truths>` block. The narrator treats them as established canon. Truths that match `engine/creation.yaml` patterns automatically seed tension threads.

**AI surface minimization.** Every value derivable from game state is computed by the engine. Director pacing is computed from scene_intensity_history, not requested from the AI. Act transitions fire when scene_count exceeds act range — deterministic, no AI flag. Memory emotional_weight is derived from (move_category, result, disposition) via `engine/memory.yaml` lookup. Opening scene clock and time_of_day are engine-determined before any AI call. The AI receives results, not choices.

**What the AI still decides.** Four AI decisions remain, each bounded by the engine, and they are deliberate rather than gaps in the rule above. The Brain turns free player text into a move, a stat, a roll bonus, a target NPC, and a new track's name and rank; free text needs interpretation, so this stays an AI call, but each choice is limited to what the engine offers in that situation (the output schema carries only the available moves, offered bonuses, listed NPCs, and active tracks, and `call_brain` refuses anything else), and the dice and the engine decide the outcome. The narrator supplies every fact the engine has not settled, such as whether a door is locked or who else is present, until step 9 resolves such facts through fate. The `narrator_metadata` extraction registers the NPCs, renames, and deaths the narration introduces, so narrated facts can become state (see Known Limitations). The Director writes NPC agendas, instincts, and arcs, for the NPCs the engine selects. Step 9 shrinks the second and third; the first and fourth are part of the design.

**Engine-resolved fiction.** The player types actions, never questions. The target model: the engine produces every fact the fiction requires before the narrator writes — NPC names and dispositions from oracle rolls, location structure from generators, plot beats from Adventure Crafter, NPC behavior under uncertainty from fate, encounter contents from weighted tables, scene structure from chaos rolls, content elements from the 45 Mythic element-meaning tables. The narrator receives resolved facts and writes prose around them. Implemented today: NPC names from oracle rolls, plot beats from Adventure Crafter, scene structure from chaos rolls, meaning-table rolls (actions and descriptions only) inside the random-event pipeline, and threat and clock naming from Mythic pairs and Datasworn cascades. The fate system itself (`mechanics/fate.py` → `resolve_fate`) is implemented and tested but has no caller in play: its only route in, a Brain tool, went away when the Brain moved to prompt injection in 0.46.50, and step 9 reconnects it through fact resolution. Location and encounter generators, fact resolution, oracle-rolled NPC dispositions, fate-driven NPC behavior, and the themed element tables are roadmap steps 9–13 and 33–34 (see Known Limitations). For fact resolution the trigger is decided: the Brain flags which undetermined fact an action depends on, chosen from a fixed list of fact types, and the engine rolls the answer and remembers it. Fate and oracles are consulted on many moments across a turn (scene setup, NPC agency, thread phase boundaries, content generation when entities first appear, doublet-triggered random events, MISS-triggered consequences) as concrete callsites in the modules that need them; a shared layer extracts only when callsite count and pattern overlap force it (per "duplication is cheaper than wrong abstraction"). Player-typed fate questions are not part of the model.

**Threat creation from random events and AC plot-points.** Threats spawn mid-game from two sources, each with its own naming source: random events whose `focus` is in `random_events.yaml::threat_creation_mapping` (currently `pc_negative` plus `npc_negative`) use the event's Mythic action+subject pair as the threat name, since the random-event mechanism already produced that pair; AC plot-points whose name is in `adventure_crafter.yaml::threat_creation_mapping` (`A New Enemy`, `Hidden Threat`, `Enemies`, `Hunted`, `A Problem Returns`) use a Datasworn cascade-roll on `oracle_paths.threats` per setting via `datasworn/cascade.py::roll_oracle_cascade`. The cascade follows markdown-link IDs in oracle-row text — Delve's `threat/category` cascades into nine sub-tables; Starforged's `campaign_launch/sector_trouble`, Classic's `settlement/trouble`, and Sundered Isles's `seafaring/peril` are single-table rolls. Each spawner dedups via `ThreatData.creation_source` (prefix `random_event:` or `ac:`); the shared per-chapter cap `max_threats_per_chapter` covers both spawners. `linked_vow_id` is `None` for mid-game threats; setup-vow-linked threats keep their string ID. Threats without a linked vow do not advance via `advance_menace_on_miss` (which is vow-driven) but do tick via `tick_autonomous_threats` and can fire `threat_menace_phase` keyed-scenes once their menace reaches the configured phase threshold.

**Clock creation from random events and AC plot-points.** Same source-vs-naming pattern as threat creation. Random events with `focus` in `random_events.yaml::clock_creation_mapping` (currently `pc_negative` → threat-clock, `move_toward_thread` → progress-clock, `move_away_from_thread` → threat-clock) use the event's Mythic action+subject pair as the clock name. AC plot-points in `adventure_crafter.yaml::clock_creation_mapping` (`Time Limit`, `A Crucial Life Support System Begins To Fail`, `A Needed Resource Runs Out`, `Impending Doom`) use the plot-point name itself as the clock name — deadlines have their own already-named character, no cascade needed. Both spawners read `engine/clocks.yaml::default_segments` for size and `default_owner_kind` for owner-kind (currently `world`). Shared per-chapter cap `max_clocks_per_chapter` covers both sources. Dedup via `ClockData.creation_source` (prefix `random_event:` or `ac:`). Each spawned clock immediately gets per-fraction keyed-scenes attached via `spawn_keyed_scenes_for_clock`. The shared spawn-source prefixes live as constants in `mechanics/spawn_sources.py` so no module repeats the literals.

**Clock fill-consequences.** When a clock fills, the engine emits a `<clock_filled>` tag to the narrator prompt — unless a keyed-scene with source-prefix `clock:<clock_name>:` is still pending on `narrative.keyed_scenes`, in which case the keyed-scene wins and the default tag is suppressed. Per-type tag templates live in `engine/clocks.yaml::fill_consequences` (one entry per clock_type: `threat`, `scheme`, `progress`). The fill-handler is `mechanics/clock_consequences.py::resolve_clock_fill`. A filled progress clock additionally completes the linked `ProgressTrack` (matched by name == clock-name) via `complete_track` with outcome `completed`. Filled scheme and threat clocks do not advance menace tracks — those mechanics stay on their own paths (`advance_menace_on_miss`, `tick_autonomous_threats`). Fill-events from MISS-driven and NPC-agency-driven ticks flow through `ActionResolution.clock_fill_results` into the same-turn narrator prompt. Fill-events from `tick_autonomous_clocks` (which fires after narration in `scene_finalization`) cannot land in their own turn's prompt, so they queue on `WorldState.pending_clock_fills` and are drained-and-prepended at the start of the next turn's action or dialog prompt assembly.

**Data-driven move outcomes.** `resolve_move_outcome` reads structured effect lists from `engine/move_outcomes.yaml` per move per result. Simple moves (momentum, resources, progress, position) are pure data — no Python. Complex moves (suffer, threshold, recovery) use named handlers that share patterns across moves. Engine-specific moves (`dialog`, `ask_the_oracle`, `world_shaping`) live alongside Datasworn moves in `engine/engine_moves.yaml` — single source of truth read by `available_moves`, the brain-output schema, and the narrator. The `available_moves` function filters moves by game state (combat position, active tracks); Brain receives the filtered list in its prompt. Consequence sentences generated from outcome strings via `engine/consequence_templates.yaml`.

**Datasworn mechanic naming.** Datasworn is the spec for mechanical behaviour, not a contract on Python shape. A Datasworn move enters `move_outcomes.yaml` as a formal move when it represents a player choice that Brain can classify and produces a structured outcome. A Datasworn `no_roll` or `special_track` move that fires automatically when a mechanical condition becomes true lives as an engine-trigger with a name that says what the code does (`advance_menace_on_miss` exemplifies the pattern). Engine-trigger code reaches for the mechanic directly rather than routing through the move-outcome pipeline. Both shapes preserve Datasworn coverage; the difference is whether the trigger is choice or consequence.

**Shared outcome resolution.** Three codepaths produce action narration: normal turns, corrections (input_misread), and momentum burns. All three share `resolve_action_consequences` in `game/finalization.py` (move outcome, combat position, MISS clock ticking, crisis check) plus `apply_progress_and_legacy` (consumes `outcome.progress_marks` and `outcome.legacy_track`). Without the shared progress step, correction and burn would silently drop progress and legacy rewards after the snapshot restore. Turn.py adds WEAK_HIT clock ticking, track completion on progress rolls, and scene_challenge routing (turn-only — mechanical turn boundaries, not re-narration events). All four narration paths share `narrate_scene` and `apply_post_narration`.

**NPC behavioral stance.** Engine computes per-NPC stance from disposition, bond (via connection track), and move category via `engine/stance_matrix.yaml`. The narrator receives `stance="evasive" constraint="One fact, then silence."` instead of raw disposition values. The engine tells the narrator how the NPC behaves, not just how they feel.

**Information gating.** Per-NPC gate level (0–4) controls what enters the narrator prompt. Gate 0 = name + description (stranger). Gate 4 = full secrets. Computed from scenes known, gather_information successes, bond level, and stance cap. The narrator cannot reveal what it doesn't have. Stance caps prevent hostile NPCs from being too transparent regardless of bond.

**Database as read model.** SQLite (in-memory, stdlib) mirrors GameState after every turn, creation, correction, restore, and load. GameState dataclasses remain the write model — all mutations go through Python. The database provides indexed queries for prompt builders, tool handlers, and future NPC trigger evaluation. Ephemeral: rebuilt from GameState on load/restore, no migration burden. JSON save files remain the persistence format.

**Tool calling.** Director uses decorator-based registry (`@register("director")`) producing OpenAI function calling schemas from Python type hints. Iterative handler loop: AI calls tool → engine executes → result appended → AI continues, with configurable round limit. Tools are read-only: they query GameState and database but never mutate. Director uses two-phase: tool loop for context, then json_schema for structured output. Brain does not use tool calling — all game state is injected via prompt (moves, NPCs, tracks).

**When tool-call vs when prompt-inject.** Prompt-injection fits when the data is always or near-always relevant for the call and the payload is bounded — adding a tool-roundtrip there spends tokens on overhead the prompt would carry anyway. Tool-calling fits when the data is selective and the AI is best-positioned to choose what is relevant (Director picking which NPC memories matter, which threads to weave into a chapter summary), when the payload set is too large to inject by default (the 600-plus Datasworn oracle tables, full per-NPC memory histories), or when the call is conditional on AI judgment that prompt-injection cannot pre-decide. Tool-calling is wrong when the AI must not be allowed to choose: Brain cannot pick which moves are available (engine filters) or which NPCs are present (engine activates), so Brain stays prompt-injection-only. New AI-consumable data evaluates on the same axis per data type.

**Concrete callsite mapping.** Brain, Narrator, Revelation_check, Opening_setup, Narrator_metadata, Recap, Chapter_summary, Correction, and Blueprint_voicing are prompt-only — engine pre-selects all inputs, no AI-side selection of what enters the call. Director is the only mixed site: scene plus story_arc plus reflection-blocks injected (engine pre-selects which NPCs need reflection, and reflections for NPCs outside that selection, as well as duplicates, are rejected when the answer is applied), and `query_npc`+`query_active_threads`+`query_active_clocks` available as tools for selective deeper inspection. The reflection-block memory window and `query_npc`'s memory limit both read `engine/npc.yaml::npc.reflection_observation_window`, so the same NPC's recent memory looks identical across paths.

**Fate system (Mythic GME 2e).** Probabilistic yes/no questions about the fiction. Two methods: fate chart (9×9 odds/chaos matrix, d100) and fate check (2d10 + modifiers). Both produce four outcomes (yes, no, exceptional yes, exceptional no) and can trigger random events via the doublet rule. Likelihood resolver maps game state (NPC disposition, chaos, resources) to odds level via `engine/fate.yaml` lookup. Not consulted in play today (see "Engine-resolved fiction" above); when fate is consulted, a doublet generates a random event through `mechanics/random_events.py`. Step 9 (fact resolution) is the first planned caller. Player-visible fate questions are not part of the model — the engine consults fate under the hood when the fiction requires a fact (see "Engine-resolved fiction" above). The `ask_the_oracle` move covers Mythic meaning-table rolls (action/subject pairs) — a separate mechanism with its own `<oracle_answer>` tag.

**Scene structure (Mythic GME 2e).** Every turn starts with a scene test. Priority order: keyed > interrupt > altered > expected. The keyed branch (`mechanics/keyed_scenes.py::evaluate_keyed_scenes`) runs first: if any `KeyedScene` on `narrative.keyed_scenes` has its trigger fire (`clock_fills`, `threat_menace_phase`, `bond_threshold`, `chaos_extreme`, or `scene_count`), the highest-priority match consumes itself from the list and replaces the chaos-driven outcome with `scene_type="keyed"` plus the spawner's `narrative_hint` carried into the narrator prompt as `<keyed_scene>`. Otherwise the d10 vs chaos factor fires: expected (roll > CF), altered (roll ≤ CF, odd), or interrupt (roll ≤ CF, even). Altered scenes roll on the Scene Adjustment Table; interrupt scenes generate a random event via the pipeline. Scene test runs before Brain call. Replaces the old chaos interrupt system.

**Keyed scenes are the engine's pre-scheduled beat channel.** Triggers in `engine/keyed_scenes.yaml`, evaluators in `mechanics/keyed_scenes.py::_EVALUATORS`. `KeyedScene.__post_init__` validates `trigger_type` against the registered set and pattern-supporting triggers also validate `trigger_value` against the per-trigger grammar. The matched scene is consumed one-shot by `check_scene`. Three spawn-sources: AC at chapter-start (campaign-skeleton beats from turning-point plot-points), random events at fire-time, and clock creation at game-start plus chapter-start (per clock-type fractions via `apply_world_setup`).

Three trigger-types accept patterns — `bond_threshold`, `threat_menace_phase`, `clock_fills` — each with valid prefixes (`<entity_id>:N`, `any:N`, plus `disposition_<value>:N` for bond) plus a matcher_strategy (`highest_bond`, `highest_menace`, `highest_filled`) in `pattern_grammars`. On fire-moment `evaluate_keyed_scenes` resolves to a concrete entity, sets `KeyedScene.bound_entity_id`, and excludes already-bound entities from siblings' resolution. `chaos_extreme` and `scene_count` are entity-less. AC's `keyed_scene_mapping` carries 33 plot-point-to-trigger mappings across all five trigger-types; dedup-A skips the same plot-point twice within a chapter, dedup-B caps via `max_keyed_scenes_per_chapter`. Random-event-spawner builds concrete triggers from `event.target_id` or `event.target`; clock-spawner reads per-clock-type fractions from `engine/clock_keyed_scenes.yaml`.

**Adventure Crafter primitives.** AC (Pigeon, Word Mill Games) provides plot-level structure complementing Mythic's scene-level chaos. Primitives in `mechanics/adventure_crafter.py`: five canonical themes via d10 table, plot-point lookup keyed by `(theme, roll)` because `data/adventure_crafter.json` carries sparse theme coverage, special-range flagging on `Conclusion (1-8)`, `None (9-24)`, and `Meta (96-100)`, plus a meta-handler dispatch table for the seven meta-plot-point types. Engine config in `engine/adventure_crafter.yaml`; lookup data in `data/adventure_crafter.json`. The yaml `theme_die_table` is cross-validated against the JSON `random_themes` block on first load. Character-crafting tables ship as pure helpers (`roll_character_traits` plus three lookups); `CharacterTraits` carries 1-or-2 identities and 1-or-2 descriptors with list-length as discriminator, currently under an orphan-symbol carve-out until step 11 (NPC tiers) consumes it.

Turning points are the second AC layer. `roll_turning_point` combines 2-5 plot points: plotline pick from `plotlines_list_template` (fallback `choose_most_logical`), 3d10 per plot point (theme priority via `plot_point_theme_priority` with 4th/5th alternation, plus 2d10 for the lookup). Conclusion (1-8) on any hit flips the active plotline from `advancement` to `conclusion`. Two NarrativeState fields hold the lists: `characters_list` shared with Mythic random-event-targeting (gains `ac_status` plus `ac_turning_point_count`); `plotlines_list` AC-only. Both round-trip through `ChapterSummary` per the three-place chapter pattern. Seven meta handlers mutate these lists in place.

AC's role is bounded to plot-skeleton at chapter boundaries plus keyed-scene-spawning. `assemble_blueprint_seed_from_ac` rolls turning-points, produces a `BlueprintSeed` (frozen), and `call_blueprint_voicing` converts it to a setting-specific `StoryBlueprint` via one structured AI call. Kishōtenketsu blueprints skip turning-point rolling — four phase-acts from yaml, voicing call fills setting fields. After each turning-point, `spawn_keyed_scenes_for_turning_point` constructs `KeyedScene` instances on `narrative.keyed_scenes`. Mid-chapter AC-scheduling is deliberately not done — pacing within a chapter runs on the six existing systems (Mythic random events, pacing-hint, clocks, threats, scene-structure, Director NPC-reflections).

**Random events.** Four-step pipeline: event focus (d100 over event-focus categories) → target selection from weighted Mythic lists → meaning table roll (actions or descriptions) → structured `RandomEvent` assembly. Events fire on interrupt scenes, and on fate doublets once fate has a caller again (step 9). `<random_event>` and `<interrupt_scene>` tags injected into narrator prompt. List maintenance: present NPCs/threads get weight bumps, new NPCs added to characters list, automatic consolidation past the configured cap.

**Director reduction.** Director no longer advises on pacing — that is fully engine-computed from scene structure and narrative direction. Director retains NPC reflections (AIMS, arc updates, description updates). Chapter summaries are a separate AI role (`ai/chapter_summary.py`). Act transitions are engine-computed from scene count vs act range.

**No save compatibility.** Saves break whenever the code requires it. No migration layer, no default-on-old fields, no ignore-unknown-fields. By design for an alpha project. See "No backwards compatibility" in Project rules for the policy.

## Known Limitations

**Single session.** One player at a time. The module-level accumulators (`_pending_events`, `_token_log`) and the in-memory SQLite database assume single-threaded access. Multi-session would require per-session state isolation.

**No faction layer yet.** Within the in-scope scheme-and-individual-relationships boundary defined under Deliberate divergences below: faction-level schemes, faction-player reputation, and faction-NPC loyalty thresholds are not implemented. NPCs act individually via agenda and goal-clocks. The "world moves independently" principle is partially realized through autonomous clock ticks and NPC agency checks, not through the scheme-interaction layer that the scope boundary calls for.

**No fiction generators yet.** Apart from oracle-rolled NPC names (`npc/naming.py`), NPCs, locations, and encounters are generated by the AI from context, not from structured oracle table rolls. The design document specifies hybrid generators (oracle tables produce structure, AI writes description within that structure). This means the engine currently relies on AI invention where it should rely on oracle-constrained generation. It also works the other way round: the `narrator_metadata` extraction registers the NPCs, renames, and deaths the prose introduces, so narration can establish facts that the engine then treats as state.

**No NPC-player emotional dynamics yet.** The engine tracks NPC disposition and bond but not relationship-altering events (broken promises, betrayals, sacrifices), emotional requests, or refusal/concession history. NPCs react to standing relationship state, not to the dynamic history of the relationship. Planned within the in-scope boundary defined under Deliberate divergences — individual scale and player-involving triangles only.

**Asset mechanics limited to adds.** Enabled abilities of paths and assets that grant an add reach the action roll through the Brain's `bonus_id` (`mechanics/bonuses.py`), and an upgrade enables the next ability in order (`mechanics/assets.py`). Rerolls, extra effects on a hit, condition meters for companions and vehicles, and choosing which ability an upgrade enables are not modelled (roadmap step 18).

## Deliberate divergences from the source rulebooks

Where a rule comes from Ironsworn/Starforged, Mythic GME 2e, or the Adventure Crafter, the engine follows the source; `tests/test_rules_conformance.py` pins the checked rules, including an automated comparison of every unconditional momentum gain in the Datasworn move texts with `engine/move_outcomes.yaml`. These are the known, deliberate exceptions:

- **Chaos factor per turn.** Mythic adjusts the chaos factor once per scene, by whether the player characters were in control. Straightjacket treats each turn as a scene and reads control from the roll: a miss raises the chaos factor by one, a strong hit lowers it by one, a weak hit leaves it, and dialog moves it by the NPC's disposition (`engine/chaos.yaml`). Start 5 and range 1 to 9 follow Mythic.
- **Classic Ironsworn uses Starforged's impact model.** `engine/move_outcomes.yaml` follows Starforged and `move_outcome_overrides` holds the classic Ironsworn differences (Secure an Advantage, Endure Harm, Endure Stress), so the numbers follow each rulebook. Classic Endure Harm and Endure Stress mark Ironsworn's own lasting harm (`maimed`, `corrupted`; `engine/impacts.yaml` also knows `encumbered`). What classic still borrows from Starforged is that wounded or shaken blocks recovery, where Ironsworn only asks for health or spirit above 0.
- **Classic Ironsworn earns experience through Starforged's legacy tracks.** Ironsworn marks experience directly when a vow is fulfilled; Straightjacket marks the quests, bonds, and discoveries legacy tracks in every setting and earns experience per filled box.
- **Make a Connection shifts the NPC's disposition** on a strong hit, an engine addition with no rulebook number behind it; the move itself gives no momentum and no progress.
- **Fixed choices where the player would choose a cost.** Where an outcome lets the player pick a cost from a list (Take Decisive Action and End the Fight on a weak hit, classic Reach Your Destination on a miss), the engine pays the price instead.
- **Pay the Price rolls the official table and costs 1.** `engine/pay_the_price.yaml` names the setting's Datasworn table; a row that says the character is harmed, stressed, or wastes resources costs 1 health, spirit, or supply, the smallest suffer amount, where the rules leave the size to the player.
- **A chained move is rolled at once, and only if it has a roll.** Where an outcome says to make another move (Test Your Relationship's hits say Develop Your Relationship), the move effect `chain_move` makes `game/finalization.py` roll that move in the same turn, with the best stat its roll options allow or, for a connection move, the connection's rank, spending a banked next-move bonus; its consequences join the first move's for the narrator. A chained move without a roll is an oracle move configured under `oracle_moves` in `engine/move_outcomes.yaml`: the engine rolls its table and marks its legacy ticks at once, where the rules mark them when the discovery or aspect is first engaged. Confront Chaos lets the player choose one to three aspects; the engine takes one.
- **Roll bonuses: the Brain judges the condition, the engine owns the number.** `mechanics/bonuses.py` offers every enabled ability of the character's paths and assets whose text grants an add ("add +1"), and every active connection's aid (add +1 and +1 momentum on a hit, `engine/roll_bonuses.yaml`), in a `<bonuses>` block of the Brain message; the Brain names at most one by id in `bonus_id` when the action clearly meets its condition, and the engine checks the id and takes the add from the rule text. Momentum on a hit counts only when the text ties it to the same add. One bonus per roll. Upgrading an asset enables its abilities in order (`mechanics/assets.py`), where the player would choose. Ability effects other than adds (rerolls, extra effects, special moves) are not modelled.
- **Boasts are not modelled.** Draw the Circle grants its weak-hit momentum without the boast the player would choose.
- **A fate-chart roll of 100 counts as doubles** and triggers a random event; Mythic 2e does not settle this edge case.

## Deliberate divergences from the design document

Five places where Straightjacket departs from the design document's architectural recommendations or settles one of its open questions. Each was an explicit decision, taken on empirical grounds or as a deliberate scope boundary, not a discard from the document.

**Input parsing as a separate call.** The design document specifies that input parsing is integrated into the single narrator call — the AI classifies the action type and narrates the result in one response. Straightjacket uses a separate Brain call that classifies input before the narrator writes prose. This split was already present in EdgeTales, where the integrated approach did not produce reliable classification. Straightjacket, which began as a fork of EdgeTales, preserved the split on the same empirical grounds. Because the two codebases share a lineage (see ORIGINS.md), this is one line of evidence carried forward, not two independent confirmations.

**Tool calling scoped per data type, not as a universal mechanism.** The design document proposes tool calling as the central engine-AI communication mechanism. Straightjacket diverges by treating tool-calling and prompt-injection as complementary: each callsite picks the gear that matches its data shape and role boundary (see "When tool-call vs when prompt-inject" above). The most visible consequence is that Brain receives all game state via prompt injection — the deeper principle being that Brain must not be allowed to pick which moves are available or which NPCs are present (engine decides). The core principle ("tools determine results, AI narrates") is preserved across all roles.

**Two-call narrator pattern.** The design document treats narration as a single AI call — one prose response per turn within hard constraints. Straightjacket runs a second call on the extraction cluster after the prose is written: the narrator_metadata extractor reads the rendered narration and returns structured NPC-related data (new NPCs, renames, details, deaths) for the engine to apply to game state. Opening_setup, revelation_check, recap, and chapter_summary are likewise separate calls. The split exists because asking the narrator model to also emit structured metadata in the same response degraded prose quality; the extraction cluster is configured for pure data extraction and does not have to balance two output contracts at once.

**No narration validator.** The design document leaves constraint verification as an open question with three candidate answers: a second, cheaper AI call that checks output against the constraints; predefined severity markers the engine checks programmatically; or leaning harder on engine-dictated consequences so there is less to verify. Straightjacket built the first option as a validator (LLM-pass plus regex-pass plus retry-loop) and ran it for many versions, then removed it in 2026.04.27.8. The verdict: verifying writing rules with an AI judge is unreliable on rules ambiguous even for humans, and the retry-loop produced predictable prose flattening as the narrator was steered away from anything the validator might flag. The principle now is AI-surface reduction, which is the document's third option: the engine narrows what the AI can produce (engine-dictated consequences, oracle-driven generation, engine-computed pacing, vocabulary control) rather than checking what it produced. A diagnostic measurement layer without retry or prompt injection remains an open option after the roadmap is fully implemented.

**Faction layer scoped to schemes and individual relationships.** The design document's Relationships/Memory and Agency/Motivation chapters describe faction schemes with goal-clocks, faction-level reputation, NPC loyalty thresholds toward their faction, and a dynamic scale of emotional requests, refusals, and concessions, without settling whether that dynamic scale also runs between factions. Straightjacket scopes the dynamic relationship layer differently: in scope are the individual scale (emotional requests, refusals, concessions, relationship events between NPC and player) plus NPC-NPC triangles that involve the player. Factions operate through schemes with independent goal-clocks, faction-player reputation, and scheme-interactions that surface as narrative consequences on encounter. Inter-faction emotional dynamics (faction-to-faction emotional requests, refusals, debts as a separate layer) are out of scope. The narrative effect the document calls for is achieved through scheme-interaction, not through a simulated faction-emotion network. This is a deliberate scope boundary, not a deferred feature.

## Testing

```bash
python -m pytest tests/                                # unit/integration suite
python tests/elvira/elvira.py --auto                   # direct engine, 8 turns, random setting and style (needs API keys)
python tests/elvira/elvira.py --auto --matrix --turns 8 # every setting and style in turn
python tests/elvira/elvira.py --auto --turns 40        # a long run that reaches rarer situations
python tests/elvira/elvira.py --auto --scenario all     # every prepared rare situation in turn
python tests/elvira/elvira.py --ws --auto --turns 5    # via WebSocket server
```

Three layers of testing, complementary, plus the static checks (ruff, mypy) listed under Contributing:

The **unit/integration test suite** (`python -m pytest tests/ -v`) runs without an API key. It uses mock providers that return canned responses. Tests verify the engine's internal logic: consequences, NPC processing, serialization, correction flow, prompt assembly, WebSocket handlers. Every PR must pass this suite.

**Project rules** (`tests/test_project_rules.py`) is one consolidated test running AST and regex scans that enforce the rules described in the Project rules section. A meta-scan fails on carve-out or whitelist entries that no longer match a file or symbol, so an exception cannot outlive the code it excuses. Four documentation-drift scans: every path named in README, ARCHITECTURE, SECURITY, ORIGINS, and AUDIT exists, the file map below is complete, every `file.py → symbol` reference in this document resolves, and the CHANGELOG matches the `pyproject.toml` version. `roadmap.md` is not scanned, and of the CHANGELOG only the version headers are. Failures are deterministic measurements — the test fails on residual debt without blocking feature work. When you touch a file that already has violations, fix them in the same commit.

**Elvira** (`tests/elvira/elvira.py`) is a headless test player that plays the real game on the models `config.yaml` names. Her own player and her judge use the provider and model named under `ai` in `tests/elvira/elvira_config.yaml` (GPT-6 Luna since 2026.09.26.2), the judge at its own reasoning setting there (`low`; at GPT-6 Luna's default effort the reasoning once used up the token limit and left no verdict, CHANGELOG 2026.09.24.35), and both log as the role `elvira`, whose cost her report lists apart from the game's total. Because she stays on one model while the game's clusters change, the same judge scores every game model; it sees one turn at a time and scores against its rubric, so its result-integrity scores are read together with the narrations (CHANGELOG 2026.09.26.2). To try another game model, point `STRAIGHTJACKET_CONFIG` at a copy of `config.yaml` with other clusters and give Elvira a config with its own `username`, so several runs can play side by side. Each run picks its setting (classic, starforged, or sundered_isles; delve is an expansion, not a setting of its own) and its play style at random unless the config or the command line names one, and `--matrix` plays every combination in turn. Every turn it checks state invariants (including NPC-DB and combat-track sync), leaked mechanics, NPC spatial consistency, and streaming (time to first sentence; streamed text equal to the final text), and a blind judge scores the narration on result integrity, prompt elements, NPC voice, player agency, restraint, and prose. After every save it loads the game back and compares the whole state; on game over it continues through succession. Once per run (`session.inject_ai_failure_turn`) it makes the narrator unreachable for one turn and checks that the turn is rolled back to exactly the state before it; a real AI failure is rolled back the same way, reported as a problem, and play continues. `--scenario` prepares a rare situation after character creation and reports whether the run reached what the scenario expects: `near_death` (health and spirit 0, and the player takes physical risks so the first turn is an action: game over at its crisis check, then succession and play on), `chapter_end` (one scene before the story's end: epilogue and new chapter), `momentum_burn` (momentum at its maximum: a burn offered and taken), `combat` (an open fight), and `clock` (a clock one segment from full); `--scenario all` plays them in turn. The scenarios live in `tests/elvira/elvira_config.yaml` and the preparation in `tests/elvira/elvira_bot/scenarios.py`. It captures the engine log per turn: lines with the prefixes in `logging.event_prefixes` become events (bonuses, chained moves, Pay the Price, extraction, Director and tools), and every warning or error, whatever its prefix, becomes a problem in the report, because a failed side call (metadata extraction, Director, revelation check, recap, chapter summary, blueprint voicing) degrades by design and the game would otherwise play on silently. A coverage tracker records which parts of the game a run touched and steers the bot towards what is missing. Each run writes a JSON session log (full narration, NPCs, verdict, streaming figures, events, and warnings per turn) and a Markdown report to `tests/elvira/runs/`, which stays local and is ignored by git: verdict first, then problems, coverage, audit, streaming, engine events, speed, and estimated cost. `tests/test_elvira_smoke.py` runs both modes against the mock provider in the normal test gate.

- Direct mode drives the engine directly; the fastest way to test engine changes.
- WebSocket mode (`--ws`) plays through the real server stack and also probes the status, tracks, threats, and recap messages.

Run Elvira before a release that touches the turn pipeline, AI calls, prompts, or configuration: the unit tests catch logic bugs, Elvira catches what only real model output and real data reveal.

## Adding a New AI Provider

1. Create `ai/provider_yourname.py` implementing the `ModelListingProvider` protocol (`create_message` plus `list_models`, see `provider_base.py`)
2. Add a branch for its type in `ai/api_client.py` → `build_adapter`
3. Add an entry under `ai.providers` in config.yaml with that `type`, and point clusters at it with `provider:`

A service with an OpenAI-compatible endpoint needs only step 3, with `type: openai_compatible`.

## Adding a New Setting

Settings are data packages that combine a Datasworn JSON file (game content: moves, oracles, assets) with a settings YAML file (engine integration: vocabulary, genre constraints, oracle paths).

### Step by step

1. Place the Datasworn JSON at `data/<datasworn_id>.json`, where `<datasworn_id>` is the value you will declare inside the yaml. Datasworn JSON files contain the game's mechanical content: moves, oracles, assets (paths/companions/etc). See [github.com/rsek/datasworn](https://github.com/rsek/datasworn) for the format.
2. Create `data/settings/<id>.yaml` (use `data/settings/starforged.yaml` as template). The yaml stem is the setting id used by the engine; `datasworn_id` inside the yaml points at the JSON file.
3. The setting appears in character creation automatically — no Python changes needed.

### Settings YAML format

Parsed strictly at load. Required top-level keys: `id`, `title`, `datasworn_id`, `description`, `oracle_paths`, `vocabulary`. Optional: `parent`, `creation_flow`. Missing required keys raise `KeyError`, and so does a key the loader does not know, at the top level or inside `oracle_paths`, `vocabulary`, or `creation_flow`.

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
  names: ["characters/name/given", "characters/name/family_name"]
  backstory: "campaign_launch/backstory_prompts"
  threats: "campaign_launch/sector_trouble"

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

## Code standards

Python 3.11+. Dataclasses with type hints. f-strings. pathlib. snake_case. No mutable defaults. Imports sorted, top of file. Max line length 120 (ruff handles this).

Read `pyproject.toml` for the full ruff/mypy config. The linter rules are the spec — if ruff passes, you're fine. mypy runs in strict mode (`strict = true`): every function is typed, generics state their parameters, re-exports are explicit through `__all__`, and a value that arrives as `Any` from yaml or JSON gets its type where it enters typed code.

## Project rules

These rules apply across the codebase. They are enforced mechanically by `tests/test_project_rules.py` and consciously upheld in review. They exist because every shortcut Python's defaulting and exception-swallowing make tempting eventually hides a real bug.

**No `#` comments and no docstrings in Python or yaml.** Code explains itself through names, types, and tests. Context, motivation, and architecture live in the md-files at the repo root, not in the code. Three narrow exceptions where a single short trailing comment is permitted at the callsite: external-boundary defaults, the AI-call carved exception, and inline imports for circular-break or lazy-load. The exception buys a half-line, not a paragraph.

**Domain config keys raise on miss.** Engine config is read by direct subscript (`config["key"]`). No `dict.get` with a literal fallback. No `x or "fallback"`. No dataclass defaults on fields that bind to a config value. If a key is missing, the engine should fail loudly, not silently substitute a value the rest of the code wasn't designed for.

Three exceptions survive: language-mandated empty collections (`field(default_factory=list)`), parsing of variable external structures, and the AI-call carve-out below. External structures means: a Datasworn field absent in at least one of the four shipped Datasworn rulesets (verifiable by grep) or marked optional in schema; a WebSocket field defined as optional in protocol spec; an AI-call field part of a documented retry-fallback dict, not happy-path response. Required-per-spec fields do not qualify even at external boundary. When in doubt, treat as required.

**Yaml content boundary.** Yaml holds values whose source can be named — a Datasworn table, an AC table, a Mythic table, a mechanical computation, or a value present elsewhere in the codebase. Values without a nameable source go in AI-call output (with setting context in the prompt), in an oracle roll, or stay absent until decided. Prose-shaped values (mood words, descriptive phrases, narrative templates) do not belong in yaml. The boundary covers every yaml in the repository, setting yaml under `data/settings/` included (decided in 2026.09.24.47). Its one exception is a setting's `vocabulary` block: the design document assigns vocabulary control to the setting as a constraint on the narrator's word choice, and it has no table source; new entries are added only when a measured drift calls for them.

**User-, narrator-, and AI-readable strings live in config or prompt files.** Not hardcoded in Python. `engine/*.yaml`, `prompts/*.yaml`, `strings/*.yaml`, and `emotions/*.yaml` are the homes. Adding a constant to Python should be a last resort with a written reason.

**Errors propagate.** No broad `except Exception: pass`, no `contextlib.suppress` over domain logic. The carve-out is AI-call sites and tool-boundary functions returning structured error dicts to an AI caller — the broad catch is logged at warning level. See "AI-call exception carve-out" under Key Design Decisions for why the carve-out exists.

**No backwards compatibility.** Saves break when the code requires it. No migration layers, no default-on-old-fields, no ignore-unknown-fields. This is by design for an alpha project with no production users; if it changes, it changes deliberately, not silently. `serialization.py` enforces it at load: a field default makes a fresh object, never an old save loadable.

**Update every caller in the same commit.** When a function signature, dataclass field, or yaml key changes, fix the callers immediately. Delete legacy code rather than retire it. Two-sided removal: a symbol is removed only when both code-side and config-side are dead — no readers, no writers beyond the definition.

When you touch a file that already has violations, fix them in the same commit. The project-rule tests measure residual debt; their failures aren't blocking, but they aren't ignorable either.

## Config-driven design

Game mechanics, emotion scoring, move types, damage tables, disposition shifts — all in YAML. Before adding a constant to Python, check if it belongs in `engine/`. Prompts are tuned per role for the active models; switching models means re-tuning in place, not adding parallel variants.

## Contributing

1. Fork, branch, make your change
2. `ruff check --fix src/ tests/` and `ruff format src/ tests/` — must be clean
3. `python -m pytest tests/ -q --cov` — all tests must pass, and total coverage must stay at or above `fail_under` in `pyproject.toml` (`[tool.coverage.report]`); raise the floor when coverage rises, never lower it. The one exception is `test_project_rules.py` reporting residual debt in files you did not touch (see Project rules); any new violation is blocking
4. `mypy src/ --config-file pyproject.toml` — must be clean
5. PR with a clear description of what and why

## Accessibility

This project is built by a blind developer. Screen reader accessibility is not optional. If you add UI elements: semantic HTML, ARIA live regions, heading structure, native form controls. No div-buttons, no spatial-only references.
