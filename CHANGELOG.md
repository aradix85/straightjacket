# Changelog

Straightjacket — AI-powered narrative solo RPG engine.
Originally forked from [EdgeTales](https://github.com/edgetales/edgetales). See [ORIGINS.md](ORIGINS.md).

Entries up to 2026.09.26.0 were shortened to their essentials in 2026.09.26.1. The full original text, with every measurement and quality-gate figure, is in git history (commit 1cef542 and earlier).

## Versioning

Calendar versioning: `YYYY.MM.DD.N`, where `N` is a zero-based counter for releases on the same day. The first CalVer release is 2026.04.25.0; earlier `0.x.y` releases keep their numbers.

## [2026.09.26.1] — 2026-09-26

The project is the game plus Elvira again, at the user's request: the model-comparison harness is removed and this CHANGELOG is shortened.

Removed: `tests/modeltest/` (the twenty-scene narrator harness with its judges, scenes, and GLM baseline), `tests/test_modeltest.py`, and the `.gitignore` line for the harness runs. Elvira's runner lost an unused constant that pointed at the harness configuration. `tests/test_brain_move_availability.py` borrowed the scripted Brain fields from the harness and now holds them itself. Elvira, with her per-turn narration audit, is the measurement for prompt changes.

Coverage. The harness test was the only test that reached thirteen lines of engine code, which left coverage at 89.99 to 90.01 percent against the floor of 90. The new `tests/test_prompt_npc_and_clock_blocks.py` tests two of those paths directly: a filled clock reaches the narrator prompt as an escaped `<clock_filled>` tag, and an activated NPC carries its most recent memory, or its reflection as insight, into the prompt.

CHANGELOG. Every version keeps its header and a short summary of what changed and why; measurement tables, test counts, and quality-gate lines of earlier entries are left to git history.

ARCHITECTURE.md no longer describes the harness; the roadmap measures prompt tuning with Elvira and drops the item asking for a CHANGELOG summary.

Quality gate: 1485 tests green, twenty-nine project-rule scans clean, coverage 90.08%, ruff check and ruff format clean on 206 files, mypy --strict clean on 109 source files. No engine code, prompt, or configuration changed, so no Elvira run. Save format unchanged.

## [2026.09.26.0] — 2026-09-26

Every role on GPT-6 Luna again: reasoning effort `none`, the creative cluster `low`, and the Director at `none` because Chat Completions allows tool calls only there. Luna back in the Elvira and harness price tables. An eight-turn Elvira session found no problems and cost about one cent.

## [2026.09.25.6] — 2026-09-25

Every role on Fireworks' standard tier of GLM 5.3, a third cheaper than Fast; in play the first sentence came after about 11 seconds and a turn took about 28.

## [2026.09.25.5] — 2026-09-25

Measured, not adopted: GLM 5.3's standard tier narrated within the noise of Fast but made the player wait far longer. The Director was found to be half of a session's cost.

## [2026.09.25.4] — 2026-09-25

The narrator system prompt ordered for prompt caching (fixed rules first, per-turn character state last), which also measured better; cached input shown in the token log; a missing `recovery_MISS` memory emotion that ended turns added.

## [2026.09.25.3] — 2026-09-25

The narrator's miss rule describes what happens instead of what to avoid; GPT-6 Sol judges beside GLM in the harness; the Brain always names a new track; a correction to a dialog turn no longer tries to roll `dialog`.

## [2026.09.25.2] — 2026-09-25

Outright errors in the prompt files fixed: the correction analyser's role, cut off by the comment sweep of 2026.04.26.2; a literal unicode escape as the quote example; stealth routed to shadow as both rulebooks say; stale references to removed tools, fields, and the retry loop.

## [2026.09.25.1] — 2026-09-25

Player and save names that Windows cannot store are refused with `InvalidNameError` and a clear message; README and ARCHITECTURE say what the AI still decides.

## [2026.09.25.0] — 2026-09-25

The setting-yaml loader refuses unknown keys; the coverage floor rises to 90; the working documents are brought in line with the code. Releases 2026.09.24.52 to .62 were made on 25 September but kept the 24 September date.

## [2026.09.24.62] — 2026-09-25

Every cluster names its own provider, model, and extra body again; the shared `ai.model` of .61 is gone.

## [2026.09.24.61] — 2026-09-25

Every role on GLM 5.3 Fast through Fireworks, Elvira's player and judge following the Brain; unused tooling removed (Elvira's narrator and model swaps, the harness contestants, the Luna and Claude price tables).

## [2026.09.24.60] — 2026-09-25

NPCs change location only when the narration names them; the Brain prompt explains every field of its schema, enforced by a test.

## [2026.09.24.59] — 2026-09-25

The Director's output schema offers only the NPCs chosen for reflection. Findings on GLM 5.3's always-on thinking and on Gemini 3.8 Flash through Google's own API.

## [2026.09.24.58] — 2026-09-25

Whole Elvira sessions on one model per candidate: GPT-6 Luna 7.7 seconds per turn and about $0.01 per session, GLM 5.3 Fast 11.9 seconds and $0.27, Gemini 3.8 Flash 7.5 seconds and $0.09. Streamed sentences decode literal unicode escapes; the Brain schema limits `bonus_id`, `target_npc`, and `target_track` to what the prompt offers.

## [2026.09.24.57] — 2026-09-25

The harness rubric values atmosphere and sensible invention and uses a two-family panel, because a judge favours its own family. Fifteen narrators compared: Gemini 3.8 Flash and GLM 5.3 Fast ahead, GPT-6 Luna with the lowest atmosphere score. Elvira runs on one model for everything.

## [2026.09.24.56] — 2026-09-25

A ten-model narrator comparison with reasoning off or as low as allowed, judged by GPT-6 Sol: Gemini 3.8 Flash, GPT-6 Luna, GPT-6 Sol, and GLM 5.3 Fast within a few tenths of each other, Luna by far the cheapest and fastest.

## [2026.09.24.55] — 2026-09-25

Three engine bugs fixed: a bond keyed scene spawned for a character who is not an NPC, the Brain able to play a move the situation does not allow, and unknown Director tool arguments failing a round.

## [2026.09.24.54] — 2026-09-25

Results of the deeper narrator test: Kimi K3 and Gemini 3.8 Flash narrated single scenes better than GPT-6 Luna, GLM 5.3 held up best over whole sessions, and all were slower and costlier than Luna.

## [2026.09.24.53] — 2026-09-25

A deeper narrator test: ten harder scenes, confidence intervals, paired comparison, and Elvira able to narrate with another model.

## [2026.09.24.52] — 2026-09-25

Two more narrator candidates measured (Muse Spark 1.3 and Qwen3.8 Flash), both below GPT-6 Luna.

## [2026.09.24.51] — 2026-09-24

Elvira plays prepared rare situations (`--scenario`: near death, chapter end, momentum burn, combat, a filling clock); the schema-strictness check became a test.

## [2026.09.24.50] — 2026-09-24

The model-comparison harness moved into the repository as `tests/modeltest/`, rebuilt on the engine's adapters, at the user's request.

## [2026.09.24.49] — 2026-09-24

Elvira varies setting and play style per run, judges with a model from another family, and survives AI failures, with one injected narrator outage per run that must roll back exactly.

## [2026.09.24.48] — 2026-09-24

Elvira's run reports leave the repository; `tests/elvira/runs/` is ignored by git.

## [2026.09.24.47] — 2026-09-24

Four decisions by the user: an AI failure pauses the turn and restores the snapshot, as the design document asks; loading returns exactly what was saved; step 9 returns `GeneratedEntity` or `ResolvedFact`; the Yaml content boundary covers setting yaml.

## [2026.09.24.46] — 2026-09-24

Documentation only: step 13b's move counts recounted; narrator-prompt issues recorded for a measured round.

## [2026.09.24.45] — 2026-09-24

Audit round against the project rules: strict loading, where an unknown or missing field raises and an old save is reported to the player as incompatible; typed config for Pay the Price and roll bonuses. The save format breaks.

## [2026.09.24.44] — 2026-09-24

The roadmap's Current state opens with priorities, working agreements, and how to run Elvira.

## [2026.09.24.43] — 2026-09-24

Documentation pruned and brought in line with the code.

## [2026.09.24.42] — 2026-09-24

Elvira reports every engine warning and error as a problem. The first such run found every Director call failing, because GPT-6 Luna refuses function tools with a reasoning effort in Chat Completions; the Director got its own cluster at reasoning effort `none`.

## [2026.09.24.41] — 2026-09-24

Roll bonuses reach real games: bare asset ids and paths, as character creation stores them, are now found.

## [2026.09.24.40] — 2026-09-24

Corrects the quality gate of .39, where mypy still reported two errors.

## [2026.09.24.39] — 2026-09-24

Corrects .38: duplicate progress-track ids are repaired too, and a vow and its thread stay linked.

## [2026.09.24.38] — 2026-09-24

A vow sworn twice no longer breaks the save.

## [2026.09.24.37] — 2026-09-24

Elvira records per turn what the engine did: bonuses, chained moves, Pay the Price, extraction, the Director and its tools.

## [2026.09.24.36] — 2026-09-24

Every role on GPT-6 Luna, the narrator included.

## [2026.09.24.35] — 2026-09-24

Elvira's judge gets its own token limit and reasoning effort `low`, after GPT-6 Luna's default reasoning used up the budget and left no verdict.

## [2026.09.24.34] — 2026-09-24

Classic Ironsworn marks its own lasting harm (maimed, corrupted).

## [2026.09.24.33] — 2026-09-24

Assets and connections give their roll bonuses: enabled abilities are tracked, the Brain names a bonus by id, and the engine takes the add from the rule text.

## [2026.09.24.32] — 2026-09-24

Every "with a match" clause is modelled, including oracle moves as chained moves and a connection's rank raise.

## [2026.09.24.31] — 2026-09-24

Moves that say "make another move" roll it in the same turn.

## [2026.09.24.30] — 2026-09-24

Outcomes on a match follow Starforged.

## [2026.09.24.29] — 2026-09-24

Pay the Price rolls the setting's official Datasworn table and applies its costs.

## [2026.09.24.28] — 2026-09-24

Turning points follow the Adventure Crafter: five slots, at most three None.

## [2026.09.24.27] — 2026-09-24

The Adventure Crafter's tables checked and pinned by tests.

## [2026.09.24.26] — 2026-09-24

Rules conformance for Mythic's lists and meaning tables, the Adventure Crafter's theme priority, and Blades clock sizes of 4, 6, or 8.

## [2026.09.24.25] — 2026-09-24

Legacy tracks, experience, and connections follow Starforged.

## [2026.09.24.24] — 2026-09-24

Move outcomes can differ per setting; Endure Harm and Endure Stress follow each rulebook.

## [2026.09.24.23] — 2026-09-24

"Add +1 on your next move" is banked and added to the next action roll.

## [2026.09.24.22] — 2026-09-24

Rules conformance, second pass: momentum per move outcome compared automatically with the Datasworn texts, Mythic checked, and the list of deliberate divergences recorded in ARCHITECTURE.md.

## [2026.09.24.21] — 2026-09-24

Negative momentum cancels a matching action die, as the rules say; Elvira counts the Director's tokens and has a calibrated judge.

## [2026.09.24.20] — 2026-09-24

Fix: the metadata and opening-setup extractions could not be routed since .9 and failed silently; a project-rule scan now requires every AI call to carry its own role name.

## [2026.09.24.19] — 2026-09-24

Narrator on Claude Opus 5.5, every other role on GPT-6 Luna; blueprint voicing asks for and checks the required counts.

## [2026.09.24.18] — 2026-09-24

Every role except the narrator on Claude Haiku 4.5.

## [2026.09.24.17] — 2026-09-24

The action roll follows Ironsworn: one d6 plus the stat, not two.

## [2026.09.24.16] — 2026-09-24

Elvira tests far more on her own (streaming checks, blind audit, save round trip, succession, coverage, report); she found broken dialog markup and a Director tool without a useful error.

## [2026.09.24.15] — 2026-09-24

Elvira runs again, with a smoke test in the normal gate.

## [2026.09.24.14] — 2026-09-24

Both SDKs used as intended: one retry layer honouring Retry-After, timeouts, refusals, and `max_completion_tokens` for OpenAI's own models.

## [2026.09.24.13] — 2026-09-24

Narrator on Claude Opus 5.5 at effort low.

## [2026.09.24.12] — 2026-09-24

Sentence-level narration streaming, so the screen reader starts after the first sentence.

## [2026.09.24.11] — 2026-09-24

All roles on Claude; the Anthropic adapter fixed for current Claude models.

## [2026.09.24.10] — 2026-09-24

The result tag in every action-turn narrator prompt was malformed XML and is now closed correctly; a test parses the engine-built scene as XML.

## [2026.09.24.9] — 2026-09-24

Providers can be mixed per role, and startup checks that every configured model still exists.

## [2026.09.24.8] — 2026-09-24

Dependencies brought to their current major versions.

## [2026.09.24.7] — 2026-09-24

Documentation only: step 9's fact-resolution trigger decided; the Brain flags undetermined facts and the engine resolves them through fate.

## [2026.09.24.6] — 2026-09-24

Rules and robustness fixes found by comparing with EdgeTales 0.9.67–0.9.96: NPC agency on dialog turns, Director reflections checked against the engine's selection, compel without bond progress, momentum reset floored at 0.

## [2026.09.24.5] — 2026-09-24

mypy runs in strict mode.

## [2026.09.24.4] — 2026-09-24

Import layers become a project rule; the track lifecycle moves to `mechanics/tracks.py`.

## [2026.09.24.3] — 2026-09-24

Five more ruff rule families enabled.

## [2026.09.24.2] — 2026-09-24

Documentation drift and the provider adapters get tests, and coverage gets a floor.

## [2026.09.24.1] — 2026-09-24

Project-rule scans hardened and three added.

## [2026.09.24.0] — 2026-09-24

Documentation re-sync after a four-month pause; `.gitattributes` keeps the design-document PDF binary.

## [2026.05.15.0] — 2026-05-15

AUDIT.md added and the roadmap committed.

## [2026.05.14.0] — 2026-05-14

Clock expansion: fill consequences, clock creation from random events and Adventure Crafter plot points, and a clock owner refactor. The save format breaks.

## [2026.05.11.0] — 2026-05-11

Threat creation from random events and Adventure Crafter plot points, with Datasworn cascade rolls for naming. The save format breaks.

## [2026.05.08.0] — 2026-05-08

CONTRIBUTING.md folded into ARCHITECTURE.md.

## [2026.05.06.3] — 2026-05-06

Step 7c: keyed-scene spawners from the Adventure Crafter, random events, and clocks, with a pattern grammar. The save format breaks.

## [2026.05.06.2] — 2026-05-06

Step 7b: the Adventure Crafter's character-crafting tables as pure helpers.

## [2026.05.06.1] — 2026-05-06

Step 8: the architect module split into `ai/recap.py` and `ai/chapter_summary.py`.

## [2026.05.06.0] — 2026-05-06

Step 7a: the AI architect replaced by an Adventure Crafter blueprint plus a voicing call; the Yaml content boundary recorded as a project rule.

## [2026.04.29.0] — 2026-04-29

Step 6b: Adventure Crafter turning points and supporting tables, with a shared characters list and a plotlines list.

## [2026.04.28.5] — 2026-04-28

Step 6: AI data supply audited at fourteen call sites; hardcoded fallbacks and dead schema fields removed.

## [2026.04.28.4] — 2026-04-28

The player types actions, not questions: the half fate flow of .2 reverted and "Engine-resolved fiction" recorded.

## [2026.04.28.3] — 2026-04-28

33 unimplemented Datasworn moves removed from the move categories; missing CHANGELOG headers restored.

## [2026.04.28.2] — 2026-04-28

Dead code removed, and a half fate flow added that nothing triggered.

## [2026.04.28.1] — 2026-04-28

Documentation only: the `engine.yaml` shorthand replaced by the per-subsystem files.

## [2026.04.28.0] — 2026-04-28

Residue of 2026.04.27.11 actually removed, so the CHANGELOG matches the tree again.

## [2026.04.27.11] — 2026-04-27

Cleanup pass; scans for format, orphan symbols, and orphan yaml keys added.

## [2026.04.27.10] — 2026-04-27

Strict-rule cleanup passes; `AICallSpec` replaces eleven optional arguments; Elvira's drift check and the genre constraints removed.

## [2026.04.27.9] — 2026-04-27

Architect and chapter validators removed.

## [2026.04.27.8] — 2026-04-27

Narration validator removed: judging writing rules with an AI proved unreliable, and its retry loop flattened the prose.

## [2026.04.27.7] — 2026-04-27

Four more strict-rule checks in the project-rule test.

## [2026.04.27.6] — 2026-04-27

Result-integrity events for the validator, narrator tuning, and the model-family resolution layer removed.

## [2026.04.27.5] — 2026-04-27

Elvira batch output no longer overwrites itself.

## [2026.04.27.4] — 2026-04-27

Classic truths reach the narrator; literal unicode escapes are decoded; WRONG examples removed from the narrator prompt.

## [2026.04.27.3] — 2026-04-27

`world_shaping` gets an outcome; validator false positives on strong hits fixed.

## [2026.04.27.1] — 2026-04-27

Hotfix: a missing stance bucket crashed most sessions; yaml symmetry tests added.

## [2026.04.27.0] — 2026-04-27

Two engine bugs fixed and move categories expanded; validator tuning.

## [2026.04.26.6] — 2026-04-26

Elvira's character creation reads the oracle paths as a dataclass.

## [2026.04.26.5] — 2026-04-26

Elvira styles `chaosagent` and `balanced` dropped.

## [2026.04.26.4] — 2026-04-26

Model-specific prompt variants; prompt blocks fully config-driven; Elvira personas rewritten.

## [2026.04.26.3] — 2026-04-26

Test-suite maintenance: wider scope, reorganisation, coverage from 81 to 88 percent, faster runs.

## [2026.04.26.2] — 2026-04-26

Every comment and docstring removed from code and yaml; context lives in the md files.

## [2026.04.26.1] — 2026-04-26

A model-family resolution layer for prompts and pattern lists, removed again in 2026.04.27.6.

## [2026.04.26.0] — 2026-04-26

Step 5: Adventure Crafter primitives (themes, plot points, meta dispatch).

## [2026.04.25.2] — 2026-04-25

Step 4: keyed scenes, consumer side.

## [2026.04.25.1] — 2026-04-25

Step 3: continue a legacy, with inheritance rolls locked in when the predecessor is archived.

## [2026.04.25.0] — 2026-04-25

First CalVer release. Step 2: a chapter-summary contradiction validator; license statements corrected.

## [0.75.0] — 2026-04-25

No-Python-defaults sweep and typed config.

## [0.74.0] — 2026-04-25

Explicit chapter transitions: `ChapterSummary` carries a mechanical snapshot.

## [0.73.0] — 2026-04-24

File splits (turn, prompt builders, move outcome) and a config-driven audit.

## [0.72.0] — 2026-04-24

Complexity refactor and a complexity-ceiling project rule.

## [0.71.0] — 2026-04-20

Third dead-code pass.

## [0.70.0] — 2026-04-20

Second dead-code pass; duplicate provider code extracted.

## [0.69.0] — 2026-04-20

Dead-code sweep; shared yaml-directory merge.

## [0.68.0] — 2026-04-20

All four project-rule debt checks pass.

## [0.67.0] — 2026-04-20

The correction module becomes a package and the engine config is split.

## [0.66.0] — 2026-04-20

Elvira gains NPC-database and combat-track invariants.

## [0.65.0] — 2026-04-20

The project-rule test with ten AST and regex scans.

## [0.64.0] — 2026-04-20

Full sweep of the 0.63 audit: strings to config, silent error suppression removed, Pay the Price wired up.

## [0.63.0] — 2026-04-19

The secret-stripping regex had drifted from its yaml label and is now structural.

## [0.62.0] — 2026-04-19

Domain enums moved to yaml; schema builders made lazy.

## [0.61.0] — 2026-04-19

Dataclass defaults that duplicated yaml removed.

## [0.60.0] — 2026-04-19

Every yaml store split into a directory of files.

## [0.59.0] — 2026-04-19

The five stat fields replaced by one stats mapping.

## [0.58.0] — 2026-04-19

AI-facing English strings moved to yaml.

## [0.57.1] — 2026-04-18

Test suite sixteen times faster through session-scoped fixtures.

## [0.57.0] — 2026-04-18

Move availability rules moved to yaml.

## [0.55.0] — 2026-04-18

Data tables moved from Python to yaml; silent fallbacks raise.

## [0.54.0] — 2026-04-18

Setting discovery and inheritance through yaml.

## [0.53.0] — 2026-04-18

Strict config access; tuning numbers moved to yaml.

## [0.52.2] — 2026-04-17

Config-driven cleanup, second pass.

## [0.52.1] — 2026-04-17

AI-facing text removed from Python.

## [0.52.0] — 2026-04-17

Legacy tracks and experience.

## [0.51.0] — 2026-04-16

Codebase audit and modularization.

## [0.50.0] — 2026-04-16

Threats and menace, impacts, and oracle-rolled NPC names; typed config.

## [0.49.0] — 2026-04-14

GLM-4.7 removed: Qwen 3 narrates and GPT-OSS does the rest, at about half the cost per session.

## [0.48.1] — 2026-04-13

Codebase audit: module ownership cleanup.

## [0.48.0] — 2026-04-13

Cluster-based AI model assignment.

## [0.47.0] — 2026-04-13

Combat, expedition, and scene-challenge track lifecycle; multi-model support.

## [0.46.50] — 2026-04-12

The Brain back to single-call prompt injection; shared resolution and narration; typed config.

## [0.46.0] — 2026-04-12

Track lifecycle; connection tracks replace bond.

## [0.45.0] — 2026-04-11

Full Forge move system, data-driven consequences, and combat position.

## [0.44.0] — 2026-04-11

Mythic GME 2e: fate system, scene structure, random events.

## [0.43.0] — 2026-04-11

Config-driven refactor; mechanics split into a package.

## [0.42.0] — 2026-04-10

GLM-4.7 prompt tuning; config-driven prompts.

## [0.41.0] — 2026-04-10

Brain and Director tool calling; Ask the Oracle.

## [0.40.0] — 2026-04-10

Oracle roller and vocabulary control.

## [0.39.0] — 2026-04-10

Consequence sentences, NPC stance, and information gating.

## [0.38.0] — 2026-04-10

SQLite read model and tool-calling infrastructure.

## [0.37.0] — 2026-04-09

The Brain slimmed and the metadata extractor split off.

## [0.36.0] — 2026-04-08

Character creation overhaul; AI surface reduced.

## [0.35.0] — 2026-04-08

Strict typing and an Elvira batch runner.

## [0.34.0] — 2026-04-08

Code audit and minimal UI.

## [0.33.0] — 2026-04-07

Prompt rewrite for Qwen3 and a hybrid validator.

## [0.32.0] — 2026-04-06

NiceGUI replaced with Starlette and WebSocket.

## [0.31.0] — 2026-04-06

Project independence. Renamed to Straightjacket.

## [0.30.0] — 2026-04-06

NPC arc system; config-driven moves.

## [0.29.1] — 2026-04-05

Serialization tightening.

## [0.29.0] — 2026-04-05

Config-driven game logic; defensive code removed.

## [0.28.0] — 2026-04-05

ChapterSummary and CurrentAct dataclasses.

## [0.27.0] — 2026-04-05

MemoryEntry dataclass.

## [0.26.0] — 2026-04-04

Typed models for NPCs, clocks, scene log, and narration.

## [0.25.0] — 2026-04-03

NPC hardening, off-screen death detection, and the Elvira test bot.

## [0.24.0] — 2026-04-01

XML injection escaping; NPC rename via correction.

## [0.23.0] — 2026-04-01

Datasworn integration; setting packages with vocabulary control.

## [0.22.0] — 2026-03-31

Constraint validator with retry.

## [0.21.0] — 2026-03-30

GameState decomposed into typed sub-objects.

## [0.20.0] — 2026-03-30

Constraint validator; open-model prompt hardening; emotions.yaml.

## [0.19.0] — 2026-03-29

engine.yaml: damage tables, resource caps, NPC limits, chaos, pacing, narrative direction.

## [0.18.0] — 2026-03-28

strings.yaml: UI text extracted; German removed from code.

## [0.17.0] — 2026-03-28

Upstream UI sync.

## [0.16.0] — 2026-03-28

Upstream sync v0.9.66. Revelation verification and fired-clock tracking.

## [0.15.0] — 2026-03-23

AI call audit; the metadata extractor receives mechanical ground truth.

## [0.14.0] — 2026-03-22

KISS cleanup; voice I/O removed.

## [0.13.0] — 2026-03-22

Upstream sync v0.9.61. GLM 4.7 as default.

## [0.12.0] — Provider tuning, multi-model testing.

## [0.11.0] — YAML configuration, multi-instance support.

## [0.10.0] — Modular refactor from upstream v0.9.44. Monolithic engine.py → packages.
