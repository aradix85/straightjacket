# The AI layer

Which AI roles exist, which model runs them, and how calls are routed, cached, streamed, and allowed to fail. Why the AI narrates and does not decide is in ARCHITECTURE.md.

## Roles

Every AI call carries its own role name (`AICallSpec.log_role`), and every role maps to one cluster in `config.yaml`.

- `brain` turns the player's input into a move, a stat, a roll bonus, a target NPC, a new track's name and rank, the undetermined facts the action or question turns on, and the boasts the player declares in a duel (`ai/brain.py` → `call_brain`). The game state is injected into its prompt, and its output schema offers only the available moves, the offered bonuses, the listed NPCs, the active tracks by id, and the fact types with the subjects each allows; `call_brain` refuses anything else, and an empty track name for a move that starts a track. The Brain names a fact; the engine decides it (`docs/mechanics.md`, Facts).
- `narrator` writes the prose, with conversation memory (`ai/narrator.py`).
- `narrator_metadata` reads the finished narration and extracts NPC data (new NPCs, renames, details, deaths), which `ai/metadata.py` applies to the game state.
- `opening_setup` extracts the NPCs, their first memories, the location, and the scene context from the opening of a new game, a chapter, or a succession; the opening clock and the time of day are the engine's (`docs/mechanics.md`).
- `revelation_check` decides whether a planned revelation has happened in the story (`ai/brain.py` → `call_revelation_check`).
- `recap` and `blueprint_voicing` write the player-facing recap and a setting-specific story blueprint from an Adventure Crafter seed (`ai/recap.py`, `ai/blueprint_voicing.py`). The chapter summary kept in campaign history is built by the engine (`docs/mechanics.md`, Chapters and succession).
- `director` writes NPC reflections after the turn (`director.py`).
- `correction` analyses a `##` correction (`correction/analysis.py` → `call_correction_brain`): a misread input, which the engine replays with the corrected input and the dice already rolled, or state operations.

The narrator writes pure prose; everything structured comes from separate calls with strict JSON schemas (`ai/schemas.py`). Why narration and extraction are separate calls is recorded in `docs/divergences.md`. Prompts live per role in `prompts/*.yaml` and are tuned for the models in use: switching models means re-tuning in place, not adding parallel variants.

## Model assignment

`config.yaml` names, under `ai.clusters`, each cluster's provider, model, and call parameters, in full even where clusters repeat each other, and maps every role to exactly one cluster under `ai.role_cluster`. The clusters are narrator, creative (blueprint voicing, recap), director, classification (brain, correction), judgment (revelation check), and extraction (narrator metadata, opening setup). `model_for_role(role)`, `provider_for_role(role)`, and `sampling_params(role)` are the only way to reach them; no module hardcodes a model. A `null` temperature or top_p is not sent, and an `api_base` of `""` means the SDK's default endpoint. A key is needed only for a provider in use; providers that are configured but unused stay, so that a cluster can move with a change of its `provider`, `model`, and `extra_body`.

The user prefers one model for every role: quality work goes through engine-side structure and prompt tuning, not a stronger model for a few scenes. Every cluster currently runs GLM 5.3 through Together at its lowest reasoning effort, `low`, where it honours strict JSON schemas and function calling. OpenAI's GPT-6 Luna needs reasoning effort `none` wherever a cluster sends a temperature or calls tools. Through OpenRouter, a cluster's `extra_body` pins one host with `provider: {order: [host], allow_fallbacks: false, require_parameters: true}`, since without the pin OpenRouter may route to a discounted, quantized, or schema-less host.

Two measures keep structured answers from running away. A JSON grammar allows any whitespace between tokens, and GLM 5.3 sometimes wrote carriage returns until the token limit, so every cluster's `extra_body` bans, through `logit_bias`, the tokens of its tokenizer that contain a carriage return (one list under the YAML anchor `no_carriage_return`). And `ai/api_client.py` → `_schema_in_prompt` appends the compact JSON schema (template `json_schema_instruction` in `prompts/blocks.yaml`) to the end of the last user message of every call with a schema, or to the system prompt if the last message is not plain user text, so the model sees what it must write; it goes last, so every cached prefix stays intact.

**Caching.** Hosts cache the longest identical prefix of a prompt, so prompts put their fixed text first and what changes per turn last: the narrator system prompt its fixed rules, then the blocks fixed for a game, then the character state; the Director its fixed task ahead of the scene. Every cluster sends `user: "straightjacket"` as a session-affinity key. OpenAI and Together cache automatically; Anthropic needs `cache_control` in the extra body. Both adapters report the cached share as `cache_read_tokens`, and the OpenAI-compatible adapter the reasoning share as `reasoning_tokens` where the host reports it; the `[TOKENS]` log line shows them.

## Routing and the startup check

`ai/api_client.py` → `get_provider` returns a routing provider that sends each call to the provider of its role's cluster, keyed on `AICallSpec.log_role`; a project-rule scan requires every AI call to set it. `python run.py` and Elvira call `check_configured_models` first: every cluster's model must appear in its provider's model list, or startup stops and names the missing model. It reads each OpenAI-compatible provider's `/models` with a plain request, because Together returns a bare list that the OpenAI SDK's model listing cannot parse.

## Provider adapters

The `AIProvider` protocol has two implementations, `ai/provider_anthropic.py` and `ai/provider_openai.py` (any OpenAI-compatible endpoint); nothing else imports a provider SDK. Both create their SDK client with `max_retries=0` and the provider's `timeout_seconds`, so `ai/provider_base.py` → `create_with_retry` is the only retry layer: it honours a `Retry-After` header, capped by `retry.max_retry_after_seconds` in `engine/retry.yaml`, and otherwise backs off exponentially. A refusal (Anthropic `refusal`, OpenAI `content_filter`) becomes the stop reason `refusal`, which is retried like a transient error. Only text reaches `AIResponse.content`, never reasoning; a host's reasoning text is kept apart for diagnostics. The OpenAI-compatible adapter sends `max_completion_tokens`, which OpenAI's own models require. The Anthropic adapter sends `temperature`, `top_p`, and `top_k` only when set, routes `cache_control`, `thinking`, and `output_config` from the cluster's `extra_body` to their typed parameters, and converts the tool loop's OpenAI-style messages into `tool_use` and `tool_result` blocks.

## When an AI call fails

The two calls a turn cannot do without, the Brain and the narrator, do not degrade. After the retries they raise `ai/provider_base.py` → `AIUnavailableError`, as do a persistent refusal and an empty narration. The web handler for a turn, a correction, or a momentum burn then restores the snapshot it took before the call and tells the player that nothing in the story changed, as the design document asks (`web/handlers.py` → `_restore_after_failed_turn`, `_error_text`); `web/server.py` → `_dispatch_one_message` reports an unexpected error in a handler without its own catch.

Every other call degrades without a wrong state change: a failed revelation check counts as not yet confirmed, the metadata extraction and the Director are skipped, the opening extraction registers no NPCs and leaves the location and scene context empty, a failed correction analysis is treated as a state correction without operations, so the turn is narrated again with the player's correction text as guidance and nothing in the state changes, blueprint voicing returns None, and a recap uses its fallback. Each such site logs at warning or error level, and Elvira reports every warning as a problem, because the game would otherwise play on silently. The broad exception handling this needs is the one exception to "errors propagate" in CONTRIBUTING.md.

## Narration streaming

With `server.stream_narration: true` in `config.yaml`, a player turn streams the narrator's output. `web/handlers.py` hands `process_turn` a `SentenceStream`, which travels through the turn into `call_narrator`; `ai/provider_base.py` → `stream_with_retry` calls the provider's `stream_message`, and only text deltas reach the stream. The stream buffers text until a sentence is complete (abbreviations and hold markers live in `engine/parser.yaml`), cleans it with `parser.py` → `clean_sentence`, and the handler sends it as a `narration_sentence` message that the client appends to the log. The `narration` message still carries the authoritative, fully parsed text and a `stream_complete` flag: when the streamed text matches, the client leaves it; otherwise it replaces it and announces only the part the player has not heard. A hold marker (tag, code fence, JSON) stops the stream and leaves the rest to the final message; a failed stream falls back to a normal call. Openings, corrections, and momentum burns do not stream.

## Tool calling and prompt injection

Prompt injection fits when the data is always or nearly always relevant for the call and its size is bounded; a tool round there only adds overhead. Tool calling fits when the data is selective and the AI is best placed to choose, when the full set is too large to inject (the Datasworn oracle tables, whole memory histories), or when the need depends on the AI's judgment. Tool calling is wrong where the AI must not choose: the Brain cannot pick which moves are available or which NPCs are present, so it gets everything by prompt injection. The narrator gets the turn's resolved facts the same way, as a `<facts>` block, because they are always relevant for the call that triggered them and bounded by `max_per_turn`. New AI-consumable data is placed on the same axis.

Every role is prompt-only except the Director. Its prompt carries the scene, the story arc, and a reflection block for each NPC the engine selected; its answer's schema gives each of those NPCs exactly one reflection slot keyed by NPC id, and a reflection for any other NPC is rejected. It has one tool, `tools/builtins.py` → `query_game_state`, which returns the active threads, the unfired clocks, and every active or background NPC in one answer. Tools are registered with `@register("director")` in `tools/registry.py`, whose type hints generate the tool schema; they read the game state and the database and never mutate. `tools/handler.py` → `run_tool_loop` runs the rounds up to `max_tool_rounds` in `engine/pacing.yaml`, after which the Director writes its structured answer. The reflection blocks and the tool read the same memory window, `npc.reflection_observation_window` in `engine/npc.yaml`, so an NPC's recent memory looks the same on both paths.

## Adding a new AI provider

1. Create `ai/provider_yourname.py` implementing the `ModelListingProvider` protocol (`create_message` plus `list_models`, see `ai/provider_base.py`).
2. Add a branch for its type in `ai/api_client.py` → `build_adapter`.
3. Add an entry under `ai.providers` in `config.yaml` with that `type`, and point clusters at it with `provider:`.

A service with an OpenAI-compatible endpoint needs only step 3, with `type: openai_compatible`.
