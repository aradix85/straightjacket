# Straightjacket

> *Forcing AI to narrate, not decide.*

AI-powered narrative solo RPG engine. You write the action. Dice determine outcomes. AI writes the world. NPCs remember you, factions move independently, stories have structure.

The AI is the narrator — constrained by mechanics, validated by the engine, never in control. Config-driven, provider-independent, screen reader accessible.

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

You type what your character does. The engine classifies the action, rolls dice, applies mechanical consequences. An AI narrator writes the scene within those constraints. A validator checks the output. The AI never decides outcomes, moves resources, or controls the player character. That's the straightjacket.

Mechanics drawn from Ironsworn/Starforged (action rolls, momentum, bonds), Mythic GME 2e (fate questions, scene structure, random events), and Blades in the Dark (position & effect, clocks).

---

## Accessibility

Screen reader accessible: semantic HTML, ARIA live regions for automatic narration readout, heading navigation per scene, native form controls. Text-in, text-out by design. Built by a blind developer — accessibility is structural, not cosmetic.

---

## Further reading

- [ARCHITECTURE.md](ARCHITECTURE.md) — turn pipeline, module layout, design decisions, configuration, extension guides
- [CONTRIBUTING.md](CONTRIBUTING.md) — code standards, test layers, how to run them
- [ORIGINS.md](ORIGINS.md) — project history, fork from EdgeTales, credits
- [SECURITY.md](SECURITY.md) — API key handling, input sanitization, session model
- [Narrative RPG Engine design document](docs/narrative_rpg_engine_v2_4.pdf) — the design this implements

---

## License

AGPL-3.0. Game data from [Datasworn](https://github.com/rsek/datasworn) (CC BY-NC-SA 4.0). Mechanics: Ironsworn/Starforged (Shawn Tomkin, CC BY-NC-SA 4.0), Mythic GME 2e (Tana Pigeon, CC BY-NC 4.0), Blades in the Dark (John Harper).
