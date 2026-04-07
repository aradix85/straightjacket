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
Validator (ai/validator.py)   → hybrid rule-based + LLM check, up to 3 retries with prompt stripping
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
| Server port | `config.yaml` (no Python) |
| Move types or stat assignments | `engine.yaml` → `move_stats` and `move_categories` |
| A new setting (genre + constraints) | `data/settings/your_setting.yaml` + Datasworn JSON |
| How dice rolls work | `mechanics.py` → `roll_action`, `apply_consequences` |
| How the narrator is prompted | `prompt_builders.py` → `build_action_prompt`, `build_dialog_prompt` |
| NPC memory / activation logic | `npc/memory.py`, `npc/activation.py` |
| Story structure / act tracking | `story_state.py`, `ai/architect.py` |
| Correction (## undo) flow | `correction.py` |
| Save format | `models.py` → `to_dict`/`from_dict` on the relevant dataclass |
| WebSocket protocol / UI | `web/handlers.py`, `web/static/index.html` |

## File Map

```
src/straightjacket/
├── engine/
│   ├── models.py            # Re-export hub for all dataclasses
│   ├── models_base.py       # GameState, Resources, WorldState, NarrativeState
│   ├── models_npc.py        # NpcData, MemoryEntry
│   ├── models_story.py      # StoryBlueprint, StoryAct, Revelation, ChapterSummary
│   ├── format_utils.py      # PartialFormatDict (shared by prompt_loader, strings_loader)
│   ├── mechanics.py         # Dice, chaos, consequences, clocks, momentum
│   ├── parser.py            # Narrator output cleanup (10 regex steps)
│   ├── correction.py        # ## correction and momentum burn re-narration
│   ├── director.py          # Story steering, NPC reflections, act transitions
│   ├── persistence.py       # Save/load
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
│   │   └── setup_common.py  # Shared opening setup logic
│   └── datasworn/
│       ├── loader.py        # Reads Datasworn JSON (oracles, assets, moves)
│       └── settings.py      # Setting packages (vocabulary, genre constraints)
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

**Typed dataclasses everywhere.** GameState has sub-objects (Resources, WorldState, NarrativeState, CampaignState). NpcData has 19 fields. MemoryEntry has 10. Attribute access, never dict-style. `_fields_to_dict`/`_fields_from_dict` helpers handle flat serialization; complex classes override manually.

**Two-call pattern.** Narrator writes pure prose. A second fast-model call extracts structured metadata (NPCs, memories, location, time). This keeps the narrator prompt clean and works across providers.

**Snapshot/restore.** `GameState.snapshot()` captures all mutable state before a turn. `restore()` reverts everything atomically. Used by correction (##) and momentum burn.

**Provider abstraction.** `AIProvider` protocol with two implementations (Anthropic, OpenAI-compatible). The engine never imports provider SDKs directly. `create_with_retry` handles transient errors with exponential backoff.

**Minimal UI.** Single HTML page, no build step, no npm. Server sends JSON, client renders. Scene headings for screen reader navigation, aria-live for automatic narration readout. Two buttons (Status, Save/Load), one text input.

## Testing

```bash
python -m pytest tests/ -v          # ~5 seconds
python elvira/elvira.py --auto --turns 5   # direct engine (needs API key)
python elvira/elvira.py --ws --auto --turns 5  # via WebSocket server
```

Elvira is the real integration test. Direct mode drives the engine with an AI player bot, checks state invariants after every turn, runs narration quality checks, tests the correction pipeline, and verifies NPC spatial consistency. WebSocket mode does the same but through the full server stack.

## Adding a New AI Provider

1. Create `ai/provider_yourname.py` implementing `AIProvider` protocol (see `provider_base.py`)
2. Add a branch in `ai/api_client.py` → `get_provider()`
3. Set `ai.provider` in config.yaml

## Adding a New Setting

1. Get Datasworn JSON → `data/your_setting.json`
2. Create `data/settings/your_setting.yaml` (see starforged.yaml as template)
3. Define vocabulary substitutions, genre constraints, oracle paths
4. The setting appears in character creation automatically
