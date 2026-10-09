# Changelog

Straightjacket — AI-powered narrative solo RPG engine. See [ORIGINS.md](ORIGINS.md) for where it comes from.

This log starts at 2026.09.24.0, the restart after a four-month pause. Earlier releases, back to the fork from EdgeTales, and the full text of entries that were later shortened, are in git history: the file as of commit d2f8dfe holds every entry.

## Versioning

Calendar versioning: `YYYY.MM.DD.N`, where `N` is a zero-based counter for releases on the same day.

## [2026.10.09.0] — 2026-10-09

A critical read of every md file against the code, and the fixes it called for. Act transitions no longer depend on the Director: the check moved from `director.py` to `story_state.py` → `check_act_transition` and runs in every turn's scene-end bookkeeping, so an act ends at the last scene of its range, where before it ended one scene earlier only when a Director call happened to run and succeed at that scene. The WebSocket origin check refused the LAN play SECURITY.md describes, and IPv6 loopback, since `[::1]` never matched a parsed host; it now also accepts a page served from the same IP address and port, and still refuses other sites and host names that are not loopback. Player and save names with a path separator or a leading dot are refused instead of stripped, since stripping let two names share one folder. The import-layer scan now splits the engine core into its base and the rest, which `datasworn`, `db`, `npc`, `mechanics`, and `tools` may not import. Dead config went (`engine/damage.yaml` apart from the miss ticks, now `clocks.miss_ticks_by_position`; creation's `starting_asset_categories`; `strings/move.yaml`; `unknown_transition_trigger`), and `run.py` and `data/data.py` lost their comments and docstrings and joined the comment scan (roadmap 9h, two substeps closed).

Documentation: CONTRIBUTING states the strict reading the user chose, no default on any dataclass field apart from the three exceptions, and roadmap 9h.4 counts what is left (about two hundred defaults in 43 classes). ARCHITECTURE lists the correction analysis among the AI's decisions and describes the import layers as the scan now enforces them. The register gains three entries, checked against the Datasworn texts: threats advance by an engine rule instead of Delve's Advance a Threat, a full menace track forsakes the vow at a fixed spirit cost, and the ordinary moves mark scene-challenge progress; step 9j gains 9j.6. SECURITY describes the origin check, the `debug_state` message, and what escaping does not stop. Smaller corrections in `docs/ai.md`, `docs/settings.md`, `docs/elvira.md`, README, and the roadmap.

Elvira, twelve turns in Starforged as explorer: the act ended at scene 7, the last of its range; no engine warnings; streaming complete and identical on all ten streamed turns; three narration findings of kinds step 9f already covers (an unprompted transmission, player-character overreach, a miss that still gave answers); about 30 cents.

Quality gate: 1580 tests green, project-rule scans clean, coverage 90.91%, ruff and mypy --strict clean. Save format unchanged.

## [2026.10.04.6] — 2026-10-04

Documentation only. The roadmap no longer notes the MiMo evaluation: the user is not changing models now and will take it up again later if needed.

Quality gate: 1557 tests green, project-rule scans clean (documentation drift included). No code, prompt, or configuration changed.

## [2026.10.04.5] — 2026-10-04

Documentation only. The roadmap's notes for sessions with the user say where the measuring setup for prompt tuning lives (outside the repository, with a README on capturing situations, measuring a variant, and reading blind) and that its captured situations predate the player-agency line of 2026.10.04.4. They also note that the evaluation of MiMo-V2.6-Pro at Prima Labs waits for Prima Labs' answer about its rate limit, with the report beside the measuring setup.

Quality gate: 1557 tests green, project-rule scans clean (documentation drift included). No code, prompt, or configuration changed.

## [2026.10.04.4] — 2026-10-04

Step 9f, substeps 1 and 2. The narrator's action and dialog tasks end with a player-agency line in the system prompt's own wording; at the end of the prompt it catches what the rule at the top of the system prompt misses. Measured on GLM 5.3 over fourteen situations captured from sessions (misses with and without a match, weak and strong hits, an NPC's secrets, near death, two openings, two dialogs without a roll), three runs per situation and two runs per variant, each narration audited against its full prompt by GPT-6 Luna: player-character overreach fell from 49 findings on average to 30 and the audit total from 158 to 131, while the unchanged prompt's two runs differed by 12, and no other kind rose beyond its spread. A length line of 150 to 200 words raised narrations within budget from 26 of 42 to 36, but together with the agency line it left weak hits without their cost more often, so it is not adopted; a sentence on the result inside the agency line did not help either. Openings keep their own task, since an opening has no player words. A blind reading found the two prompts level overall, the agency line winning on the player character and losing on some weak-hit costs. Step 9f gains three substeps from the measurement (openings that slip into the third person, an evasive NPC telling the player character's past, weak hits without their cost), and its method now reads each blind pair twice with the positions swapped, after one reader's preferences drifted toward one position.

Quality gate: 1557 tests green, project-rule scans clean, coverage 90.79%. Elvira, eight turns in Starforged on the new prompt: no engine warnings, player agency 4.5 of 5, streaming complete on all six turns, and two narration findings of known kinds (a miss that still gave answers, an NPC that deflected on a strong-hit Compel).

## [2026.10.04.3] — 2026-10-04

Documentation only. Step 9f, prompt tuning, becomes NEXT STEP ahead of 9d at the user's choice: the roadmap gave no reason for the old order, and the narrator's core rules (player agency, result integrity, length) do not depend on the generators. Step 9f gets substeps, a definition of done, and reference patterns, and describes how a prompt change is measured: the same captured situations for every variant, three runs each, an audit against the prompt by a judge from another model family, and blind reading with balanced positions. The first measurements come from comparing GLM 5.3 with MiMo-V2.6-Pro at Prima Labs over nine situations: with the same prompt changes both scored alike (93 and 97 audit findings) and drew level in a blind reading (three wins each, three ties), and the two end-of-scene reminders of 9f.2 cut GLM's player-character overreach from 23 to 14 findings and brought 26 of 27 narrations within the word budget. Step 9d keeps its content as the first sketch after NEXT STEP. Step 9e gains a finding: a `<fact>` can place an NPC out of reach while the same NPC is the scene's target.

Quality gate: 1557 tests green, project-rule scans clean (documentation drift included), coverage 90.77%. No code, prompt, or configuration changed.

## [2026.10.04.2] — 2026-10-04

Documentation only. Scene challenges turned out to be configured but unreachable in play: Begin the Scene has no roll, so the available-moves filter keeps it from the Brain, no scene-challenge track ever exists, the moves that need one are never offered, and the `fill_clock` effect of their misses is computed but read by nothing. New step 9k makes them playable from the rulebook (Begin the Scene as a formal move, a tension clock, `fill_clock` applied, the engine's own progress rule for the ordinary moves removed); step 13b no longer lists Begin the Scene, `docs/mechanics.md` says scene challenges are not playable yet, and step 9h.10 asks that every move-outcome field has a reader in play.

Quality gate: 1557 tests green, project-rule scans clean (documentation drift included), coverage 90.81%. No code, prompt, or configuration changed, so no Elvira run.

## [2026.10.04.1] — 2026-10-04

Documentation only. The md files now state the current state, each fact in one file: reasons are written out instead of pointing to CHANGELOG versions, the roadmap's DONE list, duplicated process rules, and model paragraph are gone (process rules live in CONTRIBUTING.md), AUDIT's loose notes became substeps of step 9h, ai.md lost its prices and measurement history, the register in `docs/divergences.md` is the one list of where the AI still decides what a system will take over, ORIGINS keeps lineage and credits, and this log starts at 2026.09.24.0. Fixed on the way: `docs/mechanics.md` still called `generate` the single entry point, overstated `check_npc_agency`, missed the progress-mark category when adding a move, and described chapter transitions unclearly. The user decided that death comes only through Face Death, as the rulebooks have it; step 9j.5 builds it, and the register entry moves from Open to Until step 9j.

Quality gate: 1557 tests green, project-rule scans clean (documentation drift included), coverage 90.77%, ruff and mypy --strict clean. No code, prompt, or configuration changed, so no Elvira run.

## [2026.10.04.0] — 2026-10-04

The Brain chooses a track by id, and track names reach its prompt escaped, since the background vow carries the player's own text. Action moves that mark progress (Strike, Clash, Gain Ground, expeditions, journeys, delves, scene challenges) never marked it, because Datasworn gives a track category only to progress rolls; they name their category in `engine/track_moves.yaml` now. The position resolver's secured-advantage factor never fired (an old move name) and its `matched_momentum` override read fields that do not exist; fixed and removed. The design document is linked instead of copied, Elvira has `docs/elvira.md`, and position and effect are documented. Two Elvira sessions in Starforged: two known problems in the first, none in a combat scenario where Strike and Clash filled the fight's track.

Quality gate: 1557 tests green, thirty project-rule scans clean, coverage 90.76%, ruff and mypy --strict clean. Save format unchanged.

## [2026.09.29.12] — 2026-09-29

Step 9c, soft misses from the engine side. On a miss the engine withholds what the narrator used to leak: every NPC present withholds (`information_gate.miss_stance`), the target NPC's agenda, memories, and secrets stay out with fact budget 0, bystanders lose their memory hint, and the previous Director guidance and a pending revelation wait for a hit. A miss on an information move settles `useful` as no for the place; a miss with a match rolls the story-complication oracle instead of Pay the Price in Starforged and Sundered Isles, as Datasworn describes it. Elvira gained the `miss` scenario and a report line scoring misses alone; the Director's JSON failure warning shows how the answer began. Documentation fixed where step 9b had left it stale.

Measured on audited misses (result integrity of 5, overall of 10, three to five sessions each): baseline 3.0 / 5.8; the kept version 3.4 / 6.1. Dropped because they measured no better: leaving three narrator rules out on a miss (2.4 / 4.7), the move's Datasworn miss text in the prompt (2.2 / 4.3; "reveals an unwelcome truth" read as licence to reveal), and settling `occupied` as yes on an information miss (3.3 / 5.9; "someone is here" answered a search for an intruder).

Quality gate: 1550 tests green, project-rule scans clean, coverage 90.65%, ruff and mypy --strict clean.

## [2026.09.29.11] — 2026-09-29

Documentation only. The design document is now `docs/narrative_rpg_engine_v2_4.md` instead of a PDF, so a session reads it with the other md files; the text is unchanged (5,493 words in both, compared word by word), with its sections as headings and its prompt examples as code blocks. README, ORIGINS, ARCHITECTURE, and the divergence register link to it.

## [2026.09.29.10] — 2026-09-29

Documentation only. The working agreements that lived only in conversation are now in the roadmap, so a fresh session can pick up the work: short CHANGELOG entries, commit and push per finished release, Elvira sessions as part of a step, Dutch plain-prose answers for a screen-reader user, and starting a session by reading every md file. Step 10 notes the Location Crafter in case the user buys it.

## [2026.09.29.9] — 2026-09-29

Documentation only. The user asked for no priorities or open items beside the steps: the priorities list is gone, and every item on it is now a numbered step in the order of work. The soft miss becomes the next step (9c, with a miss scenario for Elvira first); then the generators (9d), the open Elvira findings (9e), the remaining prompt work (9f), fixtures through the real creation path (9g), the first principle audit (9h), revelations (9i), and the rules conformance items (9j). A new finding becomes a substep or a step in the same commit.

## [2026.09.29.8] — 2026-09-29

Step 9b, chapters as Mythic adventures. A chapter is Mythic's and the Adventure Crafter's adventure within a campaign; the EdgeTales resets are gone: health, spirit, supply, momentum, and clocks carry over, the chaos factor restarts at Mythic's 5, and a game that is over can only continue through succession. The engine writes the chapter record from its own data (conflict, vows, plotlines, threads, people, the dead, threats, the place), so the `chapter_summary` AI role is removed, and with it the AI's projections of how NPCs change between chapters and its choice of where the next chapter starts. Step 9c, the generators, is next. The save format breaks.

Checked: an Elvira `chapter_end` session in Sundered Isles reached the new chapter with its two clocks carried over and no engine warning; its two problems are soft misses (priority 3). The record it wrote listed a vow twice and used the blueprint's conflict sentence as a title; both fixed.

Quality gate: 1529 tests green, thirty project-rule scans clean, coverage 90.44%, ruff and mypy --strict clean.

## [2026.09.29.7] — 2026-09-29

Documentation only. The user made chapters the next step: new step 9b treats a chapter as Mythic's and the Adventure Crafter's adventure within a campaign and removes what came from EdgeTales (refilled health, spirit, supply, and momentum, wiped clocks, an AI-written chapter summary), with two register entries until then. The generators move to step 9c and engine-settled revelations to 9d; earlier CHANGELOG entries keep the old numbers.

## [2026.09.29.6] — 2026-09-29

Documentation only. A one-time coverage map, read and then removed, checked every part of the four Datasworn rulesets, Mythic GME 2e, the Adventure Crafter, Blades, and the design document against the code and the roadmap; everything that stood nowhere is now on the roadmap, including three new steps (10b launch oracles, 13c foe actions and plot twists from oracles, 36 setting tooling). The register gains the session moves and Mythic's rules-system parts as Permanent, and foe actions and ranks decided by the AI until step 13c. The miss experiment (priority 3) is recorded; every role stays on one model.

## [2026.09.29.5] — 2026-09-29

The user's two decisions, built from the classic move texts. Classic Ironsworn marks experience by the vow's rank when Fulfill Your Vow hits (troublesome 1 to epic 5, one rank lower on a weak hit) instead of filling Starforged's legacy tracks. Draw the Circle takes the boasts the player declares, read by the Brain: up to two on a strong hit, one on a weak hit, each +1 momentum with its cost from `engine/boasts.yaml`; its weak hit no longer grants momentum without a boast, which closes the last known momentum divergence. New register entries: a classic successor inherits no legacy boxes, and a duel opens no combat track (until step 13b).

Quality gate: 1535 tests green, thirty project-rule scans clean, coverage 90.47%, ruff and mypy --strict clean.

## [2026.09.29.4] — 2026-09-29

Documentation only. ARCHITECTURE.md records the order of preference: a tabletop system decides first, an engine rule second, the AI only writes prose and reads free text; the divergence register judges departures by it. The user decided that classic Ironsworn earns experience by its own rule (section R) and that boasts are modelled (step 13b). New sketch step 9c: the engine settles when a revelation lands, and the revelation-check AI call goes, since it validates AI output after the fact. The roadmap lists every place the AI still decides and the system that takes it over, with steps 11 and 35 sharpened to use the Adventure Crafter's character tables and to build on facts.

## [2026.09.29.3] — 2026-09-29

The opening extraction asks for the place's short name as the narration gives it, two to five words, with what happens there in `scene_context`. Before, all three openings of the day's classic sessions came back as descriptive sentences of 15 to 20 words, which then stood in `<location>`, `<prev_locations>`, and `<fact about>`; after, four openings (three Sundered Isles, one classic) gave three-word names such as "Terracoyote Crossing wayhouse". No engine warning besides one Director time-out.

Quality gate: 1526 tests green, thirty project-rule scans clean, ruff and mypy --strict clean.

## [2026.09.29.2] — 2026-09-29

Loose ends. `docs/divergences.md` becomes a register: every departure from the design document or a rulebook states why and ends with a status (Permanent, Until step N, or Open), and a new project-rule scan rejects an entry without one. New entries: the narrator still invents off-screen NPC actions (until step 12), content is narrated rather than generated (until 9b), the WRONG/RIGHT prompt examples, the pause on AI failure, Mythic under CC BY-NC; classic experience and boasts are Open. `apply_progress_and_legacy` takes the rolled track and raises instead of assuming a vow of rank dangerous. Setting yaml gains a required `playable`, so Delve is no longer skipped by name. No Elvira session; the next release's measurement runs on this code.

Quality gate: 1526 tests green, thirty project-rule scans clean, coverage 90.42%, ruff and mypy --strict clean.

## [2026.09.29.1] — 2026-09-29

A correction of a misread input replays the turn through the turn's own code (`replay_turn`) instead of a separate copy: same scene type, the facts already settled, and the dice already rolled, rescored with the corrected stat. The copy narrated a correction without a new roll as dialog, so a miss vanished, and it skipped track creation, weak-hit clock ticks, and the scene end. The correction AI no longer decides whether to reroll (`reroll_needed` and `corrected_stat` are gone), and a corrected turn can offer a momentum burn. The turn snapshot is taken after the scene test and keeps the scene type; the save format breaks.

Elvira's new checks caught at once that a restore still cut the narration history and the session log by length, which brings back the wrong entries once the history is at its cap of three; both lists are now copied whole. One Elvira session in classic, eight turns: a burn and a correction replayed, five facts resolved; one Director answer ran to the token limit (roadmap priority 2).

Quality gate: 1523 tests green, twenty-nine project-rule scans clean, coverage 90.48%, ruff and mypy --strict clean.

## [2026.09.29.0] — 2026-09-29

Step 9a, fact resolution: the Brain names the facts an action or question turns on, Mythic's fate chart settles them with odds the engine derives from `engine/fact_resolution.yaml`, and the narrator gets them as `<facts>`. A fact belongs to its place and clears on a move, a chapter start, or a succession; a hit settles a yes where the type says so. Ask the Oracle stays the move for questions: a yes/no question that a fact type covers is answered by the fact. `resolve_likelihood` is gone. The save format breaks.

Momentum burn: it overwrote the previous turn's log entries and lost the turn's move, track, and events; it now resumes from a snapshot taken after the roll and runs the turn's own path. A restore copies the story lists whole. Also fixed: an interrupt event shown twice, a corrected oracle turn losing its answer, player input unescaped in the Brain prompt.

Elvira checks what a burn or correction may change and counts resolved facts. Two sessions (classic, eight turns, and the burn scenario): facts resolved in play, burn and rollback correct, no engine warnings; they showed a hit clearing a no, now fixed.

Quality gate: 1517 tests green, twenty-nine project-rule scans clean, coverage 90.52%, ruff and mypy --strict clean.

## [2026.09.27.2] — 2026-09-27

Documentation only: the user decided the two points step 9a left open. A fact hangs on an NPC, by the id the Brain's prompt offers, or on the current location, with no free-text objects, so the engine can recognise it again. Every fact is cleared when the player moves and at a chapter start, and each fact type says in yaml whether a hit on an action that depended on it clears it. Resolved facts live in one list on the world state. Roadmap step 9a records both decisions and their rejected alternatives.

## [2026.09.27.1] — 2026-09-27

Openings: the engine owns the opening clock and the time of day, and a succession applies its opening extraction instead of discarding it.

Cause. `opening_setup_extractor` asked for a threat clock and a time of day although the engine sets both before the opening narration. At a new game `apply_world_setup` then replaced every clock with the model's, including the engine's clock named after the background vow, with a size the model chose, and overwrote the time. A chapter opening added the model's clock and took its time only from the extraction, which left the time empty for the whole chapter whenever the extraction was skipped. A succession made the extraction call and threw the answer away, so the successor's opening NPCs were never registered.

Changes. The opening extraction returns NPCs, their first memories, deceased NPCs, the location, and the scene context; its prompt, schema, fallback, and log line lose the clock and the time. Every opening (new game, chapter, succession) starts at `opening.time_of_day`; only a new game gets an opening clock, so chapters and successions get their clocks from Adventure Crafter plot points and random events like the rest of play. A succession applies its extraction, deceased NPCs included, and skips NPCs already in play. With no clock left from a model, `conform_clock_segments`, `allowed_segments`, and the parser for setup clocks are gone; the rules-conformance test now checks that the configured clock sizes are Blades sizes. The wrappers `_apply_opening_setup` and `_apply_chapter_opening_setup`, a string replace that changed nothing, and dead validator mocks in two tests are removed. Two new tests (the schema leaves clocks and time to the engine; a succession registers its opening NPCs and keeps the engine's time) fail without the change.

Roadmap. Step 9a's odds are decided by the user: each fact type names its own base odds and the game state that shifts them, the chaos factor stays out of the score because the fate chart already reads it, and the score converts to odds through `score_to_odds`.

Checked: two Elvira sessions in Sundered Isles. `near_death` (aggressor, eight turns) reached game over and succession; `chapter_end` (explorer, five turns) reached the chapter transition, and its final save holds the engine's time of day and one clock from a random event. No engine warning or error in either; the four problems are narration audits of 3 or 4 out of 10 for misses that still give a lead (roadmap priority 3). The successor in `near_death` kept an introduced NPC, so its opening extraction was not called in play; the new unit test covers that path. In `chapter_end` a returning NPC and a new NPC of almost the same name stood side by side in chapter two (roadmap priority 2). About 28 cents for both sessions before caching.

Quality gate: 1489 tests green (five fewer: the clock-size cases and the wrapper tests went with their code), twenty-nine project-rule scans clean, coverage 90.15%, ruff check and ruff format clean on 208 files, mypy --strict clean on 109 source files. Save format unchanged.

## [2026.09.27.0] — 2026-09-27

Documentation only: the working documents slimmed down and restructured along common practice, with duplicates and claims the code contradicts removed, and roadmap step 9 split so that fate comes back first.

Structure. ARCHITECTURE.md becomes a bird's-eye view (the core idea, the turn pipeline, a code map per package, state, configuration, the interface) instead of a reference for everything. CONTRIBUTING.md returns, undoing the merge of 2026.05.08.0: workflow, rules for a change, project rules, code standards, and testing, Elvira included. The details moved to `docs/`: `ai.md` (roles, models, routing, caching, failures, streaming, tool calling), `mechanics.md`, `settings.md`, and `divergences.md`. The per-file map and the module-ownership table are gone, and the rule against comments now points at the md files in the root and in `docs/`. The documentation-drift scans follow: the path and symbol scans read every md file in the root and in `docs/` except the CHANGELOG and the roadmap, and the file-map scan became a code-map scan that requires every package in the code map of ARCHITECTURE.md.

Corrected on the way: Elvira plays and judges on GPT-6 Luna, not on the game's model; the narrator is GLM 5.3, not GLM 5.3 Flash; an eight-turn session costs about 16 cents, not two to three; the Director's truncated answers were the carriage-return loop of 2026.09.26.20; the Director's ban on gothic horror no longer applies to every setting; idea E5 was done in 2026.09.24.58; step 11 no longer names Director tools that 2026.09.26.11 removed; "genre constraints", removed in 2026.04.27.10, and a narrator "validate" step are gone; AUDIT no longer says that `load_game` repairs old data.

CHANGELOG. Entries 2026.09.26.1 to .19 shortened to their essentials, as 2026.09.26.1 did for the entries before it; their full text is in commit 5baa6ed.

Roadmap. Current state holds only the open priorities, the working agreements, and notes for this machine; its rules for a change moved to CONTRIBUTING.md. Step 9 is split into 9a, fact resolution, now NEXT, and 9b, the generators; fact resolution becomes the first category of the entry point decided in 2026.09.24.47, and where a fact's odds come from is proposed and marked to confirm before building.

AUDIT. Written for local work instead of fresh chats, with a compact Status, and anchored in CONTRIBUTING.md and ARCHITECTURE.md.

Sizes: the md files together went from about 257 to 161 KB; ARCHITECTURE.md, read at the start of every session, from 89 to 11.

Quality gate: 1494 tests green, twenty-nine project-rule scans clean (the documentation-drift scans included), coverage 90.14%, ruff check and ruff format clean on 208 files, mypy --strict clean on 109 source files. No engine code, prompt, or configuration changed, so no Elvira run. Save format unchanged.

## [2026.09.26.20] — 2026-09-26

The structured answers' "runaway" was a carriage-return loop inside the JSON; the tokens are banned, the schema goes into every structured prompt, and every role runs on GLM 5.3 again.

Cause. Streaming the Brain's own request on GLM 5.3 150 times caught one failure whole: after `{"type": "action", "move": "ask_the_oracle"` the model wrote a space and then about 8,180 carriage returns (`\r`) to the 8192-token limit, with no reasoning at all. A JSON grammar allows any whitespace between tokens, so the enforced schema could not stop it, and Together strips trailing whitespace from a non-streamed answer, which is why the failures of 2026.09.26.9 to .19 looked like short broken JSON with an empty reasoning field and were called a reasoning runaway; those entries' "runaway" is this loop. Together returns reasoning text in `reasoning_content` whenever the model reasons.

Changes. GLM 5.3 and GLM 5.3 Flash share one tokenizer of 154,820 tokens, 396 of which contain a carriage return; JSON never needs one, and neither does prose. `config.yaml` bans all 396 in every cluster through `logit_bias`, written once under the YAML anchor `no_carriage_return` and referenced by the others; Together accepted the full list for both models. Together's structured-output guide says to put the schema in the prompt as well as in `response_format`, and Fireworks and OpenAI warn that a model which does not see the schema may emit whitespace until the limit. `RoutingProvider` now appends one line from `prompts/blocks.yaml` with the compact schema to the end of the last user message of every call that has a schema (to the system prompt if the last message is not plain user text), last so that nothing before it changes and every cached prefix stays intact, including the Director's, whose schema changes with the NPCs selected for reflection. Two new tests cover the placement and an unchanged call without a schema. With structured calls safe, every cluster runs on `zai-org/GLM-5.3`.

Measured: before the changes 3 of 220 structured GLM 5.3 calls (160 Brain, 60 metadata) broke off at the limit; after them 0 of 360 (300 Brain calls on ten player actions, 60 metadata extractions), all ending normally, which at the earlier rate would happen by chance less than one time in a hundred. An eight-turn Elvira session in classic as aggressor on the new default: no Brain, Director, or extraction failure and no engine warning or error, six streamed turns identical to the final text, the first sentence after a median 3.1 seconds, the Brain's prompt taking 1,024 of 1,843 tokens from the cache, the narrator's 2,560 of 5,134, and about 16 cents for the session before caching.

Quality gate: 1494 tests green, twenty-nine project-rule scans clean, coverage 90.13%, ruff check and ruff format clean on 208 files, mypy --strict clean on 109 source files. Save format unchanged.

## [2026.09.26.19] — 2026-09-26

GLM 5.3's structured failures probed: 3 of 220 structured calls (1.4 percent) broke off at the 8192-token limit after a short piece of JSON, taken for a reasoning runaway, so the structured roles stayed on GLM 5.3 Flash. 2026.09.26.20 found the real cause, a carriage-return loop. The roadmap item about the Director reaching its three-round tool limit was dropped, since one tool cannot reach it.

## [2026.09.26.18] — 2026-09-26

A third group of narrator-prompt changes (a WRONG/RIGHT pair for failed searches and questions, the system prompt without its MUSTs and NEVERs) was measured on a forced-miss bench and not adopted. That bench is not in the repository. With earlier attempts, five instruction variants left investigation misses as soft as before, so the remaining softening looks like the model's. The wording of 2026.09.26.17 was corrected: the model mix was kept for reliability and cost, not for higher scores.

## [2026.09.26.17] — 2026-09-26

The narrator and creative clusters stayed on GLM 5.3; the Director, the Brain, judgment, and extraction went back to GLM 5.3 Flash after GLM 5.3's JSON failed a few times on Together. Over four sessions the mix matched all-GLM-5.3 on the judged scores at less than half the cost (7.3 against 16.5 cents for eight turns). Reverted in 2026.09.26.20.

## [2026.09.26.16] — 2026-09-26

Prompt review, second group: word budgets for the opening and chapter opening (250 to 350 words) and the epilogue (350 to 500), whose reflection on the character's growth is the one named exception to PLAYER AGENCY; the Brain prompt no longer restates the fields its schema enforces; the extractor prompts read the opening clock and the dispositions from configuration.

## [2026.09.26.15] — 2026-09-26

Prompt review, first group: three contradictions removed (the Director rules out the supernatural only where `<world>` lacks it, the chapter opening takes history only from what is established, the tone block follows the Director only for world and NPCs), and the Director's fixed task moved ahead of the changing scene, which raised its cached input from 27 to 50 percent.

## [2026.09.26.14] — 2026-09-26

Every role on GLM 5.3 through Together, the user's choice: on the forced-miss bench it followed the instructions about as well as GLM 5.3 Flash and finished a narration in 2.1 seconds against 3.3, at about nine times the price per token.

## [2026.09.26.13] — 2026-09-26

Elvira's judge also sees the previous narration, the backstory, the NPC descriptions, and the rolled move's own text for the result, so continuity no longer counts as invention and an unwelcome truth on a miss no longer as a silver lining. New baseline.

## [2026.09.26.12] — 2026-09-26

The narrator stops taking over the player character: a budget of 150 to 220 words, a PLAYER AGENCY rule covering the character's inner life, actions, words, and past, a Director rule that keeps its guidance off the player character, and the narrator at temperature 1.0 and top_p 0.8. Over six measured variants this raised judged player agency from 2.75 to 4.08 and cut complaints about the player character from 42 to 17 percent.

## [2026.09.26.11] — 2026-09-26

The Director's reflections become one required slot per selected NPC, keyed by its id, so a duplicate cannot be written; one tool, `query_game_state`, replaces `query_npc`, `query_active_threads`, and `query_active_clocks`.

## [2026.09.26.10] — 2026-09-26

Blueprint voicing fixes the number of acts, revelations, and endings in its schema with `minItems` and `maxItems` and calls once instead of asking again; `AIResponse` carries a host's reasoning text, and a Director failure shows its end.

## [2026.09.26.9] — 2026-09-26

The Director's retry of 2026.09.26.8 removed, since every failure ran to the 8192-token limit and a retry cannot prevent that; a failure now reports its stop reason, output and reasoning tokens, and JSON length, and the OpenAI-compatible adapter reports reasoning tokens.

## [2026.09.26.8] — 2026-09-26

The Director retried its final step once on invalid JSON (removed in 2026.09.26.9); a failed Director keeps the NPCs' importance accumulators instead of zeroing them.

## [2026.09.26.7] — 2026-09-26

The users folder follows `STRAIGHTJACKET_USERS_DIR` when set; Elvira keeps her players in tests/elvira/users.

## [2026.09.26.6] — 2026-09-26

The succession WebSocket tests save into a temporary users folder instead of the project's `users/`.

## [2026.09.26.5] — 2026-09-26

Every role on GLM 5.3 Flash through Together, the user's choice for its narration; Elvira stays on GPT-6 Luna. Together beat OpenRouter, Fireworks, and Baseten on time to the first sentence (2.9 seconds) because it also caches short prompts.

## [2026.09.26.4] — 2026-09-26

The startup check works with Together, whose `/models` returns a bare list the OpenAI SDK cannot parse; Together configured beside the other providers.

## [2026.09.26.3] — 2026-09-26

NPC statuses get one central list in `engine/enums.yaml`, and the correction schema limits `status` to it.

## [2026.09.26.2] — 2026-09-26

Elvira's player and judge name their own provider and model (GPT-6 Luna) instead of following the game; OpenRouter configured; cheap models measured against Luna (DeepSeek V4 Flash, GLM 5.3 Flash, Qwen3.7 Flash, Ling 3.0 Flash, Gemma 4 31B). Fix: the correction schema limits `disposition` to the known dispositions, after a model wrote a stance there and crashed the next turn.

## [2026.09.26.1] — 2026-09-26

The model-comparison harness removed at the user's request, so the project is the game plus Elvira again; a new test covers the engine lines only the harness reached; this CHANGELOG shortened up to 2026.09.26.0.

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
