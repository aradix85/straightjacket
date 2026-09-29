# Changelog

Straightjacket — AI-powered narrative solo RPG engine.
Originally forked from [EdgeTales](https://github.com/edgetales/edgetales). See [ORIGINS.md](ORIGINS.md).

Entries up to 2026.09.26.19 were shortened to their essentials, in 2026.09.26.1 and 2026.09.27.0. The full original text, with every measurement and quality-gate figure, is in git history (commit 1cef542 for entries up to 2026.09.26.0, commit 5baa6ed for the rest).

## Versioning

Calendar versioning: `YYYY.MM.DD.N`, where `N` is a zero-based counter for releases on the same day. The first CalVer release is 2026.04.25.0; earlier `0.x.y` releases keep their numbers.

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
