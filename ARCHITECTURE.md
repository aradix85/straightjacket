# Architecture

How a turn flows through the system. Read this first.

## Turn Pipeline

Player types "I search the room" → engine returns narration + updated game state.

```
player input
  ↓
Brain (ai/brain.py)           → classifies input into a move, stat, position, effect
  ↓
Roll (mechanics.py)           → 2d6+stat vs 2d10, result: STRONG_HIT / WEAK_HIT / MISS
  ↓
Consequences (mechanics.py)   → damage tables from engine.yaml, clock ticks, crisis check
  ↓
NPC Activation (npc/activation.py) → TF-IDF scores decide which NPCs get full context
  ↓
Prompt Builder (prompt_builders.py) → assembles XML prompt with world, NPCs, result, pacing
  ↓
Narrator (ai/narrator.py)    → AI writes prose (conversation memory for style consistency)
  ↓
Validator (ai/validator.py)   → checks 5 constraints, up to 2 retries on failure
  ↓
Parser (parser.py)            → strips leaked metadata from prose (10-step cleanup pipeline)
  ↓
Metadata Extractor (ai/narrator.py → ai/metadata.py)
                              → separate AI call extracts NPCs, memories, location, time
  ↓
Director (director.py)        → lazy story steering, NPC reflections, act transitions
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
| Server, API provider, language | `config.yaml` (no Python) |
| Move types or stat assignments | `engine.yaml` → `move_stats` and `move_categories` |
| A new setting (genre + constraints) | `data/settings/your_setting.yaml` + Datasworn JSON |
| How dice rolls work | `mechanics.py` → `roll_action`, `apply_consequences` |
| How the narrator is prompted | `prompt_builders.py` → `build_action_prompt`, `build_dialog_prompt` |
| NPC memory / activation logic | `npc/memory.py`, `npc/activation.py` |
| Story structure / act tracking | `story_state.py`, `ai/architect.py` |
| Correction (## undo) flow | `correction.py` |
| Save format | `models.py` → `to_dict`/`from_dict` on the relevant dataclass |
| Character creation UI | `ui/creation.py` (Datasworn-driven, no AI call) |

## File Map

```
src/straightjacket/
├── engine/
│   ├── models.py            # All data: GameState, NpcData, ClockData, MemoryEntry, etc.
│   ├── mechanics.py         # Dice, chaos, consequences, clocks, momentum
│   ├── parser.py            # Narrator output cleanup (10 regex steps)
│   ├── correction.py        # ## correction and momentum burn re-narration
│   ├── director.py          # Story steering, NPC reflections, act transitions
│   ├── persistence.py       # Save/load, chapter archives
│   ├── story_state.py       # Act tracking, revelation timing
│   ├── prompt_builders.py   # All narrator prompt assembly
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
│   │   ├── validator.py     # Post-narrator constraint checking
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
│   │   └── setup_common.py  # Shared opening setup logic
│   └── datasworn/
│       ├── loader.py        # Reads Datasworn JSON (oracles, assets, moves)
│       └── settings.py      # Setting packages (vocabulary, genre constraints)
├── ui/                      # NiceGUI frontend (framework-bound)
│   ├── phases.py            # Login → user selection → main game routing
│   ├── gameplay.py          # Turn input → engine → render
│   ├── creation.py          # Datasworn-driven character creation
│   ├── endgame.py           # Momentum burn, epilogue, game over
│   ├── sidebar.py           # Stats, NPCs, clocks, save/load
│   ├── chat.py              # Message history rendering
│   └── helpers.py           # Session state, scroll, entity highlighting
├── i18n.py                  # String lookup (t()), emoji constants
└── strings_loader.py        # Reads strings.yaml
```

## Key Design Decisions

**Config-driven game logic.** Move types, damage tables, disposition shifts, NPC seed emotions — all in engine.yaml. Adding a move type means adding one line to `move_stats` and one to `move_categories`. No Python change.

**Typed dataclasses everywhere.** GameState has sub-objects (Resources, WorldState, NarrativeState, CampaignState). NpcData has 19 fields. MemoryEntry has 10. Attribute access, never dict-style. `_fields_to_dict`/`_fields_from_dict` helpers handle flat serialization; complex classes override manually.

**Two-call pattern.** Narrator writes pure prose. A second fast-model call extracts structured metadata (NPCs, memories, location, time). This keeps the narrator prompt clean and works across providers.

**Snapshot/restore.** `GameState.snapshot()` captures all mutable state before a turn. `restore()` reverts everything atomically. Used by correction (##) and momentum burn.

**Provider abstraction.** `AIProvider` protocol with two implementations (Anthropic, OpenAI-compatible). The engine never imports provider SDKs directly. `create_with_retry` handles transient errors with exponential backoff.

## Testing

```bash
python -m pytest tests/ -v          # 205 tests, ~5 seconds
python elvira/elvira.py --auto --turns 5   # headless integration (needs API key)
```

Elvira is the real integration test. It drives the full engine with an AI player bot, checks state invariants after every turn, runs narration quality checks, tests the correction pipeline, and verifies NPC spatial consistency across chapter transitions.

## Adding a New AI Provider

1. Create `ai/provider_yourname.py` implementing `AIProvider` protocol (see `provider_base.py`)
2. Add a branch in `ai/api_client.py` → `get_provider()`
3. Set `ai.provider` in config.yaml

## Adding a New Setting

1. Get Datasworn JSON → `data/your_setting.json`
2. Create `data/settings/your_setting.yaml` (see starforged.yaml as template)
3. Define vocabulary substitutions, genre constraints, oracle paths
4. The setting appears in character creation automatically
