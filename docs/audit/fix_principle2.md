# Principle 2 — Config-driven: fix-file

Audit of 2026-10-17, all four passes of AUDIT.md over `src/straightjacket/`, in one session. Paths are relative to `src/straightjacket/`; line numbers are those before the session's fixes. Each violation names its outcome: fixed in release 2026.10.17.8 or 2026.10.17.9, or the roadmap substep that holds it. Items marked **[needs human judgment]** waited for the user's decision; the user settled them the same day with the rules "Config over code" and "What belongs together lives together" in CONTRIBUTING.md, and each says how.

## Pass 2a — Readable strings

### Text a player reads

- **P2-01** `web/static/index.html:482` — the save list's load button writes "(scene N)" in English in the client, outside `strings/ui.yaml`. Fixed: `ui.load_entry`.
- **P2-02** `web/static/index.html:488` — the save list's delete button shows only the glyph "✕", with no text from yaml and no accessible name (the player list's delete button at line 298 has one). Fixed: aria-label from `ui.delete` and the save name.
- **P2-03** `web/handlers.py:226`, `web/handlers.py:321` — the status message "..." while a turn or correction runs is a literal. Fixed: `game.processing`.
- **P2-04** `engine/game/chapters.py:73` — an empty epilogue becomes the hardcoded "(The narrator pauses, then offers a quiet reflection on the journey...)", which is also a silent fallback (principle 3). Fixed: an empty epilogue raises `AIUnavailableError`, as an empty narration does, so the handler reports it and nothing changes.
- **P2-05** `engine/mechanics/random_events.py:294` — "Unnamed threat" names a threat or clock whose Mythic pair is empty, a state the meaning tables never produce (principle 3). Fixed: the fallback is gone.
- **P2-06** `engine/story_state.py:21`, `engine/story_state.py:22` — the aftermath act's title "Aftermath" and goal "Open-ended play" reach the narrator's story arc, the Director, and `/status`. Fixed: `aftermath_act_title` and `aftermath_act_goal` in `ai_text.narrator_defaults`, beside the other texts the engine puts in state for the narrator.
- **P2-37 [needs human judgment]** `engine/story_state.py:15` — without a blueprint the current act has the title and goal "?" and the mood "mysterious", a mood word with no source that reaches the narrator's story arc. Moving it to yaml would break the yaml content boundary instead; the question is whether a game without a blueprint should describe an act at all. Settled in 2026.10.17.9: every caller already checks for a blueprint first, so the invented act was unreachable, and `get_current_act` now raises without one.
- **P2-07** `engine/mechanics/adventure_crafter.py:267`, `engine/mechanics/adventure_crafter.py:325` — the placeholder names "Plotline N" and "Returning N" for list entries the Adventure Crafter creates reach blueprint voicing, random events, and the chapter record. Fixed: templates in `engine/adventure_crafter.yaml`.
- **P2-08** `engine/mechanics/random_events.py:250`, `engine/mechanics/adventure_crafter.py:626` — the suffix " (N)" that tells two clocks of the same name apart is a literal, in two copies of the same function (principle 5). Fixed: `clocks.duplicate_name_template`, one function.

### Text an AI reads: narration memory and scene log

These strings become `NarrationEntry.prompt_summary`, the user turn of the narrator's conversation memory (`ai/narrator.py:39`), or `SceneLogEntry.summary`, which reaches the narrator's `<recent_events>`, the Director, and the recap.

- **P2-09** `engine/game/game_start.py:310` "Opening scene: {player} in {location}", `engine/game/game_start.py:318` "Game start". Fixed.
- **P2-10** `engine/game/chapters.py:331` "Chapter {n} opening: {player} in {location}", `engine/game/chapters.py:339` "Chapter {n} begins". Fixed.
- **P2-11** `engine/game/succession.py:308` "Succession opening: …", `engine/game/succession.py:323` "Succession from {name}". Fixed.
- **P2-12** `engine/game/turn.py:88` "Action", `engine/game/turn.py:123` "Corrected action", `engine/game/momentum_burn.py:40` "Momentum burn", `engine/game/turn_types.py:40` the default "Action" (also pass 2d), and the formats `engine/game/turn.py:329` and `engine/game/turn.py:526`. Fixed: the labels and formats are prompt keys in `prompts/blocks.yaml`, and `SceneContext.summary_label` is required.
- **P2-13** `engine/correction/orchestrator.py:89`, `engine/correction/orchestrator.py:97`, `engine/correction/orchestrator.py:103` "[corrected] {intent}". Fixed.

### Text an AI reads: other

- **P2-14** `engine/prompt_boundary.py:22` — the sentence " Use {pronouns} pronouns for the player character." is an instruction to the narrator written in Python. Fixed: `opening_pronouns_hint` in `prompts/tasks.yaml`.
- **P2-15** `engine/tools/handler.py:26` "unknown tool: {name}", `engine/tools/handler.py:42` "{name} failed: {error}" — tool errors the Director reads. Fixed: prompt keys in `prompts/director.yaml`.
- **P2-16 [needs human judgment]** Prompt scaffolding assembled in Python: XML tags with their attribute names, `key:value` labels, and short markers the AI reads. Many equivalent wrappers already live in `prompts/blocks.yaml`, so the rule's letter covers these too, but they carry no prose. Moving them keeps every prompt byte-identical only with care, since the cached prefixes and the measured tuning depend on it. Sites:
  - `engine/ai/brain.py`: 35, 36, 38, 39, 65, 73, 79, 156, 158, 164, 226.
  - `engine/ai/narrator.py`: 143, 145, 147 (`[DECEASED]` and its sibling markers), 160, 162, 164, 165, 167, 168.
  - `engine/ai/blueprint_voicing.py`: 22 to 31, 35, 38 to 58, 63, 76.
  - `engine/ai/recap.py`: 45, 51, 54, 63.
  - `engine/correction/analysis.py`: 32, 34, 43, 52; `engine/correction/orchestrator.py:148`.
  - `engine/director.py`: 86 to 105, 135 to 150, 163, 202.
  - `engine/prompt_action.py`: 46, 48, 50, 55, 56, 61, 66, 70, 102, 103, 106, 109, 116, 124.
  - `engine/prompt_dialog.py`: 44, 45, 46, 51, 64.
  - `engine/prompt_boundary.py`: 18, 19, 20, 30, 47, 59, 76 to 79, 89, 93, 98.
  - `engine/prompt_shared.py`: 36, 41, 64, 72, 86, 92, 94, 99, 114, 119, 120, 125, 131, 133, 140, 149, 176, 179, 184, 186, 189, 228, 236, 239, 241, 254, 256, 264, 273, 307, 309, 340, 349, 354.
  - `engine/prompt_blocks.py`: 18, 24.
  - `engine/mechanics/bonuses.py:86`, `engine/mechanics/tracks.py:73` (the oracle answer's " / "), `engine/mechanics/random_events.py:279` (the same separator in a clock's trigger), `engine/game/turn.py:461` (a note spliced in before `<task>`).
  Settled: the markup moves to `prompts/*.yaml`, one prompt module per session (roadmap 9h.12).

## Pass 2b — Numeric thresholds

- **P2-17** `engine/mechanics/fate.py:98` to `engine/mechanics/fate.py:102` — the fate check's answer ranges (18 to 20, 2 to 4, 11) are literals, while `engine/fate.yaml` holds hand-copied odds and chaos modifiers; `data/mythic_gme_2e.json` → `fate_check` carries all three. Fixed: the fate check reads Mythic's own table, and the copies leave `engine/fate.yaml`.
- **P2-18** `engine/mechanics/consequences.py:245` — a loss of 2 or more counts as heavy for the consequence sentence. Fixed: `resources.heavy_loss_amount`.
- **P2-19** `engine/npc/matching.py:120` — a word of a name counts when it has at least 4 letters. Fixed: `fuzzy_match.named_in_min_word_length`.
- **P2-20** `engine/mechanics/world.py:25` — two location names are compared as word sets when the shorter has at least 2 words. Fixed: `location.word_match_min_words`.
- **P2-21** `engine/npc/memory.py:50`, `engine/npc/memory.py:89` — the importance scale's maximum of 10. Fixed: `memory.importance_max`.
- **P2-22** `engine/game/action_resolution.py:67` — a threat's menace share divides by a literal 10 boxes instead of its own track. Fixed: the threat's own box count.
- **P2-23** `engine/game/game_start.py:149`, `engine/game/game_start.py:165`, `engine/game/turn.py:365` — the Mythic list weight 2 of a vow's thread and the vow's subject. Fixed: `random_events.seeded_list_weight`.
- **P2-24** `engine/mechanics/adventure_crafter.py:428`, `engine/mechanics/adventure_crafter.py:429` — the "roll for two" ranges of the character identity and descriptor tables (1 to 33, 1 to 21) copied from `data/adventure_crafter.json`. Fixed: read from the table's own row, named in `engine/adventure_crafter.yaml`.
- **P2-25 [needs human judgment]** Dice sizes and the score cap: `engine/mechanics/consequences.py:18`, `19`, `26`, `34`, `45`, `54` (d6, d10, the cap of 10), `engine/mechanics/fate.py:39`, `82` (d100, 2d10), `engine/mechanics/scene.py:26`, `50`, `73` (d10), `engine/mechanics/random_events.py:29` (d100), `engine/mechanics/adventure_crafter.py:97`, `231`, `236`, `262`, `472`, `474`, `483` (d10, d100). Also `engine/models_base.py:144` `ProgressTrack.TICKS_PER_BOX` (4), a class constant rather than a field. They are the source systems' own rules rather than tunable thresholds. Settled and fixed in 2026.10.17.9: every die and the score cap are in `engine/dice.yaml`, the progress score's cap is the track's box count, and the ticks per box are in `engine/progress.yaml`; a test checks the dice against the tables they roll.

Not violations: the range checks that mirror these dice (`1 <= roll <= 100`), regex group numbers, `len(parts) >= 2` checks on parsed strings, `ThreadPoolExecutor(max_workers=2)` for two parallel calls, log truncations, hash and number-base arguments, and `scene.py:57` (two adjustments, named by the table entry `make_2_adjustments`).

## Pass 2c — Mappings

- **P2-26** `engine/mechanics/world.py:42`, `engine/mechanics/world.py:44` — which dispositions raise or lower chaos in dialog. Fixed: `chaos.dialog_raising_dispositions` and `dialog_lowering_dispositions`.
- **P2-27** `engine/director.py:65` — the act phases whose first turn calls the Director. Fixed: `pacing.director_phases`.
- **P2-28** `engine/mechanics/consequences.py:126` — the clock types an NPC's agency ticks. Fixed: `pacing.npc_agency_clock_types`.
- **P2-29** `engine/story_state.py:60` — the act progress values that count as approaching the end. Fixed: `story_state.approaching_end_progress`.
- **P2-30** `engine/mechanics/world.py:115` — the scene types that count as intense for pacing. Fixed: `pacing.intense_scene_types`.
- **P2-31** `engine/mechanics/world.py:54` — the time progressions that move no time, a copy of the zero steps in `engine/time_progression_steps.yaml`. Fixed: read from that mapping.
- **P2-32** `engine/director.py:262`, `engine/npc/lifecycle.py:102`, `engine/ai/narrator.py:68`, `engine/parser.py:27` — four lists of sentence-ending punctuation, three of them for the same truncation check and each a little different. Fixed: `parser.sentence_end_marks` (the widest of the three, now shared) and `parser.sentence_breaks` in `engine/parser.yaml`. Still literal: `engine/parser.py:51` and `engine/parser.py:53`, in the salvage of truncated narration that roadmap 9h.13 reviews.
- **P2-33** `engine/models_npc.py:8` `NPC_STATUSES` — a copy of `enums.npc_statuses`. Fixed: the correction validates against the yaml list.
- **P2-34** `engine/models_base.py:176` `THREAT_CATEGORIES` — a hand-written list of Delve's threat categories with no reader (principle 5). Fixed: deleted.
- **P2-35 [needs human judgment]** NPC status groupings written as tuples at their callsites: `("active", "background")` at `engine/ai/brain.py:53`, `engine/director.py:58`, `engine/director.py:114`, `engine/director.py:411`, `engine/game/chapters.py:137`, `engine/mechanics/engine_memories.py:61`, `engine/npc/activation.py:27`, `engine/npc/activation.py:179`, `engine/npc/activation.py:204`, `engine/prompt_shared.py:217`, `engine/tools/builtins.py:50`; `("background", "lore")` at `engine/npc/lifecycle.py:84`, `engine/npc/processing.py:180`, `engine/npc/processing.py:215`; `("active", "background", "lore")` at `engine/npc/lifecycle.py:262`; `("active", "background", "deceased")` at `engine/game/chapters.py:104`; all four at `engine/ai/narrator.py:138`. A new status needs Python anyway, but named groups in `engine/enums.yaml` would say what each group means. Fixed in 2026.10.17.9: `npc_status_groups` in `engine/enums.yaml` (in play, reactivatable, description-matchable, returning at a chapter), checked against the status list by a test; the four-status guard at `engine/ai/narrator.py:138` let every status through and is gone, and the Adventure Crafter's present character statuses are in `engine/adventure_crafter.yaml`.

- **P2-36 [needs human judgment]** English parse patterns for AI output written in Python: `engine/game/chapters.py:63` (an "Epilogue" heading) and `engine/npc/memory.py:28` ("and", "mixed with" between emotion words). They follow the language of the prompts rather than a rule. Fixed in 2026.10.17.9: `parser.epilogue_heading` and `memory.emotion_split_pattern`.

Not violations: the hit results `("STRONG_HIT", "WEAK_HIT")`, the condition meters, the combat positions, Datasworn roll types and link formats, the legacy track names and end reasons that select model fields and Python branches, the effect keywords of the effect parser, protocol dictionaries (AI messages, JSON schemas, WebSocket messages, SQL), and security constants.

## Pass 2d — Dataclass defaults

196 defaults that are not empty collections, in 43 classes, beside 69 empty `default_factory` collections, which the rule allows (the scan's 197th hit, `ProgressTrack.TICKS_PER_BOX`, is a class constant and sits under P2-25). Roadmap 9h.4 removes them module by module; the optional fields of `AICallSpec` and the partial classes of `engine/datasworn/settings.py` parse external structures and stay, and the Datasworn classes keep a default only where the field is absent from a shipped ruleset or optional in the schema, checked per field in their session.

- `engine/ai/provider_base.py` AIResponse: stop_reason (34), usage (36), reasoning (37)
- `engine/ai/provider_base.py` AICallSpec: max_retries (46), temperature (47), top_p (48), top_k (49), extra_body (50), json_schema (51), tools (52), log_role (53), cached_system_prefix (54)
- `engine/datasworn/loader.py` OracleRow: oracle_rolls (32)
- `engine/datasworn/loader.py` OracleTable: collection_path (52)
- `engine/datasworn/moves.py` RollOption: using (13), stat (14), condition_meter (15), control (16), value (18), label (19)
- `engine/datasworn/moves.py` TriggerCondition: method (24), text (26)
- `engine/datasworn/moves.py` MoveOutcome: text (31)
- `engine/datasworn/moves.py` Move: id (36), key (37), name (38), category (39), roll_type (40), text (41), trigger_text (43), track_category (48), allow_momentum_burn (51)
- `engine/datasworn/settings.py` _OraclePathsPartial: action_theme (47), backstory (48), threats (49)
- `engine/datasworn/settings.py` _CreationFlowPartial: has_truths (54), has_backstory_oracle (55), has_name_tables (56), has_ship_creation (57), starting_asset_categories (58)
- `engine/game/finalization.py` ActionOutcome: outcome (38), position (39), effect (40)
- `engine/game/turn_types.py` SceneContext: stream (38), narrator_note (39); summary_label (40) is required since this session (P2-12)
- `engine/mechanics/adventure_crafter.py` ThemeAlternation: next_is_4 (92)
- `engine/mechanics/move_effects.py` MoveEffect: type (20), value (21), target (22)
- `engine/mechanics/move_effects.py` OutcomeResult: combat_position (28), pay_the_price (29), next_move_bonus (30), progress_marks (31), clock_fills (32), legacy_track (33), legacy_rank_shift (34), legacy_fixed_ticks (35), experience_rank_shift (36), boast_slots (37), chained_move (38), narrative_only (39)
- `engine/models.py` BrainResult: type (80), move (81), stat (82), approach (83), target_npc (84), dialog_only (85), player_intent (86), world_addition (87), location_change (88), track_name (89), track_rank (90), target_track (91), target_clock (92), bonus_id (93)
- `engine/models.py` TurnSnapshot: crisis_mode (108), game_over (109), player_input (110), brain (111), roll (112), narration (113), scene_setup (115)
- `engine/models.py` GameState: player_name (120), character_concept (121), pronouns (122), background_vow (124), setting_id (125), setting_genre (126), setting_tone (127), setting_description (128), stats (130), backstory (131), resources (139), world (140), narrative (141), campaign (142), preferences (143), crisis_mode (146), game_over (147), last_turn_snapshot (149), post_epilogue_director_done (150)
- `engine/models_base.py` EngineConfig: narration_lang (13)
- `engine/models_base.py` Resources: next_move_bonus (23)
- `engine/models_base.py` ClockData: filled (82), owner_id (83), fired (84), fired_at_scene (85)
- `engine/models_base.py` WorldState: current_location (113), current_scene_context (114), time_of_day (115), combat_position (119)
- `engine/models_base.py` ProgressTrack: ticks (151), status (152), completions (153)
- `engine/models_base.py` ThreatData: menace_ticks (199), status (200)
- `engine/models_base.py` ClockFillResult: track_completed (265)
- `engine/models_base.py` RandomEvent: target (276), target_id (277)
- `engine/models_base.py` SceneSetup: chaos_roll (283), interrupt_event (285), narrative_hint (286)
- `engine/models_base.py` FateResult: random_event_triggered (297), random_event (298)
- `engine/models_base.py` PlayerPreferences: player_wishes (303), content_lines (304)
- `engine/models_npc.py` MemoryEntry: tone (18), tone_key (19), about_npc (20), _score_debug (21)
- `engine/models_npc.py` NpcData: description (31), agenda (32), instinct (33), arc (34), introduced (37), importance_accumulator (40), last_reflection_scene (41), last_location (42), needs_reflection (43), gather_count (44)
- `engine/models_story.py` ThreadEntry: weight (18), linked_track_id (19), active (20)
- `engine/models_story.py` CharacterListEntry: weight (28), active (29), ac_status (30), ac_turning_point_count (31)
- `engine/models_story.py` PlotlineEntry: turning_point_count (39)
- `engine/models_story.py` SceneLogEntry: scene (44), scene_type (45), summary (46), move (47), result (48), position (51), effect (52), rich_summary (54), director_trigger (55), oracle_answer (56)
- `engine/models_story.py` CurrentAct: phase (81), title (82), goal (83), mood (85), transition_trigger (86), act_number (87), total_acts (88), progress (89), approaching_end (90)
- `engine/models_story.py` StoryBlueprint: story_complete (119)
- `engine/models_story.py` DirectorGuidance: narrator_guidance (124), arc_notes (126)
- `engine/models_story.py` KeyedScene: bound_entity_id (136), source (137)
- `engine/models_story.py` NarrativeState: scene_count (178), story_blueprint (181), director_guidance (182)
- `engine/models_story.py` CampaignState: chapter_number (309), epilogue_shown (310), epilogue_dismissed (311), epilogue_text (312), pending_succession (314), xp (316), xp_spent (317), legacy_quests (318), legacy_bonds (319), legacy_discoveries (320)
- `engine/npc/matching.py` _FuzzyMatch: npc (195), score (196), match_type (197)
- `web/session.py` Session: player (19), game (20), config (22), save_name (23), processing (24), active_ws (25), pending_burn (26)

## Findings for later principles

Seen while reading context, recorded for the session of their principle (roadmap 9h.13):

- Principle 3: `engine/mechanics/consequences.py:243` turns an unparsable amount into 1; `engine/mechanics/fate.py:35` clamps the chaos factor that the world already keeps in range; `engine/mechanics/fate.py:141` plays any method other than the check as the chart; `engine/mechanics/world.py:58` returns silently on an unknown time of day; `engine/user_management.py:57` returns an empty config when the file cannot be read; `engine/prompt_loader.py:23` skips a non-string prompt with a warning; `engine/parser.py` returns a raw excerpt when cleanup leaves the narration empty; `engine/parser.py` and `engine/ai/narrator.py` still handle a `<game_data>` block that no prompt asks the narrator for; `engine/game/game_start.py:301` reads `deceased_npcs` of the opening extraction with `.get`; `engine/tools/handler.py:21` reads the tool call's name and arguments with defaults.
- Principle 5: `MemoryEntry._score_debug` is written in five places and read nowhere.

Fixed in 2026.10.17.9 instead of waiting: the scene test's roll of 10 that could never be at or below the chaos factor; the emergent clock count written three times and the emergent threat count written twice, now `mechanics/clocks.py` and `mechanics/threats.py`; and two act-progress shares that `engine/story.yaml` called intensity smoothing.

## Grep log

Run with the scripts kept outside the repository (an AST walk over string, number, and collection literals), each over every `.py` file under `src/straightjacket/` unless noted.

| Pass | Query | Hits |
| --- | --- | --- |
| 2a | string literals (f-strings as one) with two words joined by space or punctuation | 603: 234 in log calls, 185 in raise statements, 184 other |
| 2a | string literals with an XML tag and no two-word run | 55 |
| 2a | string literals with two or more words split by placeholders only | 105 (31 other) |
| 2a | f-strings with one word of three or more letters | 115 (98 other) |
| 2a | string literals that are one capitalised word | 5 |
| 2a | `web/static`: two-word runs; `textContent`, `innerHTML`, `title`, `aria-label` assignments of literals; `\|\|` and `??` literal fallbacks | 297; 1; 1 |
| 2b | int and float literals other than 0, 1, and bools, in `mechanics/`, `npc/`, `game/`, `ai/` | 83 |
| 2c | dict literals with string keys and string values; set, tuple, and list literals of two or more strings | 227 |
| 2c | dict literals with string keys and number values | 4 |
| 2d | annotated assignments with a value in `@dataclass` classes | 266: 197 defaults, 69 empty collections |

Log calls and raise messages were read as a class: exception text reaches the player only as `strings/error.yaml` keys (`web/handlers.py` → `_error_text`), and logs reach the developer and Elvira's report, so neither is text a player, the narrator, or an AI reads. The one exception, a tool error returned to the Director, is P2-15.
