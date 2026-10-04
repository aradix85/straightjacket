# Elvira, the test player

Elvira (`tests/elvira/elvira.py`) is a headless test player that plays the real game on the models `config.yaml` names. CONTRIBUTING.md says when a release needs a run of hers; this document says how she works and how to run her.

## Running her

```bash
python tests/elvira/elvira.py --auto                     # 8 turns, random setting and style (needs API keys)
python tests/elvira/elvira.py --auto --matrix --turns 8  # every setting and style in turn
python tests/elvira/elvira.py --auto --turns 40          # a long run that reaches rarer situations
python tests/elvira/elvira.py --auto --scenario all      # every prepared rare situation in turn
python tests/elvira/elvira.py --ws --auto --turns 5      # through the WebSocket server
```

The API keys must be in the environment of the process that starts her: the game's provider key (`docs/ai.md`) and the key for her own player and judge. `tests/test_elvira_smoke.py` runs both modes against the mock provider in the normal test gate, so she cannot break unnoticed.

## Player and judge

Her own player and her judge use the provider and model under `ai` in `tests/elvira/elvira_config.yaml` (GPT-6 Luna, the judge at reasoning `low`), log as the role `elvira`, and are priced apart from the game in her report. Because the judge stays on one model while the game's clusters change, it scores every game model alike. It sees the player's action, the result, the previous narration, the player character's backstory, the active NPCs' descriptions, and the rolled move's own text for the result, so continuity is not scored as invention and an unwelcome truth on a miss is not scored as a silver lining; its scores are read together with the narrations.

## What she checks

Each run picks its setting (classic, starforged, or sundered_isles) and its play style at random unless the config or the command line names one; `--matrix` plays every combination. Every turn she checks state invariants (including database and combat-track sync), leaked mechanics, NPC spatial consistency, and streaming (time to the first sentence, streamed text equal to the final text), and the judge scores result integrity, prompt elements, NPC voice, player agency, restraint, and prose. After every save she loads the game back and compares the whole state; on game over she continues through succession. After a momentum burn and after a correction she checks that only the turn's own narration and log entry changed, that the scene count stayed, and after a burn that the turn's location and the burned result hold. Once per run (`session.inject_ai_failure_turn`) she makes the narrator unreachable for one turn and checks that the turn is rolled back to exactly the state before it; a real AI failure is rolled back the same way, reported as a problem, and play continues. A coverage tracker records which parts of the game a run touched and steers her towards what is missing.

## Scenarios

`--scenario` prepares a rare situation after character creation and reports whether the run reached it: `near_death` (health and spirit 0: game over at the crisis check, then succession), `chapter_end` (epilogue and new chapter), `momentum_burn` (a burn offered and taken), `combat` (an open fight), `clock` (a clock one segment from full), and `miss` (every stat at 1, investigating turns, no burns, so misses come often; the audit section of the report scores misses apart). The scenarios live in `tests/elvira/elvira_config.yaml` and their preparation in `tests/elvira/elvira_bot/scenarios.py`.

## Reports and folders

She captures the engine log per turn: lines with the prefixes in `logging.event_prefixes` become events (bonuses, chained moves, Pay the Price, extraction, the Director and its tools), and every warning or error becomes a problem in the report, because a failed side call degrades by design and the game would otherwise play on silently. Each run writes a JSON session log and a Markdown report to `tests/elvira/runs/`: verdict first, then problems, coverage, audit, streaming, engine events, speed, and estimated cost.

She keeps her players in tests/elvira/users by setting `STRAIGHTJACKET_USERS_DIR` before the engine loads, unless it is already set; git ignores both folders. In `--ws` mode she plays through the real server stack, which saves in its own users folder, and also probes the status, tracks, threats, and recap messages; direct mode drives the engine and is the faster way to test engine changes. To try another game model, point `STRAIGHTJACKET_CONFIG` at a copy of `config.yaml` with other clusters and give Elvira a config with its own `username`, so several runs can play side by side.
