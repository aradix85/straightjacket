# Architecture

How a turn flows through the system. Read this first.

## Turn Pipeline

Player types "I search the room" → engine returns narration + updated game state.

```
player input
  ↓
Brain (ai/brain.py)           → classifies input into a move and stat via tool calling
  ↓
Roll (mechanics/consequences.py) → 2d6+stat vs 2d10, result: STRONG_HIT / WEAK_HIT / MISS
  ↓
Consequences (mechanics/consequences.py) → damage tables from engine.yaml, clock ticks, crisis check
  ↓
NPC Activation (npc/activation.py) → TF-IDF scores decide which NPCs get full context
  ↓
Prompt Builder (prompt_builders.py) → assembles XML prompt with world, NPCs, result, pacing
  ↓
Narrator (ai/narrator.py)    → AI writes prose (conversation memory for style consistency)
  ↓
Validator (ai/validator.py)   → hybrid rule-based + LLM check, up to 3 retries with prompt stripping
  ↓
Parser (parser.py)            → strips leaked metadata from prose (10-step cleanup pipeline)
  ↓
Metadata Extractor (ai/narrator.py → ai/metadata.py)
                              → separate AI call extracts NPCs, memories, location, time
  ↓
Director (director.py)        → lazy story steering, NPC reflections, act transitions
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
| AI prompts (narrator, brain, director) | `prompts.yaml` (no Python) |
| Emotion scoring, keyword boosts | `emotions.yaml` (no Python) |
| UI text | `strings.yaml` (no Python) |
| Server port | `config.yaml` (no Python) |
| Move types or stat assignments | `engine.yaml` → `move_stats` and `move_categories` |
| A new setting (genre + constraints) | `data/settings/your_setting.yaml` + Datasworn JSON |
| How dice rolls work | `mechanics/consequences.py` → `roll_action`, `apply_consequences` |
| How the narrator is prompted | `prompts.yaml` → task templates; `prompt_builders.py` → XML assembly |
| NPC memory / activation logic | `npc/memory.py`, `npc/activation.py` |
| Story structure / act tracking | `story_state.py`, `ai/architect.py` |
| Correction (## undo) flow | `correction.py` |
| Save format | `models.py` → `to_dict`/`from_dict` on the relevant dataclass |
| WebSocket protocol / UI | `web/handlers.py`, `web/static/index.html` |
| Character creation validation | `game/game_start.py` → `validate_stats`, stat arrays in `engine.yaml` |
| Creation data for client | `web/serializers.py` → `build_creation_options` |
| Setting-specific creation flow | `data/settings/*.yaml` → `creation_flow` block |
| Progress track mechanics | `models_base.py` → `ProgressTrack`, `PROGRESS_RANKS` |
| Mythic threads/characters lists | `models_story.py` → `ThreadEntry`, `CharacterListEntry` |
| Truths in narrator prompt | `prompt_blocks.py` → `truths_block` |
| Director pacing (engine-computed) | `director.py` → `_map_pacing_hint`, reads `mechanics/world.py` → `get_pacing_hint` |
| Act transitions (engine-computed) | `director.py` → `_check_engine_act_transition` |
| Memory emotional weight (engine-computed) | `mechanics/engine_memories.py` → `derive_memory_emotion`, table in `engine.yaml` |
| Database queries (NPCs, memories, threads, clocks) | `db/queries.py` → `query_npcs`, `query_memories`, `query_threads`, `query_clocks` |
| Database sync after state changes | `db/sync.py` → `sync(game)`, called by turn, creation, correction, restore, load |
| Tool definitions for AI agents | `tools/registry.py` → `@register("brain")`, `get_tools(role)` |
| Tool execution and iterative loop | `tools/handler.py` → `execute_tool_call`, `run_tool_loop` |
| Built-in query tools | `tools/builtins.py` → `query_npc`, `query_active_threads`, `query_active_clocks`, `query_npc_list` |
| Consequence sentence templates | `engine.yaml` → `consequence_templates`, `pay_the_price` (no Python) |
| Consequence sentence generation | `mechanics/consequences.py` → `generate_consequence_sentences` |
| NPC stance matrix | `engine.yaml` → `stance_matrix` (no Python) |
| NPC stance resolution | `mechanics/stance_gate.py` → `resolve_npc_stance`, `NpcStance` |
| Information gate levels | `engine.yaml` → `information_gate` (no Python) |
| Information gate computation | `mechanics/stance_gate.py` → `compute_npc_gate` |
| Gate-filtered NPC prompt data | `prompt_builders.py` → `_npc_block` (gate 0–4 filtering) |

## File Map

```
src/straightjacket/
├── engine/
│   ├── models.py            # Re-export hub for all dataclasses
│   ├── models_base.py       # EngineConfig, Resources, ProgressTrack, WorldState, ClockData/Event
│   ├── models_npc.py        # NpcData, MemoryEntry
│   ├── models_story.py      # ThreadEntry, CharacterListEntry, NarrativeState, StoryBlueprint, etc.
│   ├── format_utils.py      # PartialFormatDict (shared by prompt_loader, strings_loader)
│   ├── mechanics/
│   │   ├── world.py            # Location matching, chaos, time, pacing, story structure
│   │   ├── resolvers.py        # Position, effect, time progression, move category
│   │   ├── consequences.py     # Dice, consequences, clocks, momentum, consequence sentences
│   │   ├── stance_gate.py      # NPC stance resolution, information gating
│   │   └── engine_memories.py  # Memory emotion derivation, engine memories, scene context
│   ├── parser.py            # Narrator output cleanup (10 regex steps)
│   ├── correction.py        # ## correction and momentum burn re-narration
│   ├── director.py          # Story steering, NPC reflections, act transitions
│   ├── persistence.py       # Save/load
│   ├── story_state.py       # Act tracking, revelation timing
│   ├── prompt_builders.py   # Narrator prompt XML assembly (task text from prompts.yaml)
│   ├── prompt_blocks.py     # Reusable XML blocks (content boundaries, backstory, etc.)
│   ├── prompt_loader.py     # Reads prompts.yaml
│   ├── config_loader.py     # Reads config.yaml, provides cfg() singleton
│   ├── engine_loader.py     # Reads engine.yaml, provides eng() singleton
│   ├── emotions_loader.py   # Reads emotions.yaml
│   ├── ai/
│   │   ├── provider_base.py # AIProvider protocol + retry wrapper
│   │   ├── provider_anthropic.py
│   │   ├── provider_openai.py  # Any OpenAI-compatible API
│   │   ├── brain.py         # Input → move classification
│   │   ├── narrator.py      # Prose generation + metadata extraction calls
│   │   ├── metadata.py      # Apply extracted metadata to game state
│   │   ├── architect.py     # Story blueprint, recap, chapter summary
│   │   ├── validator.py     # Hybrid constraint checking (rule-based + LLM)
│   │   ├── rule_validator.py # Instant rule-based checks (player agency, result integrity, genre, format)
│   │   └── schemas.py       # JSON output schemas (config-driven)
│   ├── npc/
│   │   ├── matching.py      # Name lookup, fuzzy matching, edit distance
│   │   ├── memory.py        # Importance scoring, retrieval, consolidation
│   │   ├── activation.py    # TF-IDF context selection for prompts
│   │   ├── lifecycle.py     # Identity merging, retiring, reactivation
│   │   └── processing.py    # Narrator metadata → NPC state changes
│   ├── game/
│   │   ├── turn.py          # Main turn pipeline (process_turn)
│   │   ├── game_start.py    # Character creation → opening scene
│   │   ├── chapters.py      # Epilogue, new chapter orchestration
│   │   ├── setup_common.py  # Shared opening setup logic
│   │   ├── finalization.py  # Shared post-narration state mutations
│   │   └── director_runner.py # Deferred Director call
│   └── datasworn/
│       ├── loader.py        # Reads Datasworn JSON (oracles, assets, moves)
│       └── settings.py      # Setting packages (vocabulary, genre constraints)
│   ├── db/
│   │   ├── schema.sql       # Table definitions (8 tables, mirrors dataclasses)
│   │   ├── connection.py    # In-memory SQLite singleton (init, get, reset, close)
│   │   ├── sync.py          # Full GameState → database sync (replace, not diff)
│   │   └── queries.py       # Read-only query functions → dataclass instances
│   ├── tools/
│   │   ├── registry.py      # @register decorator, type hints → OpenAI tool schemas
│   │   ├── handler.py       # Tool dispatch, iterative tool-call loop
│   │   └── builtins.py      # Built-in query tools for Brain and Director
├── web/
│   ├── server.py            # Starlette app, WebSocket endpoint, dispatch
│   ├── handlers.py          # One async function per protocol message type
│   ├── session.py           # Session dataclass (all mutable server state)
│   ├── serializers.py       # Game state → client JSON (i18n labels resolved)
│   └── static/
│       └── index.html       # Single-page app (HTML + CSS + JS inline)
├── i18n.py                  # String lookup (t()), label getters
└── strings_loader.py        # Reads strings.yaml
```

## Key Design Decisions

**Config-driven game logic.** Move types, damage tables, disposition shifts, NPC seed emotions — all in engine.yaml. Adding a move type means adding one line to `move_stats` and one to `move_categories`. No Python change.

**Typed dataclasses everywhere.** GameState has sub-objects (Resources, WorldState, NarrativeState, CampaignState). NpcData has 19 fields. MemoryEntry has 10. Attribute access, never dict-style. `SerializableMixin` handles serialization; complex classes override `to_dict`/`from_dict` manually.

**Two-call pattern.** Narrator writes pure prose. A second fast-model call extracts NPC-related metadata (new NPCs, renames, details, deaths). This keeps the narrator prompt clean and works across providers.

**Snapshot/restore.** `GameState.snapshot()` captures all mutable state before a turn. `restore()` reverts everything atomically. Used by correction (##) and momentum burn.

**Provider abstraction.** `AIProvider` protocol with two implementations (Anthropic, OpenAI-compatible). The engine never imports provider SDKs directly. `create_with_retry` handles transient errors with exponential backoff.

**Minimal UI.** Single HTML page, no build step, no npm. Server sends JSON, client renders. Scene headings for screen reader navigation, aria-live for automatic narration readout. Two buttons (Status, Save/Load), one text input.

**Progress tracks as dataclass.** ProgressTrack has rank-based ticks_per_mark (troublesome=12, epic=1). Background vow becomes a track at creation. Vow ranks and tick rates in PROGRESS_RANKS dict.

**Mythic lists seeded at creation.** Threads list starts with the background vow (weight 2) plus any tensions derived from truth selections via engine.yaml templates. Characters list starts with the vow subject (if provided) and opening scene NPCs. Both lists are in NarrativeState for snapshot/restore.

**Truths as world context.** Player truth selections stored in GameState.truths and injected into every narrator prompt as a `<world_truths>` block. The narrator treats them as established canon. Truths that match engine.yaml patterns automatically seed tension threads.

**AI surface minimization.** Every value derivable from game state is computed by the engine. Director pacing is computed from scene_intensity_history, not requested from the AI. Act transitions fire when scene_count exceeds act range — deterministic, no AI flag. Memory emotional_weight is derived from (move_category, result, disposition) via engine.yaml lookup. Opening scene clock and time_of_day are engine-determined before any AI call. The AI receives results, not choices.

**Engine-dictated consequences.** `apply_consequences` produces mechanical changes AND narrative sentences from engine.yaml templates. Each consequence gets a `<consequence>` tag in the narrator prompt. The narrator weaves them into prose but cannot change what happened. The validator checks keyword presence. Oracle tables (step 7) will add variety; templates are primary.

**NPC behavioral stance.** Engine computes per-NPC stance from disposition, bond, and move category via engine.yaml stance matrix (60 entries). The narrator receives `stance="evasive" constraint="One fact, then silence."` instead of raw `disposition="distrustful" bond="1/4"`. The engine tells the narrator how the NPC behaves, not just how they feel.

**Information gating.** Per-NPC gate level (0–4) controls what enters the narrator prompt. Gate 0 = name + description (stranger). Gate 4 = full secrets. Computed from scenes known, gather_information successes, bond level, and stance cap. The narrator cannot reveal what it doesn't have. Stance caps prevent hostile NPCs from being too transparent regardless of bond.

**Database as read model.** SQLite (in-memory, stdlib) mirrors GameState after every turn, creation, correction, restore, and load. GameState dataclasses remain the write model — all mutations go through Python. The database provides indexed queries for prompt builders, tool handlers, and future NPC trigger evaluation. Ephemeral: rebuilt from GameState on load/restore, no migration burden. JSON save files remain the persistence format.

**Tool calling.** Decorator-based registry (`@register("brain", "director")`) produces OpenAI function calling schemas from Python type hints. Iterative handler loop: AI calls tool → engine executes → result appended → AI continues, with configurable round limit. Tools are read-only: they query GameState and database but never mutate. Brain uses tool calling for classification (slim prompt, selective queries). Director uses two-phase: tool loop for context, then json_schema for structured output.

## Testing

```bash
python -m pytest tests/ -v          # ~20 seconds, ~485 tests
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

1. Get the Datasworn JSON for your setting → `data/your_setting.json`. Datasworn JSON files contain the game's mechanical content: moves, oracles, assets (paths/companions/etc). See [github.com/rsek/datasworn](https://github.com/rsek/datasworn) for the format.
2. Create `data/settings/your_setting.yaml` (use `data/settings/starforged.yaml` as template).
3. The setting appears in character creation automatically — no Python changes needed.

### Settings YAML format

```yaml
# data/settings/your_setting.yaml
id: your_setting                    # Must match the Datasworn JSON filename (without .json)
title: "Your Setting Name"          # Display name in character creation
description: "One paragraph describing the world, tone, and premise."

# Vocabulary substitutions: generic term → setting-specific term.
# Included in every narrator prompt to keep the AI in-genre.
vocabulary:
  spaceship: iron vessel
  planet: forge-world
  alien: abomination

# Genre constraints: what must NOT appear in narration or story blueprints.
genre_constraints:
  forbidden_terms:                  # Words the narrator must never use
    - magic
    - spell
    - wizard
  forbidden_concepts:               # Broader prohibitions for the architect validator
    - "supernatural powers beyond the setting's technology level"
  genre_test: "Could this exist in a world with only pre-industrial technology?"

# Oracle paths: where to find name tables and backstory prompts in the Datasworn JSON.
oracle_paths:
  names:                            # Used by Elvira's character creation for random names
    - "oracles/character/name/given"
    - "oracles/character/name/family"
  backstory:                        # Used for random backstory generation
    - "oracles/character/backstory"

# Character creation flow: controls which UI steps the client presents.
creation_flow:
  has_truths: true                  # Setting has world truths to choose
  has_backstory_oracle: true        # Datasworn backstory prompts available
  has_name_tables: true             # Datasworn name oracle tables available
  has_ship_creation: false          # Ship creation at character creation (Sundered Isles)
  starting_asset_categories:        # Non-path asset categories available at creation
    - companion
    - module
```

The `vocabulary` block maps generic fantasy/sci-fi terms to setting-specific language. This implements the design document's vocabulary control principle: the AI writes in the setting's voice instead of defaulting to genre conventions from training data.

The `genre_constraints` block feeds both the rule-based validator (forbidden_terms checked via regex) and the architect validator (forbidden_concepts checked via LLM). The `genre_test` string is a yes/no question the LLM applies to story blueprints.

The `creation_flow` block tells the client which character creation steps to present. Settings without backstory oracles (Classic) skip that step. Settings with ship creation (Sundered Isles) add it. The engine reads these flags in `build_creation_options()` and includes the relevant Datasworn data only when the flag is set.
