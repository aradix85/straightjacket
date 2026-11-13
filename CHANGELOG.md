# Changelog

Straightjacket — AI-powered narrative solo RPG engine. See [ORIGINS.md](ORIGINS.md) for where it comes from.

This log holds the releases of the step in progress (roadmap.md, NEXT STEP). When a step closes, its entries leave: DONE in roadmap.md keeps its summary, and git keeps every release, under the version its commit's title carries (`git log --grep <version>`, or `git log -p CHANGELOG.md` for the entries as they stood).

## Versioning

Calendar versioning: `YYYY.MM.DD.N`, where `N` is a zero-based counter for releases on the same day.

## [2026.11.13.2] — 2026-11-13

The rule for finished work, sharpened at the user's request, whose standing way of working it is: what is finished goes under DONE at the bottom of the roadmap, cut to its essence, only what a later session may still need, so that what belongs together stands together (CLAUDE.md, Always). DONE gains the line of the work that moved the sessions to Claude Code, as 9z.

Quality gate: 2018 tests, coverage 96.22% to 96.23%, mypy clean on 271 files, pylint clean, ruff clean on every rule outside the ignores. Save format unchanged. No Elvira run: nothing the game does changes.

## [2026.11.13.1] — 2026-11-13

The documents, at the user's request: the sessions now work in Claude Code on the user's laptop, in the project's folder itself, where they worked in a cloud session's clone and pulled every push to the laptop.

- **CLAUDE.md is new**, the file Claude Code hands every session at its start. It holds what the roadmap said of the sessions, Always and Sessions with the user, which now says where the work happens, with the gate's tools in `.venv`; the references to those sections follow. The roadmap keeps the order of work, so that a sub-agent handed CLAUDE.md does not carry the steps. The document scans of `tests/_rules_docs.py` read CLAUDE.md like the other root documents.
- **AGENTS.md says which kind of sub-agent Claude Code starts:** a general-purpose agent, on the model its work asks, since an Explore agent can write no file and so could keep no progress file. CLAUDE.md imports AGENTS.md, since Claude Code reads an AGENTS.md by itself only where no CLAUDE.md stands.

The gate, green on Linux, found two things on Windows, both fixed so that it is clean on either:

- mypy called the last line of `run.py` → `_venv_python` unreachable, since on Windows the platform check before it always returns; the function now picks the path in one expression.
- pylint, whose parallel jobs infer more on Windows, asked two asserts of `tests/test_clock_creation.py` to test an empty list by its truth, as they now do.

Quality gate: 2018 tests, coverage 96.21%, mypy clean on 271 files, on Windows and with `--platform linux`, pylint clean, ruff clean on every rule outside the ignores. Save format unchanged. No Elvira run: nothing the game does changes.

## [2026.11.13.0] — 2026-11-13

The request of an AI call in real types, the first half of roadmap 9y.3e. A call's schema, messages, tools, and the request each adapter hands its SDK were `Any` at every depth, so mypy held none of it against the SDKs. Each adapter now builds its request as its SDK's own parameter type and reads the answer as the SDK's answer type (`docs/ai.md`, Provider adapters).

- **What the Anthropic adapter routes from a cluster's `extra_body` is checked.** `output_config`, `cache_control`, and `thinking` go to typed parameters, so they are held, strictly, against the installed SDK's types where the adapter reads them: a key or a value those do not know, a null among them, fails the call, and the log names it, as in `extra_body.output_config: efort: Extra inputs are not permitted`, where it went to the API and came back as an error. The rest of `extra_body` passes as it did. pydantic, which both SDKs bring, does the check and is a dependency of its own now. A checked value goes out with its keys in the SDK's order, which is the same JSON.
- **The OpenAI-compatible adapter refuses a tool call that calls no function or whose arguments are no JSON object**, where the first failed on an attribute it lacks and a list or a null reached the tool's handler.
- **A tool's definition is a dataclass**, `tools/registry.py` → `ToolDefinition`, from which each adapter builds its SDK's shape, where the registry held OpenAI's.
- **A call's sampling values are one object**, `AICallSpec.sampling`, where the spec repeated the five fields `sampling_params` returns; pylint found the repeat once their types matched.
- A message is a `Message`, a schema a mapping of objects, and the roadmap splits 9y.3e: the answers remain.

Measured: a script sent 7,040 calls through the real SDK clients on a mock transport under the old code and the new (both adapters, with and without streaming, every schema, tools, cache prefix, sampling values, and seven shapes of `extra_body`): every HTTP body, read as JSON, and every parsed answer alike, on the locked SDK versions and on the lowest the project allows (anthropic 1.8.0, openai 3.19.0, pydantic 2.13.0), on which the adapters' tests pass too. mypy's `disallow_any_explicit` finds 341 errors where it found 396. Quality gate: 2018 tests, coverage 96.22%, as it was, mypy clean on 271 files, pylint clean, ruff clean on every rule outside the ignores. A sub-agent checked the release; what it found is fixed, and the new refusal of a null, in a routed key or as a tool call's arguments, stands as intended. Save format unchanged. No Elvira run: with the shipped configuration every request is as it was.

## [2026.11.12.2] — 2026-11-12

Datasworn and the settings yaml read with their values checked, the rest of roadmap 9y.3d. A Datasworn file was handed through the engine as loaded, `Any` at every depth: a move, an asset, a truth, or a meter was a dict read by its keys wherever it was used. Datasworn is an external structure with far more than the engine reads, so it is not bound whole; each value the engine reads now goes through `serialization.py` → `read_key`, which refuses another type than the one asked and names the value by its path, as in `classic.moves.adventure/face_danger.allow_momentum_burn: expected bool, got str` (ARCHITECTURE.md, Typed binding).

- **Assets, truths, and an oracle row's roll instructions are dataclasses** (`Asset`, `Truth`, `OracleRoll`), parsed where a setting or a rules file is made, where the ruleset, the page, and Elvira each read the raw dicts.
- **The rules a ruleset's readers take** (stats, meters, impacts, special tracks) and the moves are checked value by value where they are parsed.
- **A setting's yaml:** `oracle_paths`, `vocabulary`, and `creation_flow` are bound by the reader that binds the configuration, so a flag that is no boolean, a path that is no text, or a key written without a value stops the load, where a flag was coerced and a path taken as it came. One `_require` replaces three copies, one `_first` the four pickers along the chain of parents, and the partial classes lose their defaults and their carve-out in the no-defaults scan, since the binding fills in what a yaml leaves out.
- The list of saves reads its header fields through `read_key` too, and `shaped` no longer takes a boolean for a whole number.

Measured: a script held the old code against the new for all four settings: the creation options the page gets, every move, meter, stat, impact, and legacy track, every oracle table with its roll instructions, 4,672 seeded oracle rolls, the roll bonuses of a character with twelve assets, and 240 asset advances: all alike. mypy's `disallow_any_explicit` finds 396 errors where it found 435. Quality gate: 2003 tests, coverage 96.19% to 96.22%, mypy clean on 271 files, pylint clean, ruff clean on every rule outside the ignores. A sub-agent checked the release; what it found is fixed, but for a rules file parsing its assets each time it is made, which stands. Save format unchanged. No Elvira run: the shipped files read as they did.

## [2026.11.12.1] — 2026-11-12

Mythic's and the Adventure Crafter's data files bound to dataclasses, the first half of roadmap 9y.3d. Both files were handed out as loaded, `Any` at every depth, and each table was read by its keys where it was rolled. The reader that binds the configuration now binds each file whole at its first use, to `gamemaster/mythic_data.py` → `MythicData` and `crafters/adventure_crafter.py` → `AdventureCrafterData`, so a value of another type than its field's, a missing table, or a table the engine does not know stops the load and names its path, as in `adventure_crafter.json.plot_points[0].themes.action.max: expected <class 'int'>, got '8'` (ARCHITECTURE.md, Typed binding).

- The eleven tables of Mythic that no code reads yet are fields held as they are; the step that comes to read one gives it its type.
- The reader takes a field that names several plain types: an Adventure Crafter theme priority is a number or the text `4_or_5`.
- The weighted choice among threads or characters names those two lists, where it took a list of anything.
- The roadmap splits 9y.3d: Datasworn and the settings yaml remain.

Measured: a script held every lookup of both files under the old code against the new, and 27,720 seeded rolls of fate, event focus, meaning, scene adjustment, character traits, and turning points: all alike. mypy's `disallow_any_explicit` finds 435 errors where it found 444. Quality gate: 1978 tests, coverage 96.09% to 96.13%, mypy clean on 271 files, pylint clean, ruff clean on every rule outside the ignores. A sub-agent checked the release; what it found is fixed. Save format unchanged. No Elvira run: every table reads as it did.

## [2026.11.12.0] — 2026-11-12

Saves read by the reader that binds the configuration, roadmap 9y.3c. A dataclass was read from plain data in two ways: the saves by `deserialize`, which checked the names of the fields and never their values, and the configuration by the binder, which checks both. One reader, `serialization.py` → `build_strict`, now serves both, and `config_binding.py` is gone. **Saves from before this release no longer load**, since two of the changes below alter the save format; the player is told the save is incompatible.

- **A save with a value of another type than its field's is refused** as incompatible, where text for a number loaded and failed wherever it was first used. The whole file is read as one dataclass, `persistence.py` → `SavedGame`, so a file that lacks its game or its chat is refused the same way, and the log names the value by its path, as in `Kael/autosave.game_state.narrative.scene_count: expected <class 'int'>, got 'three'`.
- **The turn's snapshot holds dataclasses**, copied from the state, where it held plain dicts that only a restore read back: a snapshot in a save is checked when the save loads. A snapshot's JSON is as it was.
- **A chat message is a dataclass**, `ChatMessage`, with its epilogue mark always written, where the mark was a key only an epilogue had; this alters the save format. The entries of the list of saves are `SaveInfo`, whose header fields are checked for their types.
- **A consequence keeps its texts and its numbers in two mappings**, where one mapping of any value held both; this alters the save format too.
- **The Brain's answer** is read by the same reader, so an answer with a value of another type than its field's fails the turn, which rolls back, where it entered the state. An answer that follows the Brain's schema reads as it did.
- Gone with their tests: the two checks that a value handed to the writer or the reader is a dataclass, which mypy now holds.

Measured: a script played 60 games of six turns on the mock provider under the old code and the new, each with a turn undone, the turn's snapshot restored, and a save loaded and restored: all 540 saved states alike, but for the two mappings of their 3392 consequences. mypy's `disallow_any_explicit` finds 444 errors where it found 486. Quality gate: 1974 tests, coverage 96.05% to 96.10%, mypy clean on 271 files, pylint clean, ruff clean on every rule outside the ignores. A sub-agent checked the code and another the documents; what they found is fixed, and what they left open stands under roadmap 9y.3e. No Elvira run: a turn plays as it did, but for a Brain answer its schema does not allow.

## [2026.11.11.2] — 2026-11-11

The loaders typed and the stores loaded at startup, the rest of roadmap 9y.3b.

- **`config.yaml`** is bound by the same binder as the stores, in place of a parser of its own that checked the names of the keys and converted the values. A value of another type than its field's now stops the start: a quoted number, which was converted without a word, text for `stream_narration`, which counted as true, or a list for `extra_body`. The checks across sections stay: a cluster's provider, the eight roles, and each role's cluster. The messages name the value by its path, as in `config.yaml.ai.clusters.narrator: missing keys ['model']`.
- **At startup** `python run.py` and Elvira call `game/startup.py` → `check_startup`, which loads the four stores before it checks the configured models, so a wrong value in their yaml stops the start with its message and not the turn that first reads the store. `run.py` reports a yaml file that does not parse, or a folder that is missing, the same way, where it showed a traceback.
- **The emotions** are bound to `EmotionSettings`; `yaml_merge.py` hands on `object` and refuses a top-level key that is not text; the sampling parameters of a role are a typed mapping.
- A sub-agent checked the release; what it found is fixed. The prompts, the strings, and the emotions still load at their first use (ARCHITECTURE.md, Configuration).

Measured: mypy's `disallow_any_explicit` finds 486 errors where it found 497. Quality gate: 1952 tests, coverage 96.07% to 96.11%, mypy clean on 273 files, pylint clean, ruff clean on every rule outside the ignores. Save format unchanged. No Elvira run: the shipped `config.yaml` and emotions read as they did, but for the providers' `timeout_seconds`, which stays the whole number the file holds.

## [2026.11.11.1] — 2026-11-11

Every yaml block a typed field, roadmap 9y.3b, the raw sections. Nineteen blocks of `engine/`, `gamemaster/`, and `ruleset/` were read through `get_raw`, which handed out `Any` and checked nothing. Each is now a field of its store's settings class, bound and checked at load like the rest, so `RawSections` and `get_raw` are gone, and at the top level too a key no field holds, or a field without its key, stops loading (ARCHITECTURE.md, Configuration).

- The move outcomes are parsed by hand into `MoveOutcomeConfig` (`ruleset/config.py`): the lists of effects by their key, the two optional texts, and the parameters of the entry's handler as a dataclass of their own, `SufferParams`, `ThresholdParams`, `RecoveryParams`, or `SojournParams`, which also picks the handler (`ruleset/move_outcome.py` → `_apply_handler`). An unknown handler, which failed the turn that met it, now stops loading. The three suffer entries no turn reaches yet (Withstand Damage and the two companion moves, roadmap step 19) name the three parameters they lacked, as none.
- The oracle moves and the rows of a move's table are dataclasses; the other blocks are mappings and lists of text and numbers. A section parsed by hand is handed to the binder as its parser, so the binder's checks of the keys come first and every error carries its path.
- With `get_raw` gone, its scan and the orphan scan's reading of it are gone, and the consumers lost the local annotations that typed what it returned. Two literal fallbacks in files the release touched are gone: the Brain's trigger hint and a test's `other` category.
- Found on the way, for roadmap 9w.1: a scenario's threat is lost when creation already holds as many emergent threats as the cap allows, 5 creations in 1500, which failed one test in one run of the suite.
- A script held the old settings against the new: 3797 values alike, and all 64 move outcomes rebuild to their yaml. A sub-agent checked the release; what it found is fixed, and the roadmap's 9y.3b keeps the loaders.

Measured: mypy's `disallow_any_explicit` finds 497 errors where it found 527. Quality gate: 1942 tests, coverage 96.08% to 96.12%, mypy clean on 272 files, pylint clean, ruff clean on every rule outside the ignores. Save format unchanged. No Elvira run: the settings hold the values they held, so nothing the game does changes.

## [2026.11.11.0] — 2026-11-11

The configuration bound by its annotations, roadmap 9y.3a, the first area of "no explicit `Any`". The four yaml stores were bound to their dataclasses by hand-written functions, one per section, that checked the names of the keys and never the values, so text where a number belongs loaded and failed wherever it was first used. One binder, `config_binding.py` → `bind_sections`, now reads the annotations of each settings class and of every dataclass below it and checks each value's type at every depth, naming a wrong value, an unknown key, or a missing key by its path in the yaml (ARCHITECTURE.md, Configuration). The shipped yaml held no wrong value: a script that loaded the four stores with the old code and the new found their 1976 values alike.

- The hand-written binders of `gamemaster/config.py`, `ruleset/config.py`, `crafters/config.py`, and `engine_config.py` are gone, some 270 lines. Only the move availability rules, whose yaml shape is not their dataclass's, are still parsed by hand, now with their values checked: a position written as text was split into its letters, and any `never` that read as true passed. The two checks of the fact types stay, after the binding.
- `fate.likelihood_rules.score_to_odds` is a list of `OddsThreshold` and the engine's default texts a mapping of text, the two config fields that were typed `Any`; the clock's keyed scenes are a mapping on the settings, without the class that only wrapped it; `RawSections` holds the raw data as its own field, without a default. The binder and the saves share their shape check (`serialization.py` → `shaped`).
- `tests/test_config_loader.py` hands the `src` folder to the fresh process it starts, which found the package only where it was installed. CONTRIBUTING.md names how the gate's tools are installed.
- The roadmap splits what remains of 9y.3 by area, 9y.3b to 9y.3g. A sub-agent checked the release; what it found is fixed.

Measured: mypy's `disallow_any_explicit` finds 527 errors where it found 557. Quality gate: 1930 tests, coverage 96.02% to 96.07%, mypy clean on 272 files, pylint clean, ruff clean on every rule outside the ignores. Save format unchanged. No Elvira run: the bound settings hold the values they held, so nothing the game does changes.

## [2026.11.10.0] — 2026-11-10

pylint's duplicate code and module length at their default limits, roadmap 9y.2: `duplicate-code` and `too-many-lines` are on, where pylint found 26 blocks copied between files and one module over 1000 lines.

- The openings of a new game, a chapter, and a succession share `game/setup_common.py` → `generate_opening` (`docs/story.md`, Blueprint); the chapter's voicing no longer reads a shallow copy of the game, which neither call writes to. The action and dialog prompts take their shared fields from `prompt_shared.py` → `_scene_fields`, and a script running the old and new builders side by side over the suite found all 248 prompts alike.
- Elvira's runners share their run state and session log, and her unused `final_state_dict` (roadmap 9w.1) is gone with its test. Copied test set-ups are helpers in `tests/_helpers.py` and `tests/_creation.py`, and the config tests read the roles from `config.yaml` instead of copying the engine's list.
- `tests/test_project_rules.py` stays the one test of every scan, which now live by kind beside it (CONTRIBUTING.md, Testing). Three sub-agents checked the release; what they found is fixed.

Quality gate: 1912 tests, coverage 96.03% to 96.07%, mypy clean on 272 files, pylint clean, ruff clean on every rule outside the ignores. One run of the suite failed one test whose name it did not show; the thirteen runs after it passed, which fits the test with unfixed rolls that roadmap 9w.1 names. Save format unchanged. No Elvira run: every prompt of a turn reads as before, and the openings make the same calls in the same order.

## [2026.11.07.1] — 2026-11-07

The two functions that 2026.11.07.0 left with more than 15 locals besides their arguments are split too, at the user's request, while pylint's count of locals stays off, since it counts the arguments, whose number the user left free. `ai/blueprint_voicing.py` → `call_blueprint_voicing` asks the AI through `_ask_voicing`, which holds the call and the reading of its answer, so an answer it cannot read still degrades to no blueprint, now tested for an answer that is no JSON, no object, or lacks a field; `gamemaster/npc/memory.py` → `retrieve_memories` scores each memory through `_score_memory`, `_relevance`, and `_words` instead of a closure. Nothing the game does changes: a script found old and new memory retrieval alike on five hundred random cases. A sub-agent checked the release.

The documents, at the user's request: the CHANGELOG now holds only the releases of the step in progress, and a closed step's entries leave it (CONTRIBUTING.md, Workflow step 6), since DONE keeps its summary and every commit's title its version; and the roadmap's DONE is cut to what a later session needs, with what was done moved out of the open steps.

Quality gate: 1913 tests, coverage 96.04% to 96.06%, mypy clean on 267 files, pylint clean, ruff clean on every rule outside the ignores. Save format unchanged. No Elvira run: nothing the game does changes.

## [2026.11.07.0] — 2026-11-07

Complexity at the default limits, roadmap 9y.1: ruff's mccabe complexity (10), too many branches (12), locals (15), return statements (6), and statements (50) leave the later groups, and pylint leaves its own four to ruff, at the same limits, the user's choice. ruff's count of locals leaves out the arguments, whose count the user left free, and loop and `with` targets, so pylint's would still flag 25 functions, two of them (`ai/blueprint_voicing.py` → `call_blueprint_voicing`, `gamemaster/npc/memory.py` → `retrieve_memories`) over 15 even without their arguments. With mccabe at 10, the project-rule scan of a complexity of at most 20 is gone, with its radon dependency and the stub in `stubs/`.

- In `src/`, twelve functions are split into named steps, with nothing the game does changed: the Brain's prompt and choices, the metadata request, the correction of the state, a turning point's plot points, the Director's reasons, the engine's memories, the NPC activation's TF-IDF, the start of a track and the progress, legacy, and experience a move marks, deserialization, and the creation options. Which template a consequence takes and which of its values it tells about is one table in `ruleset/consequences.py`, now pinned row by row by a test; a move effect is parsed from a table of patterns, without the `fill_clock` pattern, which the generic one already matched alike; and a save's shape is checked by one helper with the same messages. Scripts held the old functions against the new: every effect string in the ruleset's yaml, every consequence kind, and three hundred random activations came out alike.
- In the tests, the longest project-rule checks are split by what they check, and the Director test's schema helper reads a table that raises on a type it does not know.
- Elvira's two main loops are steps around a run object, and her WebSocket runner now takes from the direct one its settings (with no scenario, which only direct mode plays), when a turn is a correction, the burn decision, the checks after a turn, the logs, and the count of burns, now read from the turn records; her other long functions are split the same way, and her two entry points no longer have defaults that only the tests left unset. A WebSocket chapter that ended on an error recorded its end as unknown and now records an engine error, as direct mode does (tested). In WebSocket mode the log lines read as direct mode's, and when the game state is lost or a chapter fails to start, the summary shows the last known state.
- Two sub-agents checked the release, one for the engine and one for Elvira; what they found is fixed.

Quality gate: 1912 tests, coverage 96.05% to 96.08%, mypy clean on 267 files, pylint clean, ruff clean on every rule outside the ignores. Save format unchanged. No Elvira run: nothing the game does changes, and her smoke tests play both rebuilt runners.

## [2026.11.06.8] — 2026-11-06

pylint beside ruff and mypy, at the user's request, and the request in the roadmap. pylint is pinned at 4.1.3 in the test extra and runs its default checks from the pre-commit hook and the quality gate (CONTRIBUTING.md, Workflow step 3) over the same paths as mypy, at ruff's line length. `[tool.pylint."messages control"]` leaves out, each with its reason, the docstring checks the project rules forbid, what clashes with the dataclass models or with the tests' list unpacking, the argument count the user left free, and the broad except and the imports that ruff checks with its carve-outs; its complexity checks wait with ruff's, and its duplicate code and module length are later groups.

- What pylint found beyond ruff: 76 test asserts that compared a typed list or dict with an empty one test it through truth, as the tests do with an empty string; the models restore their fields through `dataclasses.fields`; `consequence` calls its positional-only parameter `consequence_kind`, so that a value passed as `kind` reads as one; a parameter, a local in two tests, and loop variables in a third no longer shadow a module-level name, and the tests' own fixtures take their names through `name=`, so pylint's check of shadowed names stays on; and five smaller rewrites (`isdisjoint`, `types.NoneType`, a loop over letters, a `maxsplit`, needless parentheses).
- The web tests get a fresh session through `monkeypatch`, which restores the server's own afterwards, where two copied methods reset the shared session by hand and kept it on the test class; the players' folder moves to a temporary one through a fixture of its own.
- The roadmap holds the request as step 9y, now NEXT STEP ahead of step 18, which keeps its content: what is done under DONE, and as substeps the complexity at the default limits, pylint's duplicate code and module length, the typing that bans `Any`, pyright last, and pylint's optional extensions for the user to choose among.

Quality gate: 1896 tests, coverage 96.04% to 96.05%, mypy and pylint clean, ruff clean on every rule outside the ignores. Save format unchanged. No Elvira run: nothing the game does changes.

## [2026.11.06.7] — 2026-11-06

Positional arguments, the eighth step of the user's request: ruff's rule on more than five positional arguments leaves the later groups, at its default limit. The rule on more than five arguments in all is ignored for good, the user's choice, since keyword-only arguments name themselves at every call; a factory such as `new_npc` names every field it fills, as dataclass fields have no defaults (CONTRIBUTING.md, Code standards).

- The narrator's two prompt builders take the scene they write in, the player's words, the scene setup, and the activated and mentioned NPCs, as one `PromptScene`, and what the turn told besides the move's result, its random events, threat events, filled clocks, NPC agency, and revelation, as one `TurnEvents` (`prompt_shared.py`). The turn keeps the `PromptScene` in its `SceneContext`, which no longer holds the ids of the prompt's NPCs beside it (`PromptScene.npc_ids`), hands the same `TurnEvents` to the prompt and to the snapshot, and a correction builds the `TurnEvents` from the snapshot.
- The NPC fuzzy match's checks read their thresholds from the configuration where they use them (`gamemaster/npc/matching.py`); the other functions with more than five positional arguments, in `src/` and in Elvira, take the rest by keyword. Elvira's turn helper no longer has defaults its one caller always overrides, and three helpers of her WebSocket runner and one of her direct runner no longer take an argument they never used. The tests build the brain's schema through `tests/_helpers.py` → `brain_schema`.

Quality gate: 1896 tests, coverage 96.06%, mypy clean on 267 files, ruff clean on every rule outside the ignores. Save format unchanged. No Elvira run: nothing the game does changes and every prompt reads as before, mypy checks every changed call, and her smoke tests play both her runners.

## [2026.11.06.6] — 2026-11-06

Module state and private access, the seventh step of the user's request: ruff's rules on the `global` statement, access to a private member, too many public methods, and too many boolean expressions leave the later groups.

- The loaders of `config.yaml`, the yaml stores, the prompts, the strings, the emotions, and the Mythic and Adventure Crafter data keep what they loaded in a dict keyed by the path they read, no longer in a global they rebind, and Elvira's prompts likewise; the game master's installed ruleset answers are a one-place list (`gamemaster/questions.py` → `install_answers`). A test that points a loader at another file or folder now gets that file's content without clearing the cache, so those resets are gone.
- `load_engine`, which reinstalled the real configuration before every test, is gone with its helper, since each test that changes the configuration restores it through `monkeypatch` and the suite passes without it; `tests/_helpers.py` → `change_config` finds the layer's folder from its module.
- A setting package reads its ancestors through their public `config` and `data` and walks its chain through its own parent (`setting/packages.py` → `SettingPackage.chain`). No test reads or sets a private attribute any more, though `monkeypatch` still sets private names by their string: the reconnect after a game over connects through the server's WebSocket, the broken tool replaces the registry, and the settings folder is named from the project root.
- The Starforged move tests split their checks of the whole move set into a class of their own; two project-rule checks read a constant assignment and a `getattr` name with fewer conditions.

Quality gate: 1896 tests, coverage 96.08%, mypy clean on 267 files, ruff clean on every rule outside the ignores. Save format unchanged. No Elvira run: nothing the game does changes.

## [2026.11.06.5] — 2026-11-06

Numbers, booleans, and console output, the sixth step of the user's request: ruff's rules on magic numbers, boolean arguments, comparing with an empty string, membership in a literal, and `print` leave the later groups.

- Numbers in `src/`: the gate levels at which the narrator learns an NPC's agenda, instinct, and secrets are `information_gate.reveals` in `gamemaster/information_gate.yaml`, and the longest player or save name is `persistence.max_name_length` in `engine/persistence.yaml`, both rules of the engine that the code held (`docs/gamemaster.md`, Information gating); the other checks read as "more than one", split a trigger value with `partition`, match a scene range as a pair, and refuse a name character below the space. The tests compare with plain numbers, the user's choice.
- Every boolean parameter is keyword-only and its callers name it. The move-outcome dispatcher calls each handler with what it reads: the suffer and threshold handlers no longer take the roll's match, nor the threshold and recovery handlers the move key (`ruleset/move_outcome.py` → `_dispatch_handler`).
- Elvira writes her console output through the `elvira` logger (`elvira_bot/console.py` → `say`), which her script shows on the console, and `run.py` and `data/data.py` through loggers of their own; what appears is unchanged.
- The tests compare with an empty string through truth, and test membership in a set, ruff's rewrite; the judge's tests call the judge module they import, so mypy now checks those calls, which found the five calls whose keyword arguments a helper typed as a module had hidden.

Quality gate: 1896 tests, coverage 96.07%, mypy clean on 267 files, ruff clean on every rule outside the ignores. Save format unchanged.

## [2026.11.06.4] — 2026-11-06

Unused arguments and self, the fifth step of the user's request: ruff's rules on unused arguments (ARG), methods that never use `self`, and underscored names that are used leave the later groups.

- `load_engine`, which 922 tests asked for only to install the real configuration, runs for every test from `[tool.pytest.ini_options]` `usefixtures`, and the tests no longer name it; the other fixtures a test needs only for what they set up are named in `pytest.mark.usefixtures`.
- An argument a function must take but does not read starts with an underscore: the effect and move handlers that share one signature in `ruleset/move_effects.py` and `ruleset/move_handlers.py`, and the tests' fakes; a fake the engine calls by keyword takes the arguments it ignores as `**_kwargs`.
- A method that never reads `self` is a static method: the provider adapters' request and response builders and the test methods in classes; the two identical `client` fixtures of `tests/test_web.py` are one at module level.
- A local name that starts with an underscore but is read lost the underscore, ruff's own rewrite; three that then shadowed or misnamed another value have names of their own (`tfidf_cfg` in `gamemaster/npc/activation.py`, `weights` in `gamemaster/npc/memory.py`, `texts` in `ai/brain.py`). Two test modules that still marked `load_engine` no longer do.

Quality gate: 1896 tests, coverage 96.09% to 96.13%, mypy clean on 266 files, ruff clean on every rule outside the ignores. Save format unchanged. No Elvira run: nothing the game does changes.

## [2026.11.06.3] — 2026-11-06

Exception messages, the fourth step of the user's request: ruff's rules on how an exception is raised (EM, and TRY003 on long messages) leave the later groups. Every message is built in a variable before the `raise`, ruff's own rewrite, in `src/`, the tests, and Elvira.

- Each message takes a statement of its own, so an error path no test reached counted twice and coverage fell to 95.58%. New tests reach those paths instead of the floor moving: the yaml directory loader's four refusals (`tests/test_yaml_merge.py`), a setting yaml of the wrong shape and a missing setting (`tests/test_setting_package_errors.py`), serializing or loading what is not a dataclass or an object (`tests/test_serialization_errors.py`), an unknown odds level or chaos factor for both fate methods, a missing or non-mapping config file and a role without a model, move-availability rules of the wrong shape, an unknown meaning table, an oracle table without rows or with a gap, a missing Datasworn file, and crafter themes that disagree with the data.
- The Adventure Crafter's data is cached only once it is validated; a second load after a refusal returned the data unchecked (tested).
- `deserialize` takes its data as `object`, since it comes straight from JSON and the check that it is a mapping is what refuses anything else; typed as a dict, mypy found that check unreachable once its branch held more than the raise.

Quality gate: 1896 tests, coverage 96.08% to 96.09% over four runs, mypy clean on 266 files, ruff clean on every rule outside the ignores. Save format unchanged. No Elvira run: no message of the game changes, and the cache fix only matters once the data has been refused.

## [2026.11.06.2] — 2026-11-06

Imports at their strictest, the third step of the user's request. Every import stands at the top of its file and is absolute (`ban-relative-imports = "all"`), and an import used only in annotations stands under `TYPE_CHECKING`, in ruff's strict mode, with `SerializableMixin` declared as read at runtime, since `deserialize` resolves the models' annotations.

- The user's choices: the two provider adapters are imported at the top of `ai/api_client.py`, so both SDKs load at start where they loaded only once configured; the ruleset's answers are installed when the server starts (`web/server.py` → `_lifespan`) and when Elvira starts a direct session, no longer when the game package is imported (`docs/gamemaster.md`, Questions to the ruleset), tested for both; Elvira's script keeps its path setup ahead of its imports, the one file allowed so.
- `run.py` keeps its imports inside the function that runs once the virtual environment exists, since the system Python that first starts it has none of the dependencies; it is the one other file allowed so.
- The three imports kept inside functions to break a cycle are at the top; no cycle remains. With ruff holding every import to the top, the project-rule scan of inline imports, its whitelist, and CONTRIBUTING.md's exception for an inline import are gone, as is the import-layer scans' reading of relative imports.
- In the tests, the 1167 imports inside test functions are at the top of their files. `tests/conftest.py` no longer swaps `logging_util` out of `sys.modules` ahead of every import, but gives the `rpg_engine` logger a null handler, and pytest puts `src/` on the path; a test that patched `api_client.get_provider` patches it where Elvira's WebSocket runner holds it; the server's one session is `active_session`, which the tests reset, no longer a private name they import.

Quality gate: 1866 tests, coverage 96.16%, mypy clean on 263 files, ruff clean on every rule outside the ignores. Save format unchanged.

## [2026.11.06.1] — 2026-11-06

ruff at its strictest, the second step of the user's request: ruff is pinned at 0.17.4 in the test extra and the pre-commit hook (which pinned 0.15.12), runs its preview rules, and selects every rule. `[tool.ruff.lint]` ignores, each with its reason, only the rules that clash with a project rule or with ruff format (docstrings, the copyright comment, two formatter clashes, `dict.get` with a fallback, the dice's `random`), plus the groups later releases take up one at a time; selectors are rule names, as preview asks. Assert is allowed only in tests, a broad except only in the AI-call carve-out files, and starting a process in `run.py`, and, pending the user's choice, in the two tests that run ruff and a fresh interpreter. Of the old ignores the long lines are split, the ternaries and loops follow ruff, and the per-file ignores of unused imports are gone, which hid the dead import of `eng` in `models.py`; `dict.get` with a fallback stays ignored, and imports after setup code join the later groups. An import after setup code in Elvira's script, and `game/__init__.py` installing the ruleset's answers, wait with the inline imports for a decision of the user.

- In `src/`: an assert becomes an error that says what is missing, and a Brain answer that swears a vow without its rank now fails the turn with that error (`ruleset/tracks.py`, tested through a turn); a file or section of the configuration that is not a mapping raises `TypeError` (`config_loader.py`, `yaml_merge.py`), which `run.py`'s startup check reports like the others; `new_npc` and `new_track` take `npc_id` and `track_id`, not the builtin's name; every save and load of the web handlers runs in a thread, with what it writes taken on the event loop, so a save no longer blocks the server for the other connections (`web/handlers.py`).
- The AI call sites log and return after their `except`, with every read of the answer still inside the `try`, so a malformed answer still falls back as before (`ai/narrator.py`, `correction/analysis.py`, `director.py` → `_parsed_guidance`).
- Tests and Elvira: the fixtures that ran for every test are named in `[tool.pytest.ini_options]` `usefixtures` and in marks instead of `autouse`; `tests/test_prompt_xml.py` parses through `defusedxml`, a new test dependency; Elvira's WebSocket client takes no timeouts, which its callers set with `asyncio.timeout`, and its drain waits for a quiet period named as such. `data/data.py` names its sources as paths on the one host, writes the scheme into the request, and opens it through an opener that knows only HTTPS, with proxies and redirects handled as before; tried against both sources. A test that repeated the scan for dataclass defaults is gone.

Quality gate: 1865 tests, coverage 96.09%, mypy clean on 263 files, ruff clean on every rule outside the ignores. Save format unchanged.

## [2026.11.06.0] — 2026-11-06

mypy at its strictest, at the user's request, as a first step: strict mode plus every check mypy leaves off by default (its thirteen optional error codes, `warn_unreachable`, `strict_bytes`, `strict_equality_for_none`, `local_partial_types`, `disallow_any_unimported`, and `disallow_any_decorated`) apart from the two that ban `Any`, `disallow_any_explicit` and `disallow_any_expr`, which later steps take up with the typing of the yaml and JSON data, over the tests, Elvira, `run.py`, and `data/data.py` as well as `src/`, where it found 541 errors. The pre-commit hook and CONTRIBUTING.md now run it on all of them.

- In `src/`: the Brain's stat retry is a `while` loop that refuses inside it, so the result and stats it reports are bound on every path (`ai/brain.py` → `call_brain`); the same calls go out, but a last wrong stat no longer logs the warning that it asks again, which was untrue, before the refusal; `from_dict` returns its own class instead of `Any`, through a generic `deserialize` (`serialization.py`); an override carries `@override`, from `typing_extensions`, now a dependency since Python 3.11 lacks it.
- What it found in the tests: annotations left from when consequences were strings (`tests/_helpers.py` → `record_price_tables`, `tests/test_progress_results.py`, Elvira's `_handle_burn`, which returns the Director call); a dead branch in Elvira's recorder, `if not dg` on guidance that is always true; fake providers without the protocol's `stream_message`, now built on one `ScriptedProvider`; and three copies of a fake WebSocket that was not one, now `RecordingWebSocket`, a real Starlette WebSocket, so the handler tests also run the JSON encoding (CONTRIBUTING.md, Testing).
- The test factories return their types instead of `Any`; a test that reached a name through a module that only imports it now takes it from the module that defines it, and patches the dice through a dotted path; radon has a stub in `stubs/`; the two `[tool.mypy]` overrides, which no longer suppressed anything, are gone.
- `tests/test_providers.py` imports the SDKs it holds the adapters against, where it reached them through the adapters' own imports, which strict mode does not export; the provider-import scan allows that one test (`docs/ai.md`, Provider adapters).

Quality gate: 1864 tests, coverage 96.03% to 96.08% over the runs, mypy clean on 263 files. Save format unchanged.
