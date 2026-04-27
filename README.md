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

You type what your character does. The engine classifies the action, rolls dice, applies mechanical consequences. An AI narrator writes the scene within those constraints. The AI never decides outcomes, moves resources, or controls the player character. That's the straightjacket.

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

The engine code is AGPL-3.0.

Game data ships under its own licenses, separate from the engine code:

Datasworn rulesets in `data/`. The Ironsworn, Ironsworn: Delve, and Ironsworn: Starforged content (`classic.json`, `delve.json`, `starforged.json`) is by Shawn Tomkin, used under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — the subset Tomkin Press has placed under the commercial-permissive license. The Sundered Isles content (`sundered_isles.json`) is by Shawn Tomkin, used under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) — non-commercial, share-alike. Source: [Datasworn](https://github.com/rsek/datasworn) by rsek. Tomkin Press licensing details: [tomkinpress.com/pages/licensing](https://tomkinpress.com/pages/licensing).

Mythic and Crafter content in `data/`. The Mythic GME 2e content (`mythic_gme_2e.json`) and Adventure Crafter content (`adventure_crafter.json`) are based on works by Tana Pigeon, published by Word Mill Games, and licensed for use under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). See [wordmillgames.com/license.html](https://www.wordmillgames.com/license.html) for the full terms — the license covers text only, not art or trade dress, and prohibits commercial use.

Mechanics also referenced in the engine, not redistributed as data: Blades in the Dark by John Harper (position & effect, clocks); the AIMS framework by Gnome Stew (Agenda, Instinct, Moves, Secrets). See [ORIGINS.md](ORIGINS.md) for full credits.

Note on the engine license. The AGPL-3.0 license on the engine code does not override the non-commercial clauses on `sundered_isles.json`, `mythic_gme_2e.json`, and `adventure_crafter.json`. Anyone redistributing this repository commercially must remove or replace those files first.
