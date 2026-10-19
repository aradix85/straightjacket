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

The API keys must be in the environment of the process that starts her: the game's provider key (`docs/ai.md`) and the key of the provider her own player and judge use. `tests/test_elvira_smoke.py` runs both modes against the mock provider in the normal test gate, so she cannot break unnoticed.

## Player and judge

Her own player and her judge use the provider and model under `ai` in `tests/elvira/elvira_config.yaml` (Claude Haiku 5.5, the player without thinking and the judge at effort `low`), log as the role `elvira`, and are priced apart from the game in her report. Because the judge stays on one model while the game's clusters change, it scores every game model alike. A judge tends to favour its own model family, and this one is a Claude model judging Claude narration, so its scores are compared only with runs it scored itself. It sees the player's action, the result, the previous narration, the player character's backstory, the descriptions of the NPCs the engine counts as in the scene (those with a memory of it), and the rolled move's own text for the result, so continuity is not scored as invention and an unwelcome truth on a miss is not scored as a silver lining; its scores are read together with the narrations.

## What she checks

Each run picks its setting (classic, starforged, or sundered_isles) and its play style at random unless the config or the command line names one; `--matrix` plays every combination. Every turn she checks state invariants (including combat-track sync), leaked mechanics, NPC spatial consistency, and streaming (time to the first sentence, streamed text equal to the final text), and the judge scores result integrity, prompt elements, NPC voice, player agency, restraint, and prose. After every save she loads the game back and compares the whole state; on game over she continues through succession. After a momentum burn and after a correction she checks that only the turn's own narration and log entry changed, that the scene count stayed, and after a burn that the turn's location and the burned result hold. Once per run (`session.inject_ai_failure_turn`) she makes the narrator unreachable for one turn and checks that the turn is rolled back to exactly the state before it; a real AI failure is rolled back the same way, reported as a problem, and play continues. A coverage tracker records which parts of the game a run touched and steers her towards what is missing.

## Scenarios

`--scenario` prepares a rare situation after character creation, plays in direct mode only, and reports for each of its aims whether the run reached it; an aim it missed is a problem. A scenario can fix the results of its first turns (`results`): while such a turn plays, every action and progress roll in it, follow-up and chained moves included, comes out as named, from dice drawn among those that give it, without a match unless no other dice give it (`tests/elvira/elvira_bot/fixed_results.py`); the engine has no switch for this, since Elvira replaces the scoring of `ruleset/rolls.py` for the turn. A scenario that dice cannot bring to its moment starts at it. The scenarios: `near_death` (health, spirit, and supply 0 and every roll a miss, so harm and stress go through Endure Harm and Endure Stress and mark impacts; the coverage counts follow-up moves and impacts marked), `succession` (the game over of the first character, so the successor's creation and opening play), `chapter_end` (epilogue and new chapter), `momentum_burn` (momentum at its max and misses, so a burn is offered and taken), `combat` (an open fight), `clock` (a clock one segment from full, and misses that tick it), `miss` (investigating turns that miss, no burns; the audit section of the report scores misses apart), and `complication` (investigating turns that are weak hits, so Gather Information starts complication clocks; the coverage counts them and the ones headed off). The rolls on a move's own tables, such as the dying result of Endure Harm, stay random, so `near_death` aims at impacts, not at Face Death. The scenarios live in `tests/elvira/elvira_config.yaml` and their preparation in `tests/elvira/elvira_bot/scenarios.py`.

## Reports and folders

She captures the engine log per turn: lines with the prefixes in `logging.event_prefixes` become events (bonuses, chained moves, Pay the Price, extraction, act transitions and story completion, the Director and its tools), and every warning or error becomes a problem in the report, because a failed side call degrades by design and the game would otherwise play on silently. Each run writes a JSON session log and a Markdown report to `tests/elvira/runs/`: verdict first, then problems, coverage, audit, streaming, engine events, speed, and estimated cost. The cost comes from the token use of every engine call, the opening and each chapter start included, which a meter around the provider in `tests/elvira/elvira_bot/tokens.py` counts; in `--ws` mode the meter stands in for the server's provider.

She keeps her players in tests/elvira/users by setting `STRAIGHTJACKET_USERS_DIR` before the engine loads, unless it is already set; git ignores both folders. In `--ws` mode she plays through the real server stack, which saves in its own users folder, and also probes the status, tracks, threats, and recap messages; direct mode drives the engine and is the faster way to test engine changes. To try another game model or narration language, point `STRAIGHTJACKET_CONFIG` at a copy of `config.yaml` with other clusters or another `language` and give Elvira a config with its own `username`, so several runs can play side by side.
