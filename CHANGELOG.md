# Changelog

Straightjacket — AI-powered narrative solo RPG engine. See [ORIGINS.md](ORIGINS.md) for where it comes from.

This log holds the releases of the step in progress (roadmap.md, NEXT STEP). When a step closes, its entries leave: DONE in roadmap.md keeps its summary, and git keeps every release, under the version its commit's title carries (`git log --grep <version>`, or `git log -p CHANGELOG.md` for the entries as they stood).

## Versioning

Calendar versioning: `YYYY.MM.DD.N`, where `N` is a zero-based counter for releases on the same day.

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
