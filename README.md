# Straightjacket

> *Forcing AI to narrate, not decide.*

AI-powered narrative solo RPG engine. You write the action. Dice determine outcomes. AI writes the world. NPCs remember you, factions move independently, stories have structure.

The AI is the narrator — constrained by mechanics, validated by the engine, never in control. Config-driven, provider-independent, screen reader accessible.

Runs on open source models. ~2 seconds per turn on Cerebras. Where open models fall short on constraint compliance, the engine compensates: hybrid rule-based + LLM validator, retry with prompt stripping, best-of selection across attempts.

---

## Quick Start

```bash
git clone https://github.com/aradix85/straightjacket.git
cd straightjacket
python run.py
```

Creates a venv, installs dependencies, downloads game data, starts the server at **http://localhost:8081**. Set your API key via environment variable (configured in `config.yaml` under `ai.api_key_env`).

---

## How It Works

You type what your character does. The engine classifies the action, rolls dice, applies mechanical consequences. An AI narrator writes the scene within those constraints. A validator checks the output. A director handles NPC reflections and story arc tracking.

Four AI agents per turn: **Brain** (parses input into mechanics), **Narrator** (writes prose), **Validator** (rule-based + LLM constraint checking, retries with prompt stripping), **Director** (NPC reflections, AIMS generation).

The AI never decides outcomes, moves resources, or controls the player character. That's the straightjacket.

Mechanics drawn from Ironsworn/Starforged (action rolls, momentum, bonds), Mythic GME 2e (fate questions, scene structure, random events, meaning tables), and Blades in the Dark (position & effect, clocks).

---

## Configuration

Five YAML files, each with a clear owner:

| File | What | Who edits it |
|---|---|---|
| `config.yaml` | Server port, AI provider, language | Players |
| `engine.yaml` | Game rules, move outcomes, damage, chaos, NPC limits, pacing | Game designers |
| `emotions.yaml` | Emotion scoring, keyword boosts, dispositions | Game designers |
| `prompts.yaml` | AI system prompts, task templates, instruction fragments | Prompt engineers |
| `strings.yaml` | UI text (English default) | Translators |

Four settings ship via [Datasworn](https://github.com/rsek/datasworn): Ironsworn Classic (dark fantasy), Starforged (sci-fi), Sundered Isles (seafaring), and Delve (dungeon-crawling expansion for Classic). Each defines vocabulary, sensory palette, genre constraints, and oracle paths in `data/settings/*.yaml`. Adding a setting means adding one YAML file and a Datasworn JSON — no Python. See [ARCHITECTURE.md](ARCHITECTURE.md) for the settings YAML format.

Default AI: GLM-4.7 via Cerebras for creative roles (brain, narrator, director, architect). Qwen3 235B Instruct for analytical roles (validator, metadata extraction, recap). GPT-OSS 120B for Elvira test bot. Also supports Anthropic (Claude) and any OpenAI-compatible API. Models configurable per role in `config.yaml`.

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full turn pipeline, module ownership table, file map, and extension guides (new providers, new settings).

All mutable game state is typed dataclasses with snapshot/restore for atomic undo. Zero hardcoded game logic — move outcomes, damage tables, disposition shifts, and NPC seed emotions all read from engine.yaml. Move definitions load from Datasworn JSON per setting. Zero hardcoded prompt text — all AI-facing text lives in prompts.yaml, Python only assembles.

The architecture implements the [Narrative RPG Engine](docs/narrative_rpg_engine_v2_4.pdf) design document: AI narrates, structured systems decide. The six functions from the design document (action resolution, fiction generation, timing, relationships, agency, world state) map to engine modules. The constraint enforcement strategy (engine-dictated consequences, vocabulary control, narrative direction derived from game state) follows the document's recommendations.

---

## Tests

Two complementary layers:

**Unit/integration tests** (`python -m pytest tests/ -v`, ~692 tests, no API key needed): mock providers with canned responses test engine logic, NPC processing, serialization, correction flow, prompt assembly, WebSocket handlers, database sync/queries, tool registry/dispatch. Every commit must pass.

**[Elvira](tests/elvira/)** (`python tests/elvira/elvira.py --auto --turns 5`, needs API key): headless AI-driven test player that plays the game with real model output. Checks state invariants after every turn, validates narration quality (leaked mechanics, NPC spatial consistency), stress-tests the correction pipeline, and logs diagnostics to JSON. Two modes: direct (engine only) and WebSocket (full server stack). See [CONTRIBUTING.md](CONTRIBUTING.md) for when to use which.

**Tool calling probe** (`python tests/tool_calling_probe.py`, needs API key): evaluates tool calling reliability across models. Tests Brain and Director tool patterns, reports pass/fail per case and comparative verdict. Use `--model slug` for single model or default for Qwen + GLM comparison.

---

## Accessibility

Screen reader accessible: semantic HTML, ARIA live regions for automatic narration readout, heading navigation per scene, native form controls. Text-in, text-out by design. Built by a blind developer — accessibility is structural, not cosmetic.

---

## Cost

~$0.13 per 10-turn session with GLM + Qwen multi-model setup via Cerebras (~6s/turn). ~$0.48 with GLM-only.

---

## Origins

Straightjacket is the implementation of the [Narrative RPG Engine](docs/narrative_rpg_engine_v2_4.pdf) design document ([also on itch.io](https://blindgamer85.itch.io/narrative-rpg-engine-accessible-solo-tabletop-with-ai-as-narrator-and-systems-u)). The core argument: don't make AI smarter at telling stories — strip it down to prose and let structured systems handle everything else.

The initial prototype was built on top of [EdgeTales](https://github.com/edgetales/edgetales) by Lars, which was itself based on the same design document. The current codebase is a ground-up reimplementation — different architecture, different type system, different AI pipeline — but EdgeTales provided the starting point and several foundational ideas. Credit where it's due.

---

## License

AGPL-3.0. Game data from [Datasworn](https://github.com/rsek/datasworn) (CC-BY-4.0, some CC-BY-NC-SA-4.0). Mechanics: Ironsworn/Starforged (Shawn Tomkin, CC-BY-4.0), Mythic GME (Tana Pigeon), Blades in the Dark (John Harper).
