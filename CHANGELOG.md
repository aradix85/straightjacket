# Changelog

Straightjacket — AI-powered narrative solo RPG engine. See [ORIGINS.md](ORIGINS.md) for where it comes from.

This log starts at 2026.09.24.0, the restart after a four-month pause. Earlier releases, back to the fork from EdgeTales, and the longer text of entries that were later shortened are in git history (`git log -p CHANGELOG.md`).

## Versioning

Calendar versioning: `YYYY.MM.DD.N`, where `N` is a zero-based counter for releases on the same day.

## [2026.10.17.4] — 2026-10-17

Step 9g: tests that play a turn, a correction, a momentum burn, or a chapter transition now build their game through the real character creation (`tests/_creation.py`, with a scripted provider for the opening, the blueprint, and the opening extraction), in place of hand-built states. The move surfaced what hand-built states hid. The correction tests had asserted that a correction adds a scene and a narration entry, an artifact of a snapshot taken after its own turn; real play keeps both, and the tests now play a real turn and correct it. The rollback test now fails a real narrator call after the turn changed the state, and the whole game comes back unchanged. A new test plays a created game through a chapter transition, and it showed the chapter opening registering "Kira" beside the returning "Kira Vance", because the name matcher ignored names shorter than five letters even when they were a whole word of the known name; such a name now matches, and mid-game it keeps the known name instead of shortening it. Hand-built stats had also been an invalid spread (seven points where creation demands nine). A created game plays a turn in each playable setting and passes Elvira's invariants. The scene-test check no longer loops over random rolls, which a created game's keyed scenes made fail now and then; it gives the three rolls that decide the three scene types. Step 9h, the principle audits, becomes NEXT STEP with a new substep.

Quality gate: 1646 tests green, coverage 91.97 to 92.04% between runs, so the floor rises to 91; ruff and mypy --strict clean. Save format unchanged. No Elvira session, since only tests and the name matcher changed and the matcher has its tests.

## [2026.10.17.3] — 2026-10-17

Documentation only. Step 10 gains substep 10.7, at the user's request: at a generated place, a miss takes its worsening from the place's own peril table and an offered opportunity from its opportunity table (Starforged's location themes, derelicts, vaults, planets, and space; Sundered Isles' overland, caves, ruins, and shipwrecks), so the soft and unconnected costs that Elvira's audit keeps finding on misses come from the source tables instead of the narrator. The roadmap's notes for sessions with the user record the user's preference to settle from the source material whatever a rulebook table can settle.

Quality gate: project-rule scans clean. No code, prompt, or configuration changed.

## [2026.10.17.2] — 2026-10-17

Step 9e, the open findings from Elvira runs, each fixed in the engine. A `present` fact answered no about the NPC an action targets now releases that target, so the narrator is no longer told an NPC is out of reach while the same NPC is the one the action is aimed at. The metadata extraction's schema offers only known NPC ids for renames and details. An NPC records whether the engine rolled its name: a different full name for such an NPC becomes a new figure, while a figure the narration named, such as a lore figure, now takes its revealed name instead of spawning a stub. A figure matched by description keeps the known NPC's name (a classic run had renamed "Corrin Hale" to "Warden archer"), and a chapter opening no longer registers "Maren" beside the returning "Maren Silk". Blueprint voicing asks once more when its counts are wrong, the user's choice. In dialogs the NPC's fact budget governs instead of "nothing beyond the question", also the user's choice: on the two dialog situations the blind reader preferred the variant 5 to 4 when shown its prompt, and the old prompt 5 to 2 when shown the old rule, which forbids what the budget allows. The coverage tracker no longer misses NPC introductions. Step 9g becomes NEXT STEP.

Quality gate: 1641 tests green, coverage 91.52%, ruff and mypy --strict clean. The save format breaks: NPCs record `name_rolled`. Two Elvira sessions, Starforged through a chapter transition and classic Ironsworn: blueprint voicing succeeded at both chapter starts, no engine warnings, two low audit scores on misses of a known kind. About $1.70 for the sessions and the dialog measurement.

## [2026.10.17.1] — 2026-10-17

Step 9d, generators: places and NPC names come from the setting's own tables instead of the narrator. Each setting names under `generators` the oracle table every role of a category rolls, and `datasworn/oracle_rolls.py` follows Datasworn's own roll instructions (automatic Action and Theme rolls, Roll twice, a role that picks the table an earlier role points to). When the Brain moves the character to a place the world does not know yet, it names the place's kind, settlement or location, and the engine rolls it, keeps it with the world, and gives the narrator its details as `<generated>` for as long as the character is there; a correction keeps the place, and a return finds it again. NPC names go through the same roller, and `oracle_paths.names` became the npc category. The decisions, taken with the user, are under Decisions in the roadmap. Fixed on the way: the NPC name roll no longer swallows a missing table, Elvira's name roll no longer suppresses errors, and a test fixture that left the in-memory database out of sync is synced. Three Elvira sessions, one per playable setting: each generated a place (a big moor in classic Ironsworn, a sacred area aboard a ship in Starforged, a swamp landmark by a Sundered Isles quay), and the narration carried it; no engine warnings, one audit score of a known kind. Step 9e becomes NEXT STEP with a new finding, a named NPC renamed to a generic label by description matching.

Quality gate: 1635 tests green, coverage 91.19%, ruff and mypy --strict clean. The save format breaks: the world keeps its generated places. Elvira about $1.75.

## [2026.10.17.0] — 2026-10-17

Documentation only: step 9f closes, at the user's choice. Two more narrator-prompt variants for 9f.6 were measured on the fourteen situations: a budget of 250 to 350 words with the extra room steered to sensory detail of the same beats, and the same with ordinary mechanical sounds allowed under GENRE PHYSICS. Steering the room took away the loss of the earlier longer budget (blind reading 7 to 14 then), but neither variant won (8 to 7 and 8 to 9), player-character findings rose with the length, and the second variant wrote three of 84 narrations in the third person; its lower audit count came from the milder rule alone. After six rounds in which rewording stayed within the noise, the faults that remain are for the engine. The roadmap keeps 9f as one DONE entry, moves measuring the extraction prompts to the new step 9m and the clash between fact budget and dialog task to step 9e, and makes 9d, generators, the next step. About 4 dollars.

Quality gate: project-rule scans clean. No code, prompt, or configuration changed.

## [2026.10.16.8] — 2026-10-16

Step 9l, the user's idea: a weak-hit complication of Gather Information or Compel can start a four-segment threat clock (`mechanics/complications.py`), named from the story-complication table or a Mythic action pair, one open at a time. It fills every scene and strikes through the threat fill tag unless the Brain aims a hit at it (`target_clock`, from a `<dangers>` block). Elvira's new `complication` scenario, three sessions: the narrator showed each danger as a subtle first sign and its arrival later, and one was headed off. The roadmap keeps finished work in a short DONE section at the bottom.

Quality gate: 1621 tests green, coverage 91.09%, ruff and mypy clean. Save format unchanged. Elvira about $2.

## [2026.10.16.7] — 2026-10-16

The weak hit of Gather Information and Compel follows the rulebook, at the user's choice: its cost is the complication the move text names (a complication or a new danger, a demand in return), and it may be subtle. A `complication` effect in `engine/move_outcomes.yaml` gives the narrator that complication as a consequence it must tell (`engine/consequence_templates.yaml`), and the narrator's WEAK_HIT rule takes a named complication as the cost, falling back to something lost or broken where none is named. Measured on the three weak hits of the set, the audit no longer missed a cost; the blind reader, judging by the old rule, preferred a material loss 10 to 3, which is the stricter reading the user chose not to keep. The user's idea of a complication that strikes only when left alone becomes step 9l, complications as clocks. Tests cover the effect and its sentence.

Quality gate: 1606 tests green, project-rule scans clean, coverage 90.98%, ruff and mypy --strict clean. Save format unchanged. Elvira, eight turns in Starforged: no problems and no engine warnings, though no weak hit of these two moves came up; about 43 cents.

## [2026.10.16.6] — 2026-10-16

Documentation only: the 9f.11 branch measured with a WEAK_HIT rule that counts a named complication as the cost, on the three weak hits of the set. The audit no longer missed a cost, but the blind reader preferred the current narrations 10 to 3, because they show a loss where the branch shows a complication. Whether these weak hits follow the rulebook or keep the stricter loss is now an open decision for the user under 9f.11. Under 1 dollar.

Quality gate: project-rule scans clean. No code, prompt, or configuration changed on main.

## [2026.10.16.5] — 2026-10-16

Documentation only: 9f.6 and 9f.11 measured, neither adopted. The blind reader no longer counts length, since the user values only quality. A budget of 300 to 400 words lost that reading 7 to 14, because the extra words went to NPC facts beyond the fact budget, further developments on a miss, and moves the player did not choose; 9f.6 now asks for the extra room to go to sensory detail. For 9f.11 the engine names the complication that the weak hit of Gather Information and Compel carries by its move text; the narrator told it, but the audit still counted a missing cost, since the narrator prompt defines a weak hit's cost more narrowly than the moves do. That change waits on the branch `9f11-weak-hit-complication`, with its tests, until it is measured together with a WEAK_HIT rule that matches the moves. About 2 dollars.

Quality gate: project-rule scans clean. No code, prompt, or configuration changed on main.

## [2026.10.16.4] — 2026-10-16

Documentation only. Step 9f spends credits only where a change shows something, at the user's wish: a variant targets a problem found in measured narrations, gets the audit and the blind reading first, and the ten Elvira sessions only on a clear signal. The first variant under that rule paired "looking touches nothing" with a visible cause for every setback; the misses recovered from v14, but player-character findings stayed at 41 and 41 and the blind reader preferred the current prompt 9 to 7, so no Elvira sessions ran and the prompt stays. About 1.50 dollars.

Quality gate: project-rule scans clean. No code, prompt, or configuration changed.

## [2026.10.16.3] — 2026-10-16

Documentation only: the first round of step 9f against the new baseline. The measuring set now matches the engine (no "nothing useful" fact on a hit, Director notes by name), and the audit baseline was remade on it: 98 and 122 findings. Openings stayed in the second person and Kestrel kept the player character's past to herself on Sonnet, so 9f.9 and 9f.10 close without a prompt change. Three variants were measured and none adopted: removing "action" from the camera list (9f.3; blind reading 9 to 8, Elvira 6.52 against 6.41), replacing the copied example (blind reading 10 to 7, Elvira 6.60), and the rule that looking touches nothing (lost the blind reading 4 to 15; Elvira 6.39), which 9f.15 now pairs with a visible cause for setbacks. `docs/ai.md` gives the reason the clusters send no sampling parameters. About 25 dollars at full price.

Quality gate: project-rule scans clean. No code, prompt, or configuration changed.

## [2026.10.16.2] — 2026-10-16

Documentation only: a new Elvira baseline for step 9f under the Haiku 5.5 judge. Ten sessions of the unchanged prompt (the five comparison situations twice) scored 6.41 ± 0.14 overall and 3.81 for result integrity, where GPT-6 Luna had scored the same prompt 7.52 ± 0.18, so Haiku judges more strictly; the measuring setup's README names the new baseline. Two engine warnings: the Brain's known Set a Course as dialog (step 25), and blueprint voicing returning one revelation of three, since Anthropic does not enforce array counts, now a finding under step 9e. About 6.30 dollars at full price for the ten sessions.

Quality gate: project-rule scans clean. No code, prompt, or configuration changed.

## [2026.10.16.1] — 2026-10-16

Elvira's player and judge run on Claude Haiku 5.5 instead of GPT-6 Luna, at the user's choice, since the monthly Anthropic credit covers them: the player without thinking, the judge at effort low with room for 16,000 tokens, and a null temperature now accepted. A judge tends to favour its own model family, so Elvira scores from before this version are no baseline; step 9f needs ten fresh sessions of the unchanged prompt first. A four-turn Elvira session in Sundered Isles ran with the Anthropic key alone: the judge scored every narration, no engine warnings.

Quality gate: 1602 tests green, project-rule scans clean, coverage 90.97%, ruff and mypy --strict clean. Save format unchanged.

## [2026.10.16.0] — 2026-10-16

A critical read of every md file against the code. Corrected: a tool loop that no longer exists, a death through Face Death that nothing starts, a succession that clears every clock, AI decisions the docs left out (the Brain's free-text location, the Director's narrator guidance, the extraction's dispositions), provider notes presented as current, and Delve's 12 domains; duplicates point to one place, and this log keeps a few sentences per entry. The correction analysis and blueprint voicing escape player text, the layer scan keeps `tools` from `ai`, and a setting's `id` must equal its file name, each with a test. Roadmap steps 14a to 36 are short sketches now. The Yaml content boundary states the user's choice: game content comes from the sources, an oracle, or as the last resort the AI, never by hand, while the engine's own text lives in yaml. New substeps 9h.9 and 9h.10.

Quality gate: 1602 tests green, project-rule scans clean, coverage 90.96 to 91.03% between runs, so the floor stays at 90, ruff and mypy --strict clean. Save format unchanged. Elvira, eight turns in classic as explorer: a correction replayed through the escaped analysis, blueprint voicing succeeded, no engine warnings; three problems of known kinds (an NPC moving off screen, a soft miss, a weak hit without its benefit); about 48 cents at full price.

## [2026.10.09.4] — 2026-10-09

A hit on a search no longer reaches the narrator beside a fact saying that nothing useful is there. A search miss settles `useful` to no, so a later hit at that place, a hit after a no from the same turn's fact roll, or a burn from a miss to a hit told the narrator both. `mechanics/facts.py` → `overrule_facts_by_hit` now drops such a no on a hit, from the prompt and from the place; the turn, the momentum burn, and the state correction call it. Five Elvira sessions: overall 7.12, no engine warning. A narrator prompt with targeted changes for Sonnet (roadmap 9f.15) was measured and not adopted: fewer audit findings, no preference in the blind reading, and 7.23 against 7.52 in ten Elvira sessions each.

Quality gate: 1599 tests green, coverage 90.96%. Save format unchanged.

## [2026.10.09.3] — 2026-10-09

Every role now runs Claude Sonnet 5.5 at effort medium, the user's choice after comparing it with Haiku 5.5: the blind reader preferred Sonnet medium over Haiku medium 14 to 6, and five Elvira sessions each scored Sonnet medium 7.60 against 7.12 for Haiku, at about ten times the cost. Three faults that Sonnet showed are fixed: the Director's schema broke Anthropic's limit of 16 nullable fields when three NPCs reflected, so its reflection fields are plain strings; the Director no longer gets a tool round in which Sonnet called tools that do not exist, and `run_tool_loop` is gone; and the Anthropic adapter no longer sets the automatic cache mark beside its own. A twelve-turn session costs about 54 cents.

Quality gate: 1592 tests green, coverage 90.94%. Save format unchanged.

## [2026.10.09.2] — 2026-10-09

Every role ran Claude Haiku 5.5 at effort medium, the user's choice after 2026.10.09.1; Haiku 5.5 refuses `temperature`, `top_p`, and `top_k`, so the clusters stopped sending them. Anthropic caching works now: the adapter marks the part of the system prompt that is fixed within a game, where the automatic mark fell on the changing last block. Fixed in what the models are told: a progress mark no longer reaches the narrator as a lasting wound, Director notes name the NPC instead of its id, and the Brain and the Director see the world. Every prompt and engine text was rewritten except the narrator's, whose rewrite cut audit findings but lost the blind reading 3 to 14 and scored lower in Elvira; the extraction requests moved into `prompts/narrator.yaml`.

Quality gate: 1591 tests green, coverage 91.00%. Save format unchanged.

## [2026.10.09.1] — 2026-10-09

Claude Haiku 5.5 measured against GLM 5.3 for every role and effort, at the user's request; the model stayed GLM 5.3 until the user decided. One engine change: Anthropic's structured outputs refuse array limits such as `maxItems`, so the adapter passes schemas through the SDK's `transform_schema`, and the engine keeps checking counts after parsing. Haiku at medium won the blind readings against GLM at low and high and had fewer audit findings than GLM at low; GLM won the strong hits. In five Elvira sessions per setup, Haiku with the narrator at medium scored 7.44 against 6.82 for GLM at low, at about a sixth of the cost, with the first sentence after 10.8 seconds instead of 3.1.

Quality gate: 1581 tests green, coverage 90.95%. Save format unchanged.

## [2026.10.09.0] — 2026-10-09

A critical read of every md file against the code, and the fixes it called for. Act transitions no longer depend on the Director: `story_state.py` checks them in every turn's scene-end bookkeeping, so an act ends at the last scene of its range. The WebSocket origin check allows LAN play and IPv6 loopback and still refuses other sites. Player and save names with a path separator or a leading dot are refused instead of stripped. The import-layer scan splits the engine core into a base and the rest. Dead config went, `run.py` and `data/data.py` joined the comment scan, and the register gained three entries on threats, Forsake Your Vow, and scene-challenge progress. One Elvira session: no engine warnings.

Quality gate: 1580 tests green, coverage 90.91%. Save format unchanged.

## [2026.10.04.6] — 2026-10-04

Documentation only. The roadmap no longer notes the MiMo evaluation: the user is not changing models now and will take it up again later if needed.

Quality gate: 1557 tests green, project-rule scans clean (documentation drift included). No code, prompt, or configuration changed.

## [2026.10.04.5] — 2026-10-04

Documentation only. The roadmap's notes for sessions with the user say where the measuring setup for prompt tuning lives (outside the repository, with a README on capturing situations, measuring a variant, and reading blind) and that its captured situations predate the player-agency line of 2026.10.04.4. They also note that the evaluation of MiMo-V2.6-Pro at Prima Labs waits for Prima Labs' answer about its rate limit, with the report beside the measuring setup.

Quality gate: 1557 tests green, project-rule scans clean (documentation drift included). No code, prompt, or configuration changed.

## [2026.10.04.4] — 2026-10-04

Step 9f, substeps 1 and 2: the narrator's action and dialog tasks end with a player-agency line in the system prompt's own wording. Measured on GLM 5.3 over fourteen captured situations, audited by GPT-6 Luna: player-character overreach fell from 49 findings to 30 and the audit total from 158 to 131, and no other kind rose beyond the spread. A length line was not adopted, since together with the agency line it left weak hits without their cost more often. Step 9f gained three substeps from the measurement. One Elvira session: no engine warnings, player agency 4.5 of 5.

Quality gate: 1557 tests green, coverage 90.79%.

## [2026.10.04.3] — 2026-10-04

Documentation only. Step 9f, prompt tuning, becomes NEXT STEP ahead of 9d at the user's choice, with substeps, a definition of done, and a measuring method: the same captured situations for every variant, an audit by a judge from another model family, and a blind reading with balanced positions. A first comparison of GLM 5.3 with MiMo-V2.6-Pro scored both alike. Step 9e gains a finding: a fact can place an NPC out of reach while that NPC is the scene's target.

Quality gate: 1557 tests green, coverage 90.77%.

## [2026.10.04.2] — 2026-10-04

Documentation only. Scene challenges turned out to be configured but unreachable: Begin the Scene has no roll, so no scene-challenge track ever exists, and the `fill_clock` effect of their misses is read by nothing. New step 9k makes them playable from the rulebook, and `docs/mechanics.md` says they are not playable yet.

Quality gate: 1557 tests green, coverage 90.81%.

## [2026.10.04.1] — 2026-10-04

Documentation only. The md files state the current state, each fact in one file: reasons are written out instead of pointing to CHANGELOG versions, process rules live in CONTRIBUTING.md, the divergence register is the one list of where the AI still decides, and this log starts at 2026.09.24.0. The user decided that death comes only through Face Death; step 9j.5 builds it.

Quality gate: 1557 tests green, coverage 90.77%.

## [2026.10.04.0] — 2026-10-04

The Brain chooses a track by id, and track names reach its prompt escaped. Action moves that mark progress (Strike, Clash, Gain Ground, expeditions, journeys, delves, scene challenges) never marked it, because Datasworn gives a track category only to progress rolls; they name their category in `engine/track_moves.yaml` now. The position resolver's secured-advantage factor fires again. The design document is linked instead of copied, and Elvira has `docs/elvira.md`. Two Elvira sessions in Starforged: Strike and Clash filled the fight's track.

Quality gate: 1557 tests green, coverage 90.76%. Save format unchanged.

## [2026.09.29.12] — 2026-09-29

Step 9c, soft misses from the engine side. On a miss every NPC present withholds, the target NPC's agenda, memories, and secrets stay out of the prompt, and Director guidance and a pending revelation wait for a hit; an information miss settles `useful` as no, and a miss with a match rolls the story-complication oracle where the setting has one. Elvira gained a `miss` scenario. On audited misses, result integrity rose from 3.0 to 3.4 of 5; three other variants measured no better and were dropped.

Quality gate: 1550 tests green, coverage 90.65%.

## [2026.09.29.11] — 2026-09-29

Documentation only. The design document is now `docs/narrative_rpg_engine_v2_4.md` instead of a PDF, so a session reads it with the other md files; the text is unchanged (5,493 words in both, compared word by word), with its sections as headings and its prompt examples as code blocks. README, ORIGINS, ARCHITECTURE, and the divergence register link to it.

## [2026.09.29.10] — 2026-09-29

Documentation only. The working agreements that lived only in conversation are now in the roadmap, so a fresh session can pick up the work: short CHANGELOG entries, commit and push per finished release, Elvira sessions as part of a step, Dutch plain-prose answers for a screen-reader user, and starting a session by reading every md file. Step 10 notes the Location Crafter in case the user buys it.

## [2026.09.29.9] — 2026-09-29

Documentation only. At the user's request the priorities list is gone and every item on it is a numbered step in the order of work: 9c soft misses, 9d generators, 9e Elvira findings, 9f prompt work, 9g fixtures, 9h principle audits, 9i revelations, 9j rules conformance. A new finding becomes a substep or a step in the same commit.

## [2026.09.29.8] — 2026-09-29

Step 9b, chapters as Mythic adventures. The EdgeTales resets are gone: health, spirit, supply, momentum, and clocks carry over, the chaos factor restarts at Mythic's 5, and a game that is over continues only through succession. The engine writes the chapter record from its own data, so the `chapter_summary` AI role is removed. An Elvira `chapter_end` session reached the new chapter with its clocks carried over and no engine warning. The save format breaks.

Quality gate: 1529 tests green, coverage 90.44%.

## [2026.09.29.7] — 2026-09-29

Documentation only. The user made chapters the next step: new step 9b treats a chapter as Mythic's and the Adventure Crafter's adventure within a campaign and removes what came from EdgeTales (refilled health, spirit, supply, and momentum, wiped clocks, an AI-written chapter summary), with two register entries until then. The generators move to step 9c and engine-settled revelations to 9d; earlier CHANGELOG entries keep the old numbers.

## [2026.09.29.6] — 2026-09-29

Documentation only. A one-time coverage map checked every part of the four Datasworn rulesets, Mythic GME 2e, the Adventure Crafter, Blades, and the design document against the code and the roadmap. What stood nowhere became roadmap work, including new steps 10b, 13c, and 36, and the register gained the session moves, Mythic's rules-system parts, and foe actions decided by the AI.

## [2026.09.29.5] — 2026-09-29

The user's two decisions, built from the classic move texts. Classic Ironsworn marks experience by the vow's rank when Fulfill Your Vow hits, instead of filling Starforged's legacy tracks. Draw the Circle takes the boasts the player declares, read by the Brain, each for +1 momentum and its cost from `engine/boasts.yaml`. New register entries: a classic successor inherits no legacy boxes, and a duel opens no combat track.

Quality gate: 1535 tests green, coverage 90.47%.

## [2026.09.29.4] — 2026-09-29

Documentation only. ARCHITECTURE.md records the order of preference: a tabletop system decides first, an engine rule second, and the AI only writes prose and reads free text. The user decided that classic Ironsworn earns experience by its own rule and that boasts are modelled. A new sketch step lets the engine settle when a revelation lands, so the revelation-check AI call can go.

## [2026.09.29.3] — 2026-09-29

The opening extraction asks for the place's short name as the narration gives it, two to five words, with what happens there in `scene_context`. Before, all three openings of the day's classic sessions came back as descriptive sentences of 15 to 20 words, which then stood in `<location>`, `<prev_locations>`, and `<fact about>`; after, four openings (three Sundered Isles, one classic) gave three-word names such as "Terracoyote Crossing wayhouse". No engine warning besides one Director time-out.

Quality gate: 1526 tests green, thirty project-rule scans clean, ruff and mypy --strict clean.

## [2026.09.29.2] — 2026-09-29

`docs/divergences.md` becomes a register: every departure says why and ends with a status (Permanent, Until step N, or Open), and a project-rule scan rejects an entry without one. `apply_progress_and_legacy` takes the rolled track and raises instead of assuming a rank. Setting yaml gains a required `playable`, so Delve is no longer skipped by name.

Quality gate: 1526 tests green, coverage 90.42%.

## [2026.09.29.1] — 2026-09-29

A correction of a misread input replays the turn through the turn's own code (`replay_turn`) with the same scene type, facts, and dice, instead of a separate copy that lost misses, track creation, clock ticks, and the scene end. The correction AI no longer decides whether to reroll, and a corrected turn can offer a momentum burn. Elvira's new checks caught a restore that cut the narration history by length; it is copied whole now. The save format breaks.

Quality gate: 1523 tests green, coverage 90.48%.

## [2026.09.29.0] — 2026-09-29

Step 9a, fact resolution: the Brain names the facts an action or question turns on, Mythic's fate chart settles them with odds the engine derives from `engine/fact_resolution.yaml`, and the narrator gets them as `<facts>`. A fact belongs to its place, and a hit settles a yes where the type says so. The momentum burn resumes from a snapshot taken after the roll instead of overwriting the previous turn. Two Elvira sessions: facts resolved in play, no engine warnings. The save format breaks.

Quality gate: 1517 tests green, coverage 90.52%.

## [2026.09.27.2] — 2026-09-27

Documentation only: the user decided step 9a's open points. A fact hangs on an NPC id or on the current location, every fact clears when the player moves and at a chapter start, each fact type says whether a hit clears it, and resolved facts live in one list on the world state.

## [2026.09.27.1] — 2026-09-27

The engine owns the opening clock and the time of day. The opening extraction asked the model for both and overwrote the engine's clock and time, and a succession discarded its extraction, so the successor's opening NPCs were never registered. The extraction now returns only NPCs, memories, deaths, location, and scene context; every opening starts at `opening.time_of_day`, only a new game gets an opening clock, and a succession applies its extraction. Two Elvira sessions in Sundered Isles reached succession and a chapter transition without engine warnings. The user decided how step 9a derives its odds.

Quality gate: 1489 tests green, coverage 90.15%. Save format unchanged.

## [2026.09.27.0] — 2026-09-27

Documentation only: the working documents restructured along common practice, with duplicates and claims the code contradicts removed. ARCHITECTURE.md becomes a bird's-eye view, CONTRIBUTING.md returns, and the details move to `docs/` (`ai.md`, `mechanics.md`, `settings.md`, `divergences.md`); the documentation-drift scans follow. Roadmap step 9 is split so that fact resolution comes first. The md files went from about 257 to 161 KB.

Quality gate: 1494 tests green, coverage 90.14%.

## [2026.09.26.20] — 2026-09-26

The "runaway" of GLM 5.3's structured answers was a carriage-return loop inside the JSON, which a JSON grammar allows. Every cluster bans the 396 tokens of its tokenizer that hold a carriage return through `logit_bias`, and every call with a schema gets the compact schema at the end of its prompt, so cached prefixes stay intact. Before, 3 of 220 structured calls broke off at the token limit; after, 0 of 360. Every role runs on GLM 5.3 again; an eight-turn Elvira session showed no failures.

Quality gate: 1494 tests green, coverage 90.13%. Save format unchanged.

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
